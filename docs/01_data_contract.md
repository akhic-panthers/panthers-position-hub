# Data contract — what this project reads, by name

Truth for names is `data_contracts/uc_inventory.json` once `poshub discover` has run against the workspace. Until then this file carries what was measured in the sister project (panthers_projects: `handoff/POPULATION_MAP.md`, `audit/output/data_audit/NGS_*.md`, transcripts 2026-08-21).

## Databricks
- Workspace: `https://adb-7405617646104787.7.azuredatabricks.net` (Azure, `o=7405617646104787`).
- Catalog `pff`, schema `bronze` — PFF's feed, one table per PFF object. Same layouts for other leagues under `pff.cff`, `pff.cfl`, `pff.ufl`; `pff.silver` / `pff.gold` hold analytics tables (`scheme_data`, `pass_rush_entropy`).
- Writable Volume: `/Volumes/pff/bronze/exports/` (the notebook writes `position_hub/charted_snaps`).
- Auth from a laptop: `databricks auth login --host <workspace>` (OAuth), or a PAT in `DATABRICKS_TOKEN`. SQL needs a warehouse `DATABRICKS_HTTP_PATH`.
- ⛔ From a Claude cloud container the host is denied by the environment's network policy (measured 2026-09-25: `CONNECT tunnel failed, response 403`). Add the host to the environment's allowed domains or run the notebook in-workspace.

### Tables (rows measured 2026-08-20)

| logical | full name | rows | grain | keys we use |
|---|---|---|---|---|
| pffplays | `pff.bronze.pffplays` | 1,019,359 | play | `pff_GAMEID`,`pff_PLAYID` · `pff_GSISGAMEKEY`(=NGS `game_key`), `pff_GSISPLAYID`(=NGS `gsis_play_id`) · `pff_GAMESEASON`, `pff_WEEK` |
| pffdefense | `pff.bronze.pffdefense` | 9,184,293 | defender × play | `pff_GAMEID`,`pff_PLAYID`,`pff_GSISPLAYERID`(=NGS `nfl_id`), `pff_PLAYERID` (PFF id). **No season column** — join pffplays |
| pffoffense | `pff.bronze.pffoffense` | 9,186,059 | offensive player × play | same key pattern; `pff_ROLE = 'Pass Route'` rows carry routes |
| coverage_defense | `pff.bronze.coverage_defense` | 1,205,631 | defender × pass play | `gsis_game_id`,`gsis_play_id`,`gsis_player_id`(=NGS `nfl_id`), `season` — **2019+ usable, 2018 partial** |
| coverage_offense | `pff.bronze.coverage_offense` | 706,174 | receiver × pass play | no 2022 at source |
| pffplayerblockings | `pff.bronze.pffplayerblockings` | 5,625,517 | block × play | `BlockedPlayerId` null ≠ unblocked |
| pffrosters / nfl_player / pffgames | `pff.bronze.*` | 709,928 / 15,982 / 6,727 | | |

### Columns this project reads
**pffplays:** situation (`pff_DOWN`,`pff_DISTANCE`,`pff_QUARTER`), `pff_RUNPASS` (P/R), `pff_PLAYACTION`, `pff_RUNPASSOPTION`, `pff_DROPBACKTYPE`, `pff_DROPBACKDEPTH`, `pff_PASSCOVERAGE`, `pff_MOFOCSHOWN`/`pff_MOFOCPLAYED` (O/C), `pff_BOXPLAYERS`, `pff_DEFPERSONNEL`, `pff_DEFFRONT`, `pff_BLITZDOG`, `pff_SHOTGUN`, `pff_PISTOL`, `pff_SHIFTMOTION`, `pff_OFFPERSONNELBASIC`, `pff_RUNCONCEPTPRIMARY`, `pff_RBDIRECTION`, `pff_EXPECTEDPOINTSADDED`, and the depth/width strings `pff_DBDEPTH`, `pff_LBDEPTH`, `pff_DEFENDERWIDTH` in the form `LCB (5); SCBL (3); FSL (11)` (parser: `pff.vocab.parse_depth_string`).

**pffdefense:** `pff_POSITION` (alignment slot on the snap — the field this project is built to get past), `pff_GAMEPOSITION` (his usual slot that game), `pff_ROLE` (Run Defense / Pass Rush / Coverage …), `pff_BOXPLAYER` (Y/""), `pff_PLAYERDEPTH`, `pff_DEFTECHNIQUE`, `pff_PRESS`, `pff_PRIMARYCOVERAGE`, `pff_SECONDARYCOVERAGE`, `pff_PRESSURE`, `pff_STOP`, `pff_TACKLE`, `pff_MISSEDTACKLE`.

