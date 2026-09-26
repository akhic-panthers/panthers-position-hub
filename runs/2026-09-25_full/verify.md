# verify · out

1,618,666 defender-snaps · 147,172 plays · 1139 games · seasons [2022, 2023, 2024, 2025]

## 1 · the standardized frame, checked against the league's own numbers

- plays: 147,172; ball proxy = tagged center on 90.6%, offensive-line median on 0.0% (no player tagged C at the snap)
- **direction rule vs NGS Play_Direction: 99.9% agree** on 147,148 plays
  - disagreements by ball proxy: center 89, ol_middle 2
- ball vs center proxy (n=133,360): along-field offset median +0.00 yd (IQR -0.00…+0.00), lateral median +0.00 yd (IQR -0.00…+0.00); |along| > 1.5 yd on 0.1%
- ball vs ol_middle proxy (n=13,781): along-field offset median -0.00 yd (IQR -0.00…+0.00), lateral median +0.00 yd (IQR -0.00…+0.00); |along| > 1.5 yd on 0.1%
- ball vs ol_median proxy (n=1): along-field offset median +0.58 yd (IQR +0.58…+0.58), lateral median -2.39 yd (IQR -2.39…-2.39); |along| > 1.5 yd on 0.0%
- our depth (from the snapper) minus NGS depth_from_los_at_snap: median +0.63 yd, IQR +0.43…+0.85, |diff| > 2 yd on 0.2% of 1,617,497 defender-snaps (expected: a constant ≈ +0.5–0.8, the snapper's body behind the ball)
- join identity: distance between our raw snap position and NGS x_at_snap/y_at_snap — median 0.00 yd, > 1 yd on 0.0% (a snap-frame disagreement of one or two frames, not a wrong player, if small)

## 2 · events

- plays with a snap event that reached this table: 147,172 (plays without `ball_snap`/`snap_direct` never get a row; see the features log for the play spine)
- line_set before the snap: 97.5% of plays
- pass_forward: 53.5% of plays
- handoff: 35.4% of plays
- an end event: 98.6% of plays
- PFF pass plays with a pass_forward event: 87.6% of 89,682 (sacks, scrambles and throwaways legitimately lack one)
- PFF run plays with a handoff event: 89.8% of 57,490 (QB keepers and direct snaps lack one)
- frames after the snap: median 93, < 20 (no 2 s window) on 0.0%

## 3 · the join spine (game_key, gsis_play_id, nfl_id)

| season | defender-snaps | → pffdefense | pass snaps → coverage_defense | → NGS player_play |
|---|---|---|---|---|
| 2022 | 403,616 | 100.0% | 99.8% | 99.9% |
| 2023 | 410,236 | 100.0% | 99.8% | 99.9% |
| 2024 | 406,756 | 100.0% | 99.2% | 99.9% |
| 2025 | 398,058 | 100.0% | 98.6% | 100.0% |
- defender-snaps without a pffdefense row: 109; by NGS position: DT 15, DE 14, WR 14, ILB 12, FS 11, CB 11
  - on 98 plays; plays where ALL our defenders miss (PFF has no defense rows for the play, e.g. a penalty no-play): 0
- defenders per play in tracking: 11 on 99.8%, 10 or fewer on 0.2%, 12+ on 0.0%

## 4 · rule alignment role × charted labels (row %, n)

**PFF alignment family (`pff_POSITION` → family)**

| rule role | n | BOUNDARY_CB | BOX_SAFETY | DEEP_SAFETY | EDGE | INTERIOR_DL | OFF_BALL_LB | SLOT_CB |
|---|---|---|---|---|---|---|---|---|
| EDGE | 307,527 | 1% | · | · | 98% | · | · | 1% |
| INTERIOR_DL | 332,364 | · | · | · | 25% | 70% | 5% | · |
| OFF_BALL_LB | 261,527 | · | · | · | 2% | 1% | 93% | 3% |
| OVERHANG | 15,040 | 5% | · | · | 10% | · | 62% | 23% |
| SLOT_CB | 159,289 | 9% | 1% | · | 6% | · | 15% | 69% |
| BOUNDARY_CB | 303,498 | 79% | 2% | · | 3% | · | 10% | 5% |
| BOX_SAFETY | 42,368 | 2% | 53% | 6% | · | · | 10% | 29% |
| DEEP_HALF | 123,273 | 5% | 10% | 80% | · | · | · | 5% |
| DEEP_MIDDLE | 73,518 | · | 5% | 93% | · | · | · | 2% |

- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **82.1%** on 1,618,404

**NGS ngs_position → family**

| rule role | n | BOUNDARY_CB | BOX_SAFETY | DEEP_SAFETY | EDGE | INTERIOR_DL | OFF_BALL_LB | SLOT_CB |
|---|---|---|---|---|---|---|---|---|
| EDGE | 307,340 | 1% | · | · | 95% | 2% | · | 1% |
| INTERIOR_DL | 332,179 | · | · | · | 4% | 96% | · | · |
| OFF_BALL_LB | 261,370 | 1% | · | · | 2% | 4% | 92% | 1% |
| OVERHANG | 15,035 | 22% | · | · | 9% | · | 40% | 29% |
| SLOT_CB | 159,165 | 9% | · | 2% | 6% | · | 18% | 64% |
| BOUNDARY_CB | 303,314 | 85% | · | 2% | 3% | · | 5% | 5% |
| BOX_SAFETY | 42,358 | 4% | 5% | 55% | · | · | 16% | 20% |
| DEEP_HALF | 123,205 | 5% | 1% | 91% | · | · | · | 2% |
| DEEP_MIDDLE | 73,475 | · | · | 99% | · | · | · | · |

- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **87.1%** on 1,617,441


## 5 · bite at 2 s by rule role (yards; negative = toward the line)

| rule role | n | pass: median bite | pass: IQR | run: median bite | ground covered 2 s (median) |
|---|---|---|---|---|---|
| EDGE | 307,578 | -5.1 | -6.5…-3.2 | -1.4 | 4.8 |
| INTERIOR_DL | 332,449 | -3.7 | -4.6…-2.4 | -0.5 | 3.8 |
| OFF_BALL_LB | 261,563 | -0.0 | -2.0…+1.6 | -1.9 | 3.6 |
| OVERHANG | 15,042 | +0.1 | -2.5…+1.8 | -1.1 | 3.8 |
| SLOT_CB | 159,289 | +1.7 | +0.2…+3.0 | -0.5 | 3.6 |
| BOUNDARY_CB | 303,518 | +2.9 | +1.3…+4.2 | +0.8 | 3.6 |
| BOX_SAFETY | 42,378 | +1.5 | -0.2…+3.7 | -1.4 | 3.6 |
| DEEP_HALF | 123,290 | +2.9 | +0.9…+4.4 | +0.3 | 3.6 |
| DEEP_MIDDLE | 73,524 | +3.1 | +1.6…+4.3 | +0.5 | 3.4 |

## 6 · depth by rule role (yards from the snapper)

| rule role | n | depth p5 | median | p95 | |lateral| median |
|---|---|---|---|---|---|
| EDGE | 307,595 | 0.8 | 1.2 | 1.7 | 5.6 |
| INTERIOR_DL | 332,452 | 0.9 | 1.3 | 1.8 | 2.0 |
| OFF_BALL_LB | 261,564 | 2.5 | 4.8 | 6.2 | 2.2 |
| OVERHANG | 15,043 | 2.2 | 4.2 | 5.8 | 6.4 |
| SLOT_CB | 159,290 | 1.4 | 4.2 | 7.3 | 8.8 |
| BOUNDARY_CB | 303,528 | 1.3 | 5.0 | 9.0 | 11.7 |
| BOX_SAFETY | 42,378 | 6.9 | 8.7 | 9.9 | 5.3 |
| DEEP_HALF | 123,291 | 10.3 | 12.9 | 17.8 | 6.5 |
| DEEP_MIDDLE | 73,525 | 10.5 | 13.9 | 18.0 | 3.4 |
- defenders standardised BEHIND the line at the snap (depth < −0.5): 1,115 (0.1%) — a few are real (a corner over a stacked release), many would mean a flipped play
