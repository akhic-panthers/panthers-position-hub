# panthers-position-hub

**What does he actually play?** PFF charts one position per snap. This project gives every defender-snap a
probability vector over roles from NGS tracking geometry, with PFF charting as context and check, and rolls it
up to a player-season **role mix** with percentiles against position peers — the college player viewer's
position percentiles, for the pros, from the tracking.

```
                 tracking (NGS, 10 Hz)            charting (PFF, Unity Catalog)
                 ─────────────────────            ─────────────────────────────
                 where he stood at the snap       pffplays · pffdefense · coverage_defense
                 what he did in 2.0 s
                            └──────────────┬──────────────┘
                                 one row per defender-snap
                                           │
                     alignment model  ─────┼─────  responsibility model
                     (9 roles, soft)       │       (charted where charted, else modelled)
                                           │
                        player-season role mix · peer percentiles · gates
                                           │
                        viewer JSON  →  viewer/index.html  /  the sister app's boards
```

Example output (synthetic dry run, so the names are fake): a safety at **41% deep middle · 32% deep half ·
27% box safety**, entropy 1.09 (three jobs), 75th percentile for depth among safeties.

## Quick start

```bash
pip install -e ".[dev]"            # numpy · polars · pyarrow · scikit-learn · requests · pytest
databricks auth login --host https://adb-7405617646104787.7.azuredatabricks.net   # once; or `az login`
export DATABRICKS_HOST=https://adb-7405617646104787.7.azuredatabricks.net          # no token needed after a CLI login
pytest -q                          # 28 tests, synthetic tracking, ~15 s

poshub demo                        # whole pipeline on synthetic plays → viewer/data/role_mix.json
python -m http.server -d viewer 8765   # open http://localhost:8765
```

On a machine that holds the tracking (`PANTHERS_DATA_DIR/<season>_NGS_Player_Play/`) and can reach the workspace:

```bash
poshub status                      # Databricks reachable? local export? Thunder? OpenField?
poshub probe                       # host → auth → catalog → warehouse → SQL → tables, with the remedy for the first failure
poshub discover                    # → data_contracts/uc_inventory.json (catalogs, tables, columns, NGS candidates)
poshub features --seasons 2024 2025          # NGS + PFF → out/features.parquet
poshub fit --holdout-weeks 17 18             # → out/model.pkl (held out by GAME)
poshub score                                 # → out/scored.parquet (probabilities per snap)
poshub mix                                   # → out/role_mix.parquet, out/gates.md, viewer/data/role_mix.json
```

If the workspace is reachable but the tracking is not, run `notebooks/databricks/01_role_snaps_uc.py` in the
workspace first; it writes the charted half of the snap table to `/Volumes/pff/bronze/exports/position_hub`.

## Read in this order
1. `docs/00_research_brief.md` — the question, the method, what is and is not built.
2. `docs/02_role_taxonomy.md` — the registered role vocabulary and every threshold.
3. `docs/REGISTERED_role_attribution_v1.md` — the gates, written before any real snap is scored.
4. `docs/01_data_contract.md` — Databricks names, NGS schema, join spine, landmines.
   `docs/03_databricks_setup.md` — how to authenticate from a laptop, a container, or CI, and what each probe rung means.
5. `docs/paper_notes/eager_seth_2023.md` — Eric's paper and what is taken from it.

## Layout

```
src/position_hub/
  config.py            env, table registry (pff.bronze.*), registered constants (2 s window, snap floors)
  databricks/          Unity Catalog REST · SQL (Statement API / connector) · local parquet fallback · discover
  pff/                 vocab (alignment slots → families, 19 assignments → 6 responsibilities), typed loaders
  ngs/                 per-game loader · standardized frame · per-defender snap / 2 s / throw features
  roles/               taxonomy · rule labels · two HistGB classifiers · role mix · percentiles · team shells
  eval/                registered gates incl. the destruction control that must fail
  telemetry/           Thunder (XOS film) · Catapult OpenField · PFF Ultimate links
  viewer/              JSON export in the sister app's board shape
  synth.py             NGS-shaped synthetic plays with hidden truth (tests + demo; never a result)
  cli.py               poshub
notebooks/databricks/  in-workspace builder for the charted snap table
viewer/                static viewer (index.html + data/role_mix.json)
tests/                 28 tests on synthetic tracking
data_contracts/        uc_tables.json (measured), uc_inventory.json (written by discover)
```

## House rules carried over from panthers_projects
Gate first, tune never. A NO-GO ships as a report. A bug is never a finding. Descriptive vs predictive is
labelled (role shares are ratings of deployment, not grades or projections). Nothing generated enters any
pool, price, index or board. Held out by game, never by row. Empty string ≠ NULL in the PFF feed.

## Status (2026-09-25)
Built and tested on synthetic tracking only. This container could not reach the Databricks workspace
(network policy) and holds no tracking, so no real snap has been scored; the first real run fills the gate
table in `docs/REGISTERED_role_attribution_v1.md`.