**coverage_defense:** `position` (30 alignment slots: RCB LCB SCBL SCBR SCBiL SCBiR SCBoL SCBoR FS FSL FSR SS SSL SSR MLB LILB RILB LLB RLB LOLB ROLB LEO REO LE RE DLT DRT NT NLT NRT), `season_position`, `assignment` (19 classes: **MAN HOL CFL CFR HCL HCR 3L 3M 3R DF 4IL 4IR 4OL 4OR 2L 2R FL FR PRE**), `modifier1`/`modifier2` (MAT SEA REA TAM CAR BRK DRP DOG PUP PAF …; **MAT/SEA/CAR/TAM = pattern-match, a zone call played as man on that rep**, +33% man reps over the charted MAN flag), `primary_matchup_player_gsis_id`, `press` (JAM/MIR/CNT, not boolean), `bust`, `bail`, `primary_coverage`, `coverage_grade`, `defense`.

### Landmines (all measured in the sister project)
- **Empty string ≠ NULL** across the raw feed. Test membership (`== 'Y'`, `IN ('C','O')`), never `IS NOT NULL`.
- PFF left/right are the **defense's** left and right.
- `pffdefense.pff_POSITION` is the alignment of **that rep**, not the player's position; a slot corner gets an edge label on the snap he blitzes from the edge.
- `separation` in the coverage feeds is an 18-value **code**, not yards; `is_open` is the same signal.
- `gsis_id` ("00-00…") ≠ `nfl_id`; the coverage feeds and `pffdefense.pff_GSISPLAYERID` are in `nfl_id` space, which is what NGS carries as `nfl_id`.

## NGS tracking (Next Gen Stats Player Play)
- Layout: `<season>_NGS_Player_Play/<week>/<game_key>.parquet`, one game per file, 2022–2025 (36 GB, 1,338 files), under `PANTHERS_DATA_DIR` on the Mac. Weeks `1–18`, `19–21`, `23`. **`preseason/` has a different, play-level 108-column schema and is skipped.** 2024 is missing week 2 and the postseason.
- Columns: `game_key, nfl_id, time, team_id, gsis_id, esb_id, player_name, jersey_number, position, position_group, is_on_field, x, y, z(null), s, a, dis, o, dir, gsis_play_id, event, sa`. ~10 Hz. No `frame_id` (derived as dense rank of `time` within play). **No ball track** — the snapper is the ball proxy.
- Raw frame: x ∈ [0,120] end zone to end zone, y ∈ [0,53.3]. Angles: 0 = +y, clockwise.
- Events used: `ball_snap`/`snap_direct` (manual preferred over `autoevent_ballsnap`), `line_set`, `pass_forward`, `handoff`, `pass_arrived`, ends (`tackle`, `out_of_bounds`, `pass_outcome_*`, `qb_sack`, …), `play_action`, `man_in_motion`, `shift`.
- Whether these frames also exist as a Unity Catalog table is **unknown** — `poshub discover` lists any table whose name contains ngs / tracking / player_play / frame; set `POSHUB_TABLE_NGS_TRACKING` if one turns up.

## Join spine
`(game_key, gsis_play_id, nfl_id)` everywhere. `game_key = pff_GSISGAMEKEY = coverage_defense.gsis_game_id`; `nfl_id = pff_GSISPLAYERID = coverage_defense.gsis_player_id`.

## Telemetry / film
- **Thunder (XOS / Catapult film):** `https://tclightningservices.xosdigital.com/Api` (ThunderAPI v1, 39 endpoints), SSO at `https://tcssoservices.xosdigital.com/sso/RESTSSOServices.svc`. Auth `Authorization: API <base64(user:pass)>`. Deep link `LaunchPlayerByGSIS` takes `^game_key|gsis_play_id`. Server-side only; credential never in a client.
- **Catapult OpenField:** the club's JWT (issuer `backend-us.openfield.catapultsports.com`, scopes sensor-read-only, athletes/activities/tags/parameters-update, customer 1302) is for practice GPS, **not** film. Client at `telemetry/openfield.py`, unverified from this environment.
- **PFF:** no API in this stack. `https://ultimate.pff.com/play/<pff_PLAYID>` is the film page; `pffplays` carries both key spaces so the link is a join.
