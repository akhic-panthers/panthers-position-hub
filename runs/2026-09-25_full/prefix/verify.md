# verify · out

1,712,656 defender-snaps · 155,734 plays · 1139 games · seasons [2022, 2023, 2024, 2025]

## 1 · the standardized frame, checked against the league's own numbers

- plays: 155,734; ball proxy = tagged center on 91.0%, offensive-line median on 0.0% (no player tagged C at the snap)
- **direction rule vs NGS Play_Direction: 99.9% agree** on 148,867 plays
  - disagreements by ball proxy: center 95, ol_middle 2
- ball vs center proxy (n=134,621): along-field offset median +0.00 yd (IQR -0.00…+0.00), lateral median +0.00 yd (IQR -0.00…+0.00); |along| > 1.5 yd on 0.1%
- ball vs ol_middle proxy (n=13,960): along-field offset median -0.00 yd (IQR -0.00…+0.00), lateral median +0.00 yd (IQR -0.00…+0.00); |along| > 1.5 yd on 0.1%
- ball vs ol_median proxy (n=1): along-field offset median +0.58 yd (IQR +0.58…+0.58), lateral median -2.39 yd (IQR -2.39…-2.39); |along| > 1.5 yd on 0.0%
- our depth (from the snapper) minus NGS depth_from_los_at_snap: median +0.63 yd, IQR +0.43…+0.85, |diff| > 2 yd on 0.2% of 1,619,674 defender-snaps (expected: a constant ≈ +0.5–0.8, the snapper's body behind the ball)
- join identity: distance between our raw snap position and NGS x_at_snap/y_at_snap — median 0.00 yd, > 1 yd on 0.0% (a snap-frame disagreement of one or two frames, not a wrong player, if small)

## 2 · events

- plays with a snap event that reached this table: 155,734 (plays without `ball_snap`/`snap_direct` never get a row; see the features log for the play spine)
- line_set before the snap: 97.3% of plays
- pass_forward: 50.7% of plays
- handoff: 33.6% of plays
- an end event: 93.3% of plays
- PFF pass plays with a pass_forward event: 87.6% of 89,682 (sacks, scrambles and throwaways legitimately lack one)
- PFF run plays with a handoff event: 89.8% of 57,490 (QB keepers and direct snaps lack one)
- frames after the snap: median 93, < 20 (no 2 s window) on 0.0%

## 3 · the join spine (game_key, gsis_play_id, nfl_id)

| season | defender-snaps | → pffdefense | pass snaps → coverage_defense | → NGS player_play |
|---|---|---|---|---|
| 2022 | 424,457 | 96.3% | 99.8% | 95.0% |
| 2023 | 431,997 | 96.2% | 99.8% | 94.9% |
| 2024 | 430,506 | 95.8% | 99.2% | 94.4% |
| 2025 | 425,696 | 94.5% | 98.6% | 93.5% |
- defender-snaps without a pffdefense row: 73,813; by NGS position: DT 13033, CB 11826, DE 11449, OLB 9447, ILB 8491, FS 6270
  - on 6,822 plays; plays where ALL our defenders miss (PFF has no defense rows for the play, e.g. a penalty no-play): 6,526
- defenders per play in tracking: 11 on 99.6%, 10 or fewer on 0.3%, 12+ on 0.0%

## 4 · rule alignment role × charted labels (row %, n)

**PFF alignment family (`pff_POSITION` → family)**

| rule role | n | BOUNDARY_CB | BOX_SAFETY | DEEP_SAFETY | EDGE | INTERIOR_DL | OFF_BALL_LB | SLOT_CB |
|---|---|---|---|---|---|---|---|---|
| EDGE | 311,510 | 1% | · | · | 98% | · | · | 1% |
| INTERIOR_DL | 336,568 | · | · | · | 25% | 70% | 5% | · |
| OFF_BALL_LB | 264,599 | · | · | · | 2% | 1% | 93% | 3% |
| OVERHANG | 15,258 | 5% | · | · | 10% | · | 62% | 23% |
| SLOT_CB | 161,374 | 9% | 1% | · | 6% | · | 15% | 69% |
| BOUNDARY_CB | 307,169 | 79% | 2% | · | 3% | · | 10% | 5% |
| BOX_SAFETY | 42,956 | 2% | 53% | 6% | · | · | 10% | 29% |
| DEEP_HALF | 124,813 | 5% | 10% | 80% | · | · | · | 5% |
| DEEP_MIDDLE | 74,443 | · | 5% | 93% | · | · | · | 2% |

- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **82.1%** on 1,638,690

**NGS ngs_position → family**

| rule role | n | BOUNDARY_CB | BOX_SAFETY | DEEP_SAFETY | EDGE | INTERIOR_DL | OFF_BALL_LB | SLOT_CB |
|---|---|---|---|---|---|---|---|---|
| EDGE | 307,379 | 1% | · | · | 95% | 2% | · | 1% |
| INTERIOR_DL | 332,226 | · | · | · | 4% | 96% | · | · |
| OFF_BALL_LB | 261,404 | 1% | · | · | 2% | 4% | 92% | 1% |
| OVERHANG | 15,039 | 22% | · | · | 9% | · | 40% | 29% |
| SLOT_CB | 159,182 | 9% | · | 2% | 6% | · | 18% | 64% |
| BOUNDARY_CB | 303,338 | 85% | · | 2% | 3% | · | 5% | 5% |
| BOX_SAFETY | 42,365 | 4% | 5% | 55% | · | · | 16% | 20% |
| DEEP_HALF | 123,211 | 5% | 1% | 91% | · | · | · | 2% |
| DEEP_MIDDLE | 73,485 | · | · | 99% | · | · | · | · |

- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **87.1%** on 1,617,629


## 5 · bite at 2 s by rule role (yards; negative = toward the line)

| rule role | n | pass: median bite | pass: IQR | run: median bite | ground covered 2 s (median) |
|---|---|---|---|---|---|
| EDGE | 330,811 | -5.1 | -6.5…-3.2 | -1.4 | 4.8 |
| INTERIOR_DL | 371,406 | -3.7 | -4.6…-2.4 | -0.5 | 3.6 |
| OFF_BALL_LB | 280,750 | -0.0 | -2.0…+1.6 | -1.9 | 3.4 |
| OVERHANG | 17,421 | +0.1 | -2.5…+1.8 | -1.1 | 3.7 |
| SLOT_CB | 161,384 | +1.7 | +0.2…+3.0 | -0.5 | 3.6 |
| BOUNDARY_CB | 307,472 | +2.9 | +1.3…+4.2 | +0.8 | 3.6 |
| BOX_SAFETY | 44,018 | +1.5 | -0.2…+3.7 | -1.4 | 3.5 |
| DEEP_HALF | 124,831 | +2.9 | +0.9…+4.4 | +0.3 | 3.6 |
| DEEP_MIDDLE | 74,515 | +3.1 | +1.6…+4.3 | +0.5 | 3.4 |

## 6 · depth by rule role (yards from the snapper)

| rule role | n | depth p5 | median | p95 | |lateral| median |
|---|---|---|---|---|---|
| EDGE | 330,831 | 0.8 | 1.2 | 1.8 | 5.6 |
| INTERIOR_DL | 371,412 | 0.9 | 1.3 | 1.8 | 2.0 |
| OFF_BALL_LB | 280,754 | 2.3 | 4.8 | 6.2 | 2.2 |
| OVERHANG | 17,422 | 2.1 | 4.1 | 5.7 | 6.5 |
| SLOT_CB | 161,385 | 1.4 | 4.2 | 7.3 | 8.8 |
| BOUNDARY_CB | 307,485 | 1.3 | 5.0 | 9.0 | 11.7 |
| BOX_SAFETY | 44,018 | 6.8 | 8.6 | 9.9 | 5.3 |
| DEEP_HALF | 124,832 | 10.3 | 12.9 | 17.8 | 6.5 |
| DEEP_MIDDLE | 74,517 | 10.5 | 13.9 | 18.0 | 3.4 |
- defenders standardised BEHIND the line at the snap (depth < −0.5): 1,239 (0.1%) — a few are real (a corner over a stacked release), many would mean a flipped play
