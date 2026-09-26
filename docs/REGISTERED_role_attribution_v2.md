# REGISTERED — positional role attribution v2 (written 2026-09-26, before any v2 model was fit)

v1 read its position field off a geometric rule, and the model trained on rule ∧ PFF became a copy of the rule
(G2a void; model = rule on 98.6% of held-out snaps; top probability ≥ 0.9 on 98.8%). v2 answers the question v1 could
not: **given where a man stood at the snap, how would a charter have labelled that snap** — a real probability, learned
from PFF's charting, checked against a labeller it never saw (NGS).

## Taxonomy v2 — eight alignment roles (overhang dropped)

OVERHANG is removed as a class: under 3% for every linebacker in v1 and the least stable role (split-half r 0.67).
The label is PFF's charted slot on the snap (`pffdefense.pff_POSITION`), folded:

| v2 role | PFF slots | measured check (2022–2025, before any fit) |
|---|---|---|
| EDGE | LEO REO LOLB ROLB DLE DRE | NGS calls 98–99% of them EDGE |
| INTERIOR_DL | DLT DRT NT NLT NRT **LE RE** | PFF's LE/RE is an end lined up inside the tackle (median 0.46 yd inside his centre); NGS calls it interior 98% |
| OFF_BALL_LB | MLB LILB RILB LLB RLB | NGS MLB / OLB |
| SLOT_CB | SCBL SCBR SCBiL SCBiR SCBoL SCBoR | NGS SLOT_CB |
| BOUNDARY_CB | LCB RCB | NGS CB |
| DEEP_MIDDLE | FS | median 14.0 yd, 2.1 yd off the ball, 1.4 deep defenders on the play |
| DEEP_HALF | FSL FSR | median 13.5 yd, 6.6 yd off the ball, 1.9 deep defenders |
| BOX_SAFETY | SS SSL SSR | median 8–10 yd; 41% of SSL/SSR are ≥ 10 yd, which is exactly the snap a soft answer is for |

Anything else (a handful of special slots, nulls) is unlabelled and not trained on.

## Model

Same classifier family as v1 (histogram gradient boosting), trained on the PFF v2 label on non-holdout games.
**Features are geometry only** — depth, width, receiver leverage, shell count, width rank, pre-snap movement, the same
list as v1. Never PFF context, never roster position, never player identity. Held out: weeks 17–18 of each season,
by game.

## Gates

```
claim:               a geometry-only model reproduces how a charter labels the snap, with probabilities that
                     mean something, and its player-season mix is stable and the player's own
baseline:            the v1.1 rule, folded to the v2 taxonomy (OVERHANG → OFF_BALL_LB)
independent check:   NGS's per-snap role (ngsdb.bronze.player_play.ngs_position), never used in training
ceiling:             PFF v2 label vs NGS family agreement on the same held-out snaps (the label's own agreement
                     with the other labeller). Reported beside the model's; a model that beats it by > 0.02 means the
                     construction is wrong — stop
destruction control: V1 refit on labels shuffled within game → held-out accuracy must fall to ≤ majority + 0.02
population:          as v1 (tracking 2022–2025 ∩ pffdefense ∩ run+pass plays)
```

| id | question | bar |
|---|---|---|
| V1 | does it reproduce the charter on unseen games? | held-out accuracy vs PFF v2 label ≥ rule's accuracy on the same snaps + 0.02 |
| V2 | does it stay honest to the labeller it never saw? | held-out agreement with NGS family ≥ rule's − 0.01 |
| V3 | do the probabilities mean what they say? | held-out top-label expected calibration error ≤ 0.05 (10 bins) |
| V4 | is the field actually soft? | top probability < 0.8 on ≥ 5% of held-out snaps |
| V5 | does the mix repeat? | split-half (even vs odd games) median r ≥ 0.70 |
| V6 | is the repeat his? | within-play shuffle of the vectors → V5 < 0.5 × V5 |
| V1-null | destruction | labels shuffled within game, refit → ≤ majority + 0.02 |

Nothing in `rules.py` changes for v2; the rule is now only the baseline. Responsibility (v1 G2b GO) is unchanged.

## Display amendment (2026-09-26, not gated)
Peer groups for percentiles follow the roster label, except where the roster label is ambiguous between edge and
interior: a DE/OLB whose v2 primary job is INTERIOR_DL is compared with interior linemen, and a DT whose primary job is
EDGE with edges. Found on the first read of the Player Room (Derrick Brown, listed DE, 91% interior, read at the 98th
box percentile against edge rushers).

## Result — filled 2026-09-26 (`runs/2026-09-26_v2/`)

| gate | value | bar | verdict |
|---|---|---|---|
| V1 held-out vs charter | 0.942 | 0.844 | GO |
| V2 held-out vs NGS | 0.896 | 0.854 | GO (ceiling 0.886; model +0.010, inside the 0.02 tripwire) |
| V3 calibration ECE | 0.003 | 0.05 | GO |
| V4 field is soft | 10.6% | 5% | GO |
| V1 null (labels shuffled within game) | 0.219 | 0.225 | GO |
| V5 split-half | 0.977 | 0.70 | GO |
| V6 destruction | 0.279 | < 0.489 | GO |
