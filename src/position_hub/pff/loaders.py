"""PFF loaders — narrow, typed reads of the three charting tables this project needs.

Landmines carried over from panthers_projects (handoff/POPULATION_MAP.md):
  * empty string ≠ NULL across the raw feed: test membership (`== 'Y'`), never IS NOT NULL.
  * pffdefense / pffoffense carry NO season column — season comes from pffplays via pff_GAMEID.
  * coverage_defense is usable 2019+ (2018 partial); its gsis_player_id is the NGS nfl_id.
  * pffplays.pff_GSISGAMEKEY = NGS game_key; pff_GSISPLAYID = NGS gsis_play_id.
"""
from __future__ import annotations

import polars as pl

from ..databricks.client import DataSource
from .vocab import align_family, assignment_class

PLAY_COLS = ["pff_GAMEID", "pff_PLAYID", "pff_GSISGAMEKEY", "pff_GSISPLAYID", "pff_GAMESEASON", "pff_WEEK",
             "pff_OFFTEAM", "pff_DEFTEAM", "pff_DOWN", "pff_DISTANCE", "pff_QUARTER", "pff_RUNPASS",
             "pff_PLAYACTION", "pff_RUNPASSOPTION", "pff_DROPBACKTYPE", "pff_DROPBACKDEPTH",
             "pff_PASSCOVERAGE", "pff_MOFOCSHOWN", "pff_MOFOCPLAYED", "pff_BOXPLAYERS", "pff_DEFPERSONNEL",
             "pff_DEFFRONT", "pff_BLITZDOG", "pff_SHOTGUN", "pff_PISTOL", "pff_SHIFTMOTION",
             "pff_OFFPERSONNELBASIC", "pff_RUNCONCEPTPRIMARY", "pff_RBDIRECTION", "pff_DBDEPTH", "pff_LBDEPTH",
             "pff_DEFENDERWIDTH", "pff_EXPECTEDPOINTSADDED"]
DEF_COLS = ["pff_GAMEID", "pff_PLAYID", "pff_PLAYERID", "pff_GSISPLAYERID", "pff_PLAYERNAME", "pff_POSITION",
            "pff_GAMEPOSITION", "pff_ROLE", "pff_BOXPLAYER", "pff_PLAYERDEPTH", "pff_DEFTECHNIQUE",
            "pff_PRESS", "pff_PRIMARYCOVERAGE", "pff_SECONDARYCOVERAGE", "pff_PRESSURE", "pff_STOP",
            "pff_TACKLE", "pff_MISSEDTACKLE"]
COV_COLS = ["gsis_game_id", "gsis_play_id", "gsis_player_id", "season", "week", "position", "season_position",
            "assignment", "modifier1", "modifier2", "primary_matchup_player_gsis_id", "press", "bust", "bail",
            "primary_coverage", "coverage_grade", "defense"]


# PFF team codes → standard NFL codes (the sister app's normTeam). Everything a person reads uses the standard code.
PFF_TEAM_TO_NFL = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU"}


def nfl_team_code(code: str | None) -> str | None:
    return PFF_TEAM_TO_NFL.get(code, code) if code else code


def flag(df: pl.DataFrame, col: str) -> pl.Expr:
    """A PFF 'did it happen' column as a Boolean expression, whatever type it arrived in.
    The feed says 'Y' / '' (empty string, never NULL); the bronze tables and the parquet export type some of
    them as smallint 0/1 (pff_PLAYACTION, pff_BLITZDOG, pff_RUNPASSOPTION); the INLINE SQL path returns every
    value as a string. Measured 2026-09-25: `pff_PLAYACTION == 'Y'` raised on both real sources."""
    if col not in df.columns:
        return pl.lit(None, pl.Boolean)
    dt = df.schema[col]
    if dt == pl.Boolean:
        return pl.col(col).fill_null(False)
    if dt.is_numeric():
        return pl.col(col).fill_null(0) != 0
    return pl.col(col).is_in(["Y", "1", "True", "true"])


def _present(src: DataSource, logical: str, wanted: list[str]) -> list[str]:
    """Only ask for columns the table actually has; the feed's column set has drifted before."""
    try:
        have = set(src.read(logical, limit=1).columns)
    except Exception:
        return wanted
    return [c for c in wanted if c in have]


