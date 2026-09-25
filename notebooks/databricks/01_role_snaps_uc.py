# Databricks notebook source
# MAGIC %md
# MAGIC # Position Hub · role snaps from Unity Catalog
# MAGIC
# MAGIC Runs **inside the Panthers workspace** (`adb-7405617646104787.7.azuredatabricks.net`), where the PFF bronze
# MAGIC tables live and no network policy is in the way. It builds the charted half of the defender-snap table
# MAGIC (`pffplays` × `pffdefense` × `coverage_defense`) and writes it to a Volume; the tracking half is joined
# MAGIC by `poshub features` wherever the NGS frames are (local per-game parquet, or a UC table if one exists).
# MAGIC
# MAGIC Landmines (from panthers_projects/handoff/POPULATION_MAP.md): empty string ≠ NULL (test `== 'Y'`),
# MAGIC `pffdefense` has no season column (join `pffplays` on `pff_GAMEID`), `coverage_defense` is 2019+.

# COMMAND ----------

CATALOG, SCHEMA = "pff", "bronze"
SEASONS = [2022, 2023, 2024, 2025]
VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/exports/position_hub"
T = lambda t: f"{CATALOG}.{SCHEMA}.{t}"

# COMMAND ----------

# Cell 1 — every table resolves before a byte is written; the column lists are the data contract
for t in ["pffplays", "pffdefense", "coverage_defense", "pffrosters"]:
    cols = [r.col_name for r in spark.sql(f"DESCRIBE TABLE {T(t)}").collect() if not r.col_name.startswith("#")]
    print(f"{T(t)}: {len(cols)} columns")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.exports")

# COMMAND ----------

# Cell 2 — discovery: is NGS tracking registered anywhere in Unity Catalog?
cands = []
for c in [r.catalog for r in spark.sql("SHOW CATALOGS").collect()]:
    try:
        for s in [r.databaseName for r in spark.sql(f"SHOW SCHEMAS IN `{c}`").collect()]:
            for r in spark.sql(f"SHOW TABLES IN `{c}`.`{s}`").collect():
                fn = f"{c}.{s}.{r.tableName}".lower()
                if any(h in fn for h in ("ngs", "tracking", "player_play", "frame", "nextgen")):
                    cands.append(fn)
    except Exception as e:  # a catalog we cannot read is a fact, not a crash
        print("skip", c, str(e)[:80])
print("NGS candidates:", cands or "none — tracking stays on per-game parquet (PANTHERS_DATA_DIR)")

# COMMAND ----------

seasons_sql = ", ".join(map(str, SEASONS))
plays = spark.sql(f"""
  SELECT CAST(pff_GAMEID AS BIGINT) pff_GAMEID, CAST(pff_PLAYID AS BIGINT) pff_PLAYID,
         CAST(pff_GSISGAMEKEY AS BIGINT) game_key, CAST(pff_GSISPLAYID AS BIGINT) gsis_play_id,
         CAST(pff_GAMESEASON AS INT) season, CAST(pff_WEEK AS INT) week, pff_OFFTEAM, pff_DEFTEAM,
         CAST(pff_DOWN AS INT) pff_DOWN, pff_DISTANCE, pff_QUARTER, pff_RUNPASS, pff_PLAYACTION, pff_RUNPASSOPTION,
         pff_DROPBACKTYPE, pff_DROPBACKDEPTH, pff_PASSCOVERAGE, pff_MOFOCSHOWN, pff_MOFOCPLAYED, pff_BOXPLAYERS,
         pff_DEFPERSONNEL, pff_DEFFRONT, pff_BLITZDOG, pff_SHOTGUN, pff_PISTOL, pff_SHIFTMOTION, pff_OFFPERSONNELBASIC,
         pff_RUNCONCEPTPRIMARY, pff_RBDIRECTION, pff_DBDEPTH, pff_LBDEPTH, pff_DEFENDERWIDTH, pff_EXPECTEDPOINTSADDED,
         (pff_RUNPASS = 'P') AS is_pass, (pff_PLAYACTION = 'Y') AS is_play_action
  FROM {T('pffplays')} WHERE CAST(pff_GAMESEASON AS INT) IN ({seasons_sql})""")
plays.createOrReplaceTempView("ph_plays")
print("plays", plays.count())

# COMMAND ----------

