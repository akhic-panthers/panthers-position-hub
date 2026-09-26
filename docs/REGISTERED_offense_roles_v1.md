# REGISTERED — offensive role attribution v1 (written 2026-09-26, before any offensive model was fit)

The rule-based offensive roles (E4 in `REGISTERED_phase3_extensions.md`) NO-GO'd at 84.3% against PFF's offensive
slot. Reading PFF's slots against the tracking (before any fit) shows why: the fold was wrong, not the geometry.

| PFF slot | median yd outside the tackle | on the line | what it is |
|---|---|---|---|
| LWR RWR | 8.6 | 88% | the widest receiver |
| SLWR SRWR | 4.9 | 72% | a detached slot |
| SLoWR SRoWR | 8.0 | 89% | the outside man of a stack/bunch pair on a side with two wide |
| SLiWR SRiWR | 3.7 | 65% | an inside slot, often a flexed tight end (NGS lists half of them TE) |
| TE-L TE-R | 1.5 | 75% | the tight end, attached |
| TE-iL TE-iR · TE-oL TE-oR | 1.3 · 2.5 | 88% · 81% | two tight ends on one side: inner and outer. ⚠ corrected below: the outer one is usually a wing |
| FB-L FB-R | −1.2 | 8% | an offset fullback / H-back, half the time off the backfield spot |
| FB | −3.1 | 0% | a fullback in the I |
| HB HB-L HB-R | −3.1 · −0.9 | 0% | the tailback, behind or offset from the quarterback |

## Taxonomy — six roles, the label is PFF's charted slot folded

| role | PFF slots |
|---|---|
| WIDE | LWR RWR SLoWR SRoWR |
| SLOT | SLWR SRWR |
| FLEX | SLiWR SRiWR |
| INLINE_TE | TE-L TE-R TE-iL TE-iR TE-oL TE-oR |
| H_BACK | FB FB-L FB-R FB-oL FB-oR FB-iL FB-iR |
| TAILBACK | HB HB-L HB-R HB-oL HB-oR HB-iL HB-iR |

Two geometric descriptors ride beside the role, never as labels: **on or off the line** (a WIDE off the line is a Z,
on it an X; an INLINE_TE off the line is a wing) and **motion** (lateral change from line set to snap).

## Model and gates

Same classifier family as the defense, geometry at the snap only (depth, width, yards outside the tackle, receiver
number and count on his side, sideline distance, on the line, in the backfield, line-set position and motion). Never
roster position, never identity. Held out: weeks 17–18 of each season, by game.

| id | question | bar |
|---|---|---|
| O1 | reproduces PFF's slot on unseen games | held-out accuracy ≥ the E4 rule folded to this taxonomy + 0.02, and ≥ majority + 0.15 |
| O1-null | destruction | labels shuffled within game, identical fit → ≤ majority + 0.02 |
| O2 | calibrated | held-out top-label ECE ≤ 0.05 |
| O3 | mix repeats | split-half (even vs odd games) median r ≥ 0.70, players ≥ 100 snaps |
| O4 | the repeat is his | within-play shuffle of the vectors across the offense → O3 < 0.5 × O3 |

Everything downstream of the role — routes (PFF's charted route, and the tracked path in the first 3 seconds), who
covered him (the v2 defensive role of his charted `coverage_defense` matchup), what he blocked (PFF's blocking chart) —
is descriptive and not gated. Target share and route mix rate usage, not play.

## Correction (2026-09-26, after the gates were read — a description fix only; no fold, feature or bar changed)

The "on the line" column above came from a geometric cut (within 1.5 yd of the snapper's depth). PFF charts it directly
(`pffoffense.pff_ONLOS`) and disagrees: TE-L/TE-R are on the line 44% of snaps, TE-iL 81%, **TE-oL 14%**, LWR/RWR about
63%. The outer tight end of a two-TE side is usually a wing, so the line "not wings" above was wrong. The fold and the
gates are unchanged (wing is a descriptor, not a role); X vs Z and wing vs attached now read from PFF's flag, because the
geometric cut called 98% of wide receivers X.