def load_play_context(src: DataSource, seasons: list[int]) -> pl.DataFrame:
    cols = _present(src, "pffplays", PLAY_COLS)
    where = f"pff_GAMESEASON IN ({', '.join(str(int(s)) for s in seasons)})"
    df = src.read("pffplays", cols, where=where)
    ren = {"pff_GSISGAMEKEY": "game_key", "pff_GSISPLAYID": "gsis_play_id", "pff_GAMESEASON": "season",
           "pff_WEEK": "week"}
    df = df.rename({k: v for k, v in ren.items() if k in df.columns})
    casts = [pl.col(c).cast(pl.Int64, strict=False) for c in ("game_key", "gsis_play_id", "pff_GAMEID", "pff_PLAYID") if c in df.columns]
    casts += [pl.col(c).cast(pl.Int32, strict=False) for c in ("season", "week", "pff_DOWN", "pff_QUARTER") if c in df.columns]
    df = df.with_columns(casts)
    if "pff_RUNPASS" in df.columns:
        df = df.with_columns(is_pass=(pl.col("pff_RUNPASS") == "P"), is_run=(pl.col("pff_RUNPASS") == "R"))
    df = df.with_columns(is_play_action=flag(df, "pff_PLAYACTION"), is_rpo=flag(df, "pff_RUNPASSOPTION"), is_blitz=flag(df, "pff_BLITZDOG"))
    for c in ("pff_OFFTEAM", "pff_DEFTEAM"):
        if c in df.columns:
            df = df.with_columns(pl.col(c).map_elements(nfl_team_code, return_dtype=pl.Utf8).alias(c))
    return df


def load_defender_snaps(src: DataSource, plays: pl.DataFrame) -> pl.DataFrame:
    """pffdefense rows for the plays given, with season joined in and alignment family attached."""
    cols = _present(src, "pffdefense", DEF_COLS)
    gids = plays.get_column("pff_GAMEID").unique().drop_nulls().to_list()
    # chunk the IN list; a season is ~280 games
    frames = []
    for i in range(0, len(gids), 400):
        chunk = gids[i:i + 400]
        frames.append(src.read("pffdefense", cols, where=f"pff_GAMEID IN ({', '.join(str(int(g)) for g in chunk)})"))
    d = pl.concat(frames) if frames else pl.DataFrame({c: [] for c in cols})
    d = d.with_columns([pl.col(c).cast(pl.Int64, strict=False) for c in ("pff_GAMEID", "pff_PLAYID", "pff_PLAYERID", "pff_GSISPLAYERID") if c in d.columns])
    keys = plays.select("pff_GAMEID", "pff_PLAYID", "game_key", "gsis_play_id", "season", "week")
    d = d.join(keys, on=["pff_GAMEID", "pff_PLAYID"], how="inner")
    d = d.rename({"pff_GSISPLAYERID": "nfl_id", "pff_POSITION": "pff_alignment", "pff_GAMEPOSITION": "pff_game_position"})
    d = d.with_columns(
        pl.col("pff_alignment").map_elements(align_family, return_dtype=pl.Utf8).alias("pff_align_family"),
        flag(d, "pff_BOXPLAYER").alias("pff_in_box"),
    )
    return d


def load_coverage_assignments(src: DataSource, seasons: list[int]) -> pl.DataFrame:
    cols = _present(src, "coverage_defense", COV_COLS)
    where = f"season IN ({', '.join(str(int(s)) for s in seasons)})"
    c = src.read("coverage_defense", cols, where=where)
    c = c.rename({"gsis_game_id": "game_key", "gsis_player_id": "nfl_id", "position": "cov_alignment"})
    c = c.with_columns([pl.col(k).cast(pl.Int64, strict=False) for k in ("game_key", "gsis_play_id", "nfl_id") if k in c.columns])
    m1 = pl.col("modifier1") if "modifier1" in c.columns else pl.lit(None)
    m2 = pl.col("modifier2") if "modifier2" in c.columns else pl.lit(None)
    c = c.with_columns(
        pl.struct(a=pl.col("assignment"), m1=m1, m2=m2)
        .map_elements(lambda s: assignment_class(s["a"], s["m1"], s["m2"]), return_dtype=pl.Utf8)
        .alias("responsibility"))
    return c
