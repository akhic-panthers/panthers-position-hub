# Position Hub — research brief

**Question.** PFF charts one position per player per snap (`pff_POSITION`, a slot like `FSL` or `RILB`) and one per game/season (`pff_GAMEPOSITION`, "how he was most commonly used"). Neither says what a man *plays*. A safety listed FS who lines up at 8 yards over the tight end on a third of his snaps is not "a free safety"; he is 65% deep middle, 25% box safety, 10% slot. This project produces that field, per snap and per season, from NGS tracking geometry with PFF charting as context and check, so the Panthers can compare defenders by the jobs they actually did — the way the college player viewer already compares prospects by position percentiles.

**Why defense.** On offense the alignment is the position (a left tackle is a left tackle). On defense the same eleven men are re-deployed by call: the nickel is a corner on one snap and a box player the next; the "strong safety" rotates to the post; the edge drops. That is where a one-label field loses the most information, and where tracking can recover it.

## What is built (v0.1)

| layer | what | where |
|---|---|---|
| data access | Unity Catalog REST + SQL (Statement Execution API or `databricks-sql-connector`), local parquet fallback in the sister repo's layout, table registry `pff.bronze.*`, discovery to `data_contracts/uc_inventory.json` | `src/position_hub/databricks/` |
| charting | typed loaders for `pffplays`, `pffdefense`, `coverage_defense`; alignment-slot → family; 19 coverage assignments → 6 responsibilities with pattern-match modifiers separated | `src/position_hub/pff/` |
| tracking | per-game NGS loader, standardized frame (offense +x, ball proxy origin, QB-behind-the-line direction rule), snap / line-set / throw / handoff / 2 s anchors, per-defender geometry | `src/position_hub/ngs/` |
| roles | registered taxonomy (9 alignment roles × 6 responsibilities), transparent rule labels, two gradient-boosted classifiers giving per-snap probability vectors, player-season role mix, peer percentiles, team shell mix | `src/position_hub/roles/` |
| gates | PFF agreement (sanity), held-out-GAME accuracy, split-half stability, destruction control that must fail | `src/position_hub/eval/` |
| film / telemetry | Thunder (XOS, Catapult film) client with the measured `API` auth scheme and GSIS deep links; Catapult OpenField client; PFF Ultimate play links | `src/position_hub/telemetry/` |
| surfaces | viewer JSON in the sister app's board shape + a static viewer | `src/position_hub/viewer/`, `viewer/` |
| in-workspace | a Databricks notebook that builds the charted half of the snap table where the data lives | `notebooks/databricks/` |

## Method in one paragraph
Every defender-snap gets geometry at the snap (depth off the ball, lateral offset, on-line / in-box / outside-tackle flags, which receiver he is over and how far, cushion, sideline distance, how many deep defenders the team shows, his depth rank), pre-snap movement from line-set to snap (rotation), and behaviour at 2.0 s (bite = depth change, lateral move, ground covered, distance to the aligned receiver, to the QB, to the ball carrier on runs, whether he crossed the line), plus at the throw. **Alignment role** is a classifier trained on the snaps where a geometric rule and PFF's charted alignment family independently agree, then scored on all snaps: its probability vector is the snap's position field. **Responsibility** is a classifier trained on PFF's charted coverage assignment (`coverage_defense`, folded to RUSH / MAN / MAN_MATCH / UNDER_ZONE / DEEP_ZONE), scored on every pass snap; run snaps are geometric (RUN_FIT / RUSH). A **player-season role mix** is the mean of the vectors over his snaps; **percentiles** are within roster-position group and season, among players above the snap floor. The 2 s window is Eager & Seth's (docs/paper_notes).

## What it is not (yet)
- **Not a grade.** Shares describe deployment. "More deep-middle than 88% of safeties" is a fact about usage, not quality.
- **Not GCOE/BDUE.** The paper's over-expected residuals are phase 2 (the features they need — bite, ground covered, closing on the carrier — are already computed). They will ship as per-play descriptors, never a season leaderboard, per the house rule.
- **Not offense.** The taxonomy is defensive. Offensive alignment roles (X/Z/slot/wing/inline/backfield) are a small addition to `rules.py` if wanted; the geometry already exists in `_receivers()`.
- **Not validated on real snaps.** Everything here has run only on synthetic tracking (`position_hub.synth`), because this container cannot reach the workspace (network policy) and holds no tracking. The gates are written; the first real run decides GO / NO-GO. See `REGISTERED_role_attribution_v1.md`.

## Population (cite handoff/POPULATION_MAP.md in the sister repo)
Tracking 2022–2025 (2024 missing week 2 and the postseason) ∩ `pffdefense` (all seasons) ∩ `coverage_defense` (2019+) ⇒ **2022–2025, four seasons**, ~700k defender-snaps on pass plays with a charted assignment, ~1.3M total.

## Open questions for Eric
1. Is NGS frame tracking registered in Unity Catalog, or only on the Mac? (`poshub discover` / notebook cell 2 answers this.)
2. Is a play-level NGS product (the 108-column preseason schema) obtainable for the regular season? It carries `depth_from_los_at_snap` and would remove the ball-proxy caveat.
3. Which single number should the viewer lead with for a safety: deep share, box share, or entropy (number of jobs)? Three options, pick one.
4. Whether the Catapult OpenField feed (practice GPS) is in scope for a "rehearsed role" axis; the connector exists, no call has been made.
