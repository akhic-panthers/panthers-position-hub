# Role taxonomy (registered, v1)

Two axes. Left and right are folded (the mirror image of a job is the same job).

## Axis 1 — alignment role, from geometry at the snap

| role | rule (yards, standardized frame) | PFF slots that usually map here |
|---|---|---|
| EDGE | depth ≤ 2.0 and outside the tackle (+1.5) | LEO REO LE RE DLE DRE LOLB ROLB |
| INTERIOR_DL | depth ≤ 2.0 inside the tackles | DLT DRT NT NLT NRT |
| OFF_BALL_LB | 2 < depth ≤ 7, inside the tackles' width | MLB LILB RILB LLB RLB |
| OVERHANG | 2 < depth ≤ 7, outside the tackle, not over a detached receiver | LOLB/ROLB (off the line), SS walked down, SCB over a wing |
| SLOT_CB | depth ≤ 8, outside the tackle, over a **detached** #2/#3 within 3.5 laterally | SCBL SCBR SCBiL SCBiR SCBoL SCBoR |
| BOUNDARY_CB | outside the tackle, over #1 within 4.0 laterally | LCB RCB |
| BOX_SAFETY | 6 ≤ depth < 10, not over a receiver | SS SSL SSR |
| DEEP_HALF | depth ≥ 10 with ≥ 2 deep defenders, off the middle | FSL FSR SSL SSR (two-high) |
| DEEP_MIDDLE | depth ≥ 10 as the lone deep defender, or the middle of three | FS |

Depth is measured from the **snapper** (NGS has no ball); the ball is ≈ 0.5 yd in front of him, which is why the on-line threshold is 2.0 and not 1.5.

The rule is the seed and the fallback. The **model's probability vector is the product**: trained on snaps where the rule and PFF's charted family agree, scored on all snaps. Disagreements are the interesting snaps and they get a soft answer.

## Axis 2 — responsibility, from PFF charting on pass plays and geometry elsewhere

| class | coverage_defense.assignment | geometric fallback |
|---|---|---|
| RUSH | PRE | crossed the line by 2 s |
| RUN_FIT | — (run plays are not charted here) | handoff play, no throw |
| MAN | MAN | stays within 4.5 yd of the receiver he aligned over while moving ≥ 3 yd |
| MAN_MATCH | any zone assignment with modifier MAT / SEA / CAR / TAM | — (not recoverable from geometry at v1) |
| UNDER_ZONE | HOL CFL CFR HCL HCR FL FR | otherwise, shallower than 11 yd at 2 s |
| DEEP_ZONE | 3L 3M 3R DF 4IL 4IR 4OL 4OR 2L 2R | ≥ 11 yd at 2 s and gaining depth |

A **charted rep is the truth** and is one-hot in the output. The model fills uncharted pass snaps. MAN_MATCH is kept separate from MAN on purpose: the call was zone, the rep was man, and a coach reads those as different things.

## Player-season output
- `share_<ROLE>`: mean probability over snaps (soft). `hard_share_<ROLE>`: share of snaps where ROLE was most likely. The gap = how ambiguous his alignments were.
- `resp_<CLASS>`: responsibility shares.
- `align_entropy`: 0 = one job every snap.
- `mean_depth`, `box_rate`, `mean_bite_2s`, `mean_ground_covered_2s`.
- `pct_<col>`: percentile within `peer_group × season` among players with ≥ 200 snaps. **More of the job than peers, not better at it.**

## Peer groups
NGS/roster position → EDGE (DE OLB), IDL (DT NT), LB (LB ILB MLB), CB, S (S SS FS), DB (fallback).

## What v2 would add (not registered)
Offensive alignment roles (X / Z / slot / wing / inline TE / backfield); a MAN_MATCH detector from post-snap geometry; play-action-specific bite over expected (BDUE) and run-flow over expected (GCOE) as per-play descriptors; a "rehearsed role" axis from practice GPS if OpenField is in scope.