dsnaps = spark.sql(f"""
  SELECT p.game_key, p.gsis_play_id, p.season, p.week, p.pff_GAMEID, p.pff_PLAYID,
         CAST(d.pff_GSISPLAYERID AS BIGINT) nfl_id, CAST(d.pff_PLAYERID AS BIGINT) pff_player_id, d.pff_PLAYERNAME,
         d.pff_POSITION AS pff_alignment, d.pff_GAMEPOSITION AS pff_game_position, d.pff_ROLE,
         (d.pff_BOXPLAYER = 'Y') AS pff_in_box, d.pff_PLAYERDEPTH, d.pff_DEFTECHNIQUE, d.pff_PRESS,
         d.pff_PRIMARYCOVERAGE, d.pff_SECONDARYCOVERAGE, d.pff_PRESSURE, d.pff_STOP, d.pff_TACKLE, d.pff_MISSEDTACKLE
  FROM {T('pffdefense')} d
  JOIN ph_plays p ON CAST(d.pff_GAMEID AS BIGINT) = p.pff_GAMEID AND CAST(d.pff_PLAYID AS BIGINT) = p.pff_PLAYID""")
dsnaps.createOrReplaceTempView("ph_dsnaps")
print("defender-snaps", dsnaps.count())

# COMMAND ----------

cov = spark.sql(f"""
  SELECT CAST(gsis_game_id AS BIGINT) game_key, CAST(gsis_play_id AS BIGINT) gsis_play_id,
         CAST(gsis_player_id AS BIGINT) nfl_id, CAST(season AS INT) season, position AS cov_alignment, season_position,
         assignment, modifier1, modifier2, primary_matchup_player_gsis_id, press, bust, bail, primary_coverage, coverage_grade, defense,
         CASE WHEN assignment = 'MAN' THEN 'MAN'
              WHEN assignment = 'PRE' THEN 'RUSH'
              WHEN assignment IN ('3L','3M','3R','DF','4IL','4IR','4OL','4OR','2L','2R') THEN
                   CASE WHEN modifier1 IN ('MAT','SEA','CAR','TAM') OR modifier2 IN ('MAT','SEA','CAR','TAM') THEN 'MAN_MATCH' ELSE 'DEEP_ZONE' END
              WHEN assignment IN ('HOL','CFL','CFR','HCL','HCR','FL','FR') THEN
                   CASE WHEN modifier1 IN ('MAT','SEA','CAR','TAM') OR modifier2 IN ('MAT','SEA','CAR','TAM') THEN 'MAN_MATCH' ELSE 'UNDER_ZONE' END
         END AS responsibility
  FROM {T('coverage_defense')} WHERE CAST(season AS INT) IN ({seasons_sql})""")
cov.createOrReplaceTempView("ph_cov")
print("coverage rows", cov.count())

# COMMAND ----------

snaps = spark.sql("""
  SELECT d.*, c.cov_alignment, c.season_position, c.assignment, c.modifier1, c.modifier2, c.responsibility,
         c.primary_matchup_player_gsis_id, c.press AS cov_press, c.bust, c.bail,
         p.is_pass, p.is_play_action, p.pff_PASSCOVERAGE, p.pff_MOFOCSHOWN, p.pff_MOFOCPLAYED, p.pff_BOXPLAYERS,
         p.pff_DOWN, p.pff_DISTANCE, p.pff_DROPBACKTYPE, p.pff_DROPBACKDEPTH, p.pff_RUNCONCEPTPRIMARY,
         p.pff_DBDEPTH, p.pff_LBDEPTH, p.pff_DEFENDERWIDTH, p.pff_OFFTEAM, p.pff_DEFTEAM
  FROM ph_dsnaps d
  JOIN ph_plays p USING (game_key, gsis_play_id)
  LEFT JOIN ph_cov c USING (game_key, gsis_play_id, nfl_id)""")
snaps.createOrReplaceTempView("ph_snaps")
tot = snaps.count()
charted = snaps.filter("responsibility IS NOT NULL").count()
print(f"charted snaps {tot:,}; with coverage assignment {charted:,} ({charted/tot:.1%})")

# COMMAND ----------

# Cell 7 — the population, by season, so no one designs on a population they do not have
display(spark.sql("""
  SELECT season, COUNT(*) snaps, COUNT(DISTINCT game_key) games, COUNT(DISTINCT nfl_id) defenders,
         AVG(CASE WHEN responsibility IS NOT NULL THEN 1.0 ELSE 0.0 END) charted_share,
         AVG(CASE WHEN is_pass THEN 1.0 ELSE 0.0 END) pass_share
  FROM ph_snaps GROUP BY season ORDER BY season"""))

# COMMAND ----------

(snaps.write.mode("overwrite").partitionBy("season").parquet(f"{VOLUME}/charted_snaps"))
print("wrote", f"{VOLUME}/charted_snaps", "→ pull with: databricks fs cp -r dbfs:" + VOLUME + " ./data/position_hub")

# COMMAND ----------

# MAGIC %md
# MAGIC Next: on the machine that holds the NGS frames, `poshub features --seasons 2024 2025` reads the tracking,
# MAGIC joins these charted snaps by (game_key, gsis_play_id, nfl_id), then `poshub fit` / `score` / `mix`.
