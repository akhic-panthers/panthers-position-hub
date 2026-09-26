# verify · out_smoke

2,893 defender-snaps · 264 plays · 2 games · seasons [2025]

## 1 · the standardized frame, checked against the league's own numbers

- plays: 264; ball proxy = tagged center on 76.5%, offensive-line median on 0.0% (no player tagged C at the snap)
- **direction rule vs NGS Play_Direction: 100.0% agree** on 251 plays
- ball vs center proxy (n=189): along-field offset median +0.00 yd (IQR -0.00…+0.00), lateral median -0.00 yd (IQR -0.00…+0.00); |along| > 1.5 yd on 0.0%
- ball vs ol_middle proxy (n=62): along-field offset median +0.00 yd (IQR -0.00…+0.00), lateral median -0.00 yd (IQR -0.00…+0.00); |along| > 1.5 yd on 0.0%
- our depth (from the snapper) minus NGS depth_from_los_at_snap: median +0.65 yd, IQR +0.47…+0.87, |diff| > 2 yd on 0.0% of 2,718 defender-snaps (expected: a constant ≈ +0.5–0.8, the snapper's body behind the ball)
- join identity: distance between our raw snap position and NGS x_at_snap/y_at_snap — median 0.00 yd, > 1 yd on 0.0% (a snap-frame disagreement of one or two frames, not a wrong player, if small)

## 2 · events

- plays with a snap event that reached this table: 264 (plays without `ball_snap`/`snap_direct` never get a row; see the features log for the play spine)
- line_set before the snap: 91.7% of plays
- pass_forward: 50.8% of plays
- handoff: 28.0% of plays
- an end event: 93.6% of plays
- PFF pass plays with a pass_forward event: 81.2% of 165 (sacks, scrambles and throwaways legitimately lack one)
- PFF run plays with a handoff event: 89.2% of 83 (QB keepers and direct snaps lack one)
- frames after the snap: median 112, < 20 (no 2 s window) on 0.0%

## 3 · the join spine (game_key, gsis_play_id, nfl_id)

| season | defender-snaps | → pffdefense | pass snaps → coverage_defense | → NGS player_play |
|---|---|---|---|---|
| 2025 | 2,893 | 95.1% | 99.6% | 94.0% |
- defender-snaps without a pffdefense row: 142; by NGS position: CB 28, DT 27, OLB 22, DE 22, SS 14, ILB 14
  - on 13 plays; plays where ALL our defenders miss (PFF has no defense rows for the play, e.g. a penalty no-play): 12
- defenders per play in tracking: 11 on 95.8%, 10 or fewer on 4.2%, 12+ on 0.0%

## 4 · rule alignment role × charted labels (row %, n)

**PFF alignment family (`pff_POSITION` → family)**

| rule role | n | BOUNDARY_CB | BOX_SAFETY | DEEP_SAFETY | EDGE | INTERIOR_DL | OFF_BALL_LB | SLOT_CB |
|---|---|---|---|---|---|---|---|---|
| EDGE | 533 | · | · | · | 98% | · | · | 1% |
| INTERIOR_DL | 534 | · | · | · | 17% | 80% | 3% | · |
| OFF_BALL_LB | 435 | · | · | · | 1% | · | 95% | 4% |
| OVERHANG | 19 | · | · | · | 11% | · | 58% | 32% |
| SLOT_CB | 269 | 6% | 1% | · | 4% | · | 15% | 74% |
| BOUNDARY_CB | 536 | 80% | 2% | · | 2% | · | 11% | 5% |
| BOX_SAFETY | 52 | · | 44% | 10% | · | · | 8% | 38% |
| DEEP_HALF | 281 | · | 9% | 88% | · | · | · | 3% |
| DEEP_MIDDLE | 92 | · | 11% | 89% | · | · | · | · |

- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **85.9%** on 2,751

**NGS ngs_position → family**

| rule role | n | BOUNDARY_CB | BOX_SAFETY | DEEP_SAFETY | EDGE | INTERIOR_DL | OFF_BALL_LB | SLOT_CB |
|---|---|---|---|---|---|---|---|---|
| EDGE | 527 | 2% | · | · | 94% | 2% | · | 1% |
| INTERIOR_DL | 529 | · | · | · | 1% | 99% | · | · |
| OFF_BALL_LB | 431 | · | · | · | · | 3% | 96% | 1% |
| OVERHANG | 19 | 32% | · | · | 11% | · | 26% | 32% |
| SLOT_CB | 265 | 6% | · | 2% | 5% | · | 21% | 66% |
| BOUNDARY_CB | 528 | 85% | · | 2% | 2% | · | 6% | 4% |
| BOX_SAFETY | 52 | · | 2% | 63% | · | · | 13% | 21% |
| DEEP_HALF | 277 | · | · | 100% | · | · | · | · |
| DEEP_MIDDLE | 90 | · | 2% | 98% | · | · | · | · |

- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **89.4%** on 2,718


## 5 · bite at 2 s by rule role (yards; negative = toward the line)

| rule role | n | pass: median bite | pass: IQR | run: median bite | ground covered 2 s (median) |
|---|---|---|---|---|---|
| EDGE | 567 | -5.4 | -6.6…-3.9 | -1.2 | 5.0 |
| INTERIOR_DL | 613 | -3.6 | -4.3…-2.8 | -0.6 | 3.4 |
| OFF_BALL_LB | 461 | +0.5 | -1.3…+1.8 | -1.8 | 2.9 |
| OVERHANG | 21 | +1.0 | -6.3…+2.6 | -1.2 | 3.9 |
| SLOT_CB | 269 | +1.6 | +0.1…+2.9 | -0.9 | 3.5 |
| BOUNDARY_CB | 536 | +2.7 | +1.2…+3.9 | +0.7 | 3.3 |
| BOX_SAFETY | 53 | +0.8 | -0.6…+3.1 | -2.3 | 3.4 |
| DEEP_HALF | 281 | +3.1 | +0.3…+4.8 | +0.0 | 3.9 |
| DEEP_MIDDLE | 92 | +3.5 | +1.7…+4.6 | +0.2 | 3.5 |

## 6 · depth by rule role (yards from the snapper)

| rule role | n | depth p5 | median | p95 | |lateral| median |
|---|---|---|---|---|---|
| EDGE | 567 | 0.9 | 1.3 | 1.8 | 5.6 |
| INTERIOR_DL | 613 | 0.9 | 1.3 | 1.8 | 1.9 |
| OFF_BALL_LB | 461 | 2.5 | 4.8 | 6.0 | 2.2 |
| OVERHANG | 21 | 2.1 | 3.5 | 5.0 | 6.8 |
| SLOT_CB | 269 | 1.4 | 4.4 | 6.9 | 8.6 |
| BOUNDARY_CB | 536 | 1.4 | 5.6 | 8.7 | 12.6 |
| BOX_SAFETY | 53 | 6.2 | 9.1 | 9.9 | 5.8 |
| DEEP_HALF | 281 | 10.4 | 12.8 | 15.7 | 6.8 |
| DEEP_MIDDLE | 92 | 10.6 | 13.3 | 16.1 | 3.2 |
- defenders standardised BEHIND the line at the snap (depth < −0.5): 0 (0.0%) — a few are real (a corner over a stacked release), many would mean a flipped play
