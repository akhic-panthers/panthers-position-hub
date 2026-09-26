# Offense in the Player Room — first run, 2022–2025

**Bottom line.** Receivers, tight ends and backs now have a Player Room:
- a role mix read from the tracking (wide, slot, flexed inside, tight end, H-back, tailback)
- PFF's route tree, and the tracked path of every route in its first three seconds
- targets and carries on film
- who covered him, read by the v2 job of the defender PFF charted on him
- whom he blocked, from PFF's blocking chart

The offensive role model clears four of its five registered gates. The fifth is a finding: about half of an offensive
player's stable role mix is his offense's personnel and formation usage, not him.

Everything is descriptive: shares, route mix and target rate rate usage, not play.

## Gates (registered in `docs/REGISTERED_offense_roles_v1.md` before the fit)

| gate | result | bar | verdict |
|---|---|---|---|
| O1 held-out games, vs PFF's charted slot | 0.904 | 0.811 (the old rule scored 0.791) | GO |
| O1 destruction, labels shuffled within game | 0.413 | ≤ majority 0.413 + 0.02 | GO |
| O2 calibration error | 0.004 | ≤ 0.05 | GO |
| O3 mix repeats, even vs odd games | 0.972 | ≥ 0.70 | GO |
| O4 same, role vectors shuffled across the offense within the play | 0.533 | < 0.486 | **NO-GO** |

Per-role split-half r: wide 0.99, slot 0.93, flexed inside 0.85, tight end 0.99, H-back 0.96, tailback 1.00.

**What the NO-GO means.** Shuffling roles across the five skill players on the same play still leaves 0.53 of the
0.97 repeat. A receiver's mix is stable partly because his offense lines up the same way week to week (how much 11,
12 and 21 personnel it uses, and where it puts its tight end). The mix still separates players: the shuffled null
is half the real value. But it has to be read beside his offense's formations, and the Player Room says so.

## Defects and corrections found on the way

1. **The offensive rule's fold was wrong.** PFF's TE-i and TE-o are two tight ends on one side, and PFF's
   "inside slot" (SLiWR/SRiWR) is usually a flexed tight end. That explains most of the old rule's 84.3% NO-GO.
2. **The geometric on-the-line cut called 98% of wide receivers X.** X vs Z and wing vs attached now come from PFF's
   own charted on-the-line flag. PFF charts the outer tight end of a two-TE side off the line 86% of the time, which
   corrects a description in the registration, recorded there.
3. **Team and opponent showed as NGS team ids.** Now NFL codes.
4. **Running backs' "routes" included PFF's pass-block assignments.** These are now counted as "Stayed in to block".

Motion is labelled from PFF's shift-and-motion key: motion at the snap vs a shift, across the formation, and out of or
into the backfield. PFF's motion-type letters (M, I, J, G, H) are not defined in its guide and are not shown.

## Readings (2024–2025)

| player | season | where he lined up | note |
|---|---|---|---|
| Tetairoa McMillan (CAR) | 2025 | 87% wide · 9% slot | 86% of his wide snaps on the line (an X); 21% of routes targeted |
| Xavier Legette (CAR) | 2025 | 73% wide · 18% slot · 6% flexed | |
| Ja'Tavion Sanders (CAR) | 2025 | 45% tight end · 23% flexed · 17% wide · 14% slot | 16% motion or shift |
| Chuba Hubbard (CAR) | 2025 | 83% tailback · 9% wide · 6% H-back | flares and flats; stays in to block on about a tenth of pass snaps |
| Travis Kelce (KC) | 2024 | 38% tight end · 27% wide · 19% slot · 12% flexed | covered most by off-ball linebackers, then slot corners |
| George Kittle (SF) | 2024 | 66% tight end · 14% slot · 10% wide | 59% of his tight end snaps off the line as a wing |
| Kyle Juszczyk (SF) | 2024 | all six jobs | 52% motion or shift |
| Puka Nacua (LA) | 2025 | 62% wide · 22% slot · 11% tight end | 34% of routes targeted; X only 43% of wide snaps |
| Amon-Ra St. Brown (DET) | 2024 | 58% wide · 27% slot | covered almost evenly by boundary corners, slot corners and backers |
