# Position hub — first real run, 2022–2025

**Bottom line.** The role mix is real, stable, and the player's own. It reproduces 0.96 split-half, the within-play
shuffle drops that to 0.20, and the call explains 1% of a safety's alignment. Three of the four scoring gates are GO. The
fourth, G2a, is void: the alignment model is a copy of the geometric rule, so v1's "position field" is a count of
per-snap roles, not a soft probability. Bite and ground covered over expected rebuild the paper's numbers. Disguise
and zone-match are recoverable from tracking. Offensive roles missed their bar by 0.7 points.

Everything is descriptive: shares and percentiles rate deployment, not play. Nothing here is a grade or a projection.

## Population

| season | games | run + pass plays | defender-snaps | defenders |
|---|---|---|---|---|
| 2022 | 284 | 36,701 | 403,616 | 1,001 |
| 2023 | 285 | 37,298 | 410,236 | 995 |
| 2024 | 285 | 36,983 | 406,756 | 1,011 |
| 2025 | 285 | 36,190 | 398,058 | 1,025 |
| total | 1,139 | 147,172 | 1,618,666 | |

Tracking has 2024 without week 2 and without the postseason, at source. Of 1,140 game files queued, one produced no snap.

## Joins and the frame

| check | result |
|---|---|
| PFF run + pass plays with a tracked snap | 98.8% (1,719 plays have no `ball_snap` in the frames) |
| defender-snaps → `pffdefense` | 100.0% |
| pass snaps with a charted responsibility | 98.6–99.8% by season (61% from `coverage_defense`, the rest rushers from `pff_ROLE`) |
| defender-snaps → NGS play-level (`ngsdb.bronze.player_play`) | 99.9% |
| our direction of play vs NGS `Play_Direction` | 99.9% agree (97 of 148,867 plays differ) |
| snapper proxy vs NGS ball at the snap | 0.00 yd median, off by > 1.5 yd on 0.1% |
| our depth vs NGS depth from the line | a constant +0.63 yd (the snapper's body), > 2 yd off on 0.2% |
| defenders behind the line at the snap | 0.1% |

**NGS is in Unity Catalog.** `poshub discover` found `ngsdb.bronze.player_position` (frame tracking, 2016–2026),
`ngsdb.bronze.ball_position_data` (a real ball track) and `ngsdb.bronze.player_play`. That last one is the 108-column
play-level product, with NGS's own per-snap defender role. That answers the brief's open questions 1 and 2. The
play-level table became the independent check for this run.

## Defects found and fixed (each re-run, none presented as a finding)

1. `get_source` required a warehouse path, so a logged-in Mac silently read the local export.
2. `pff_PLAYACTION`, `pff_BLITZDOG` and `pff_RUNPASSOPTION` are 0/1 integers in bronze, and `== 'Y'` raised on them.
3. With no player tagged at center (5–14% of plays), the offensive-line coordinate median sat 0.43 yd behind the ball. The middle lineman is the snapper, now 0.00 yd off.
4. Five alignment-rule defects, fixed before any gate was read (v1.1 amendment, each with a planted test):
   - a press corner read as an edge
   - 5-, 6- and 7-techniques read as interior
   - a backer at 6–7 yd in the box read as a box safety
   - an off corner with inside leverage read as a box safety
   - a head-up 0.0 yd became 99 yd
   - Rule agreement with PFF went from 73% to 86%, and with NGS from 78% to 89%.
5. G2b scored the column that is overwritten with the charted label. The synthetic "1.000" was that tautology.
6. `coverage_defense` never charts the rush. Rush and run-fit truth now come from `pffdefense.pff_ROLE`.
7. Penalties, no-plays, kneels and spikes were in the population (5.5% of tracked plays), and corners read 4% "pass rush" on them. Now run and pass plays only. The pre-fix gates are in `prefix/`.
8. The E2 destruction control, as registered, could not pass by construction. Amended on the 2-game plumbing run, before the population run.
9. Workers oversubscribed Polars threads: load average 220 and 636 minutes of system time on a 272-minute build. Now one thread per worker.

## Registered gates

| gate | value | bar | verdict |
|---|---|---|---|
| G1 geometry agrees with PFF's charted slot | 0.836 | 0.80 | GO |
| G2a alignment on held-out games | 1.000 | 0.52 | **VOID** |
| G2b responsibility on held-out charted pass snaps | 0.804 | 0.532 | GO |
| G3 role mix repeats, even vs odd games | 0.963 | 0.70 | GO |
| G4 same, defenders shuffled within the play | 0.204 | < 0.48 | GO |

Consensus label coverage is 83.4%. Per-role split-half r ranges from 0.91 to 0.99, except overhang at 0.67, a class with
almost nobody in it. The soft-vs-hard share gap is 0.1% median, 0.3% at p90.

**Why G2a is void.** The training label is the rule wherever PFF agrees, and the rule is a function of the same
features, so the model reproduces it on unseen games at 1.000. On held-out games it matches the rule on 98.6% of snaps.
Against labels it never saw, it gains about one point: PFF slot 0.814 to 0.826, NGS role 0.865 to 0.869. The
probabilities are effectively hard. The mix is honest as a count of what he lined up as, snap by snap. The "8.5 yards,
55% box / 30% deep" soft answer is not what v1 delivers, and the viewer copy no longer implies it.

## Ten readings, as a coach would check them

1. **Kyle Hamilton (BAL).** 2024 was 26% deep half, 23% slot, 15% off-ball, 10% box and 10% deep middle. In 2025 he was 29% slot, 17% off-ball, 14% on the edge and 13% deep half. His job count (entropy 1.96) is the highest of any safety we read: a true position-less defender who moved closer to the ball in 2025.
2. **Minkah Fitzpatrick.** In Pittsburgh in 2024 he was a post safety, 46% deep middle. In Miami in 2025 he was 38% slot and 20% deep middle. The FS label never changed; the job did.
3. **Jalen Ramsey.** In Miami in 2024 he was 74% boundary corner. In Pittsburgh in 2025 he was 26% slot, 21% deep middle, 21% boundary and 20% deep half. That is a corner turned into a four-job defensive back.
4. **Cooper DeJean (PHI).** A 74% nickel as a rookie. In 2025 he was 56% slot and 32% boundary, kicking outside on base downs.
5. **Jalen Pitre (HOU) and Nick Emmanwori (SEA).** Listed at safety, they are nickels: Pitre 62–65% slot, Emmanwori 50% as a rookie. Derwin James is 38% slot and 11% on the edge.
6. **Jessie Bates (ATL).** In 2024 he was 56% deep half. In 2025 he was 25% deep half, 24% deep middle and 22% box, the fourth-highest box share among safeties. Atlanta rotated him down with Xavier Watts beside him.
7. **Nick Scott (CAR, 2025).** 51% deep half and 29% deep middle. He is deep on 76% of one-high calls and 89% of two-high calls, making him the Panthers' half-field and post safety. Lathan Ransom is 69% deep half.
8. **Tre'von Moehrig (CAR, 2025).** Listed SS, he read 25% slot, 21% deep half, 16% boundary, 13% off-ball LB and 12% box. His entropy (1.92) is the same as Hamilton's, with depth at the 12th percentile and box at the 90th among safeties. The "16% boundary" is partly the v2 lead below: he stands over a tight #1 in condensed sets, which is an apex job, not a corner.
9. **Chau Smith-Wade (CAR).** 51% slot, 18% boundary and 15% deep half in 2025: a nickel who rotates to a half-field. In 2024 he was 16% box.
10. **Carolina's outside corners.** Mike Jackson is 93% boundary and Jaycee Horn 90%, both pure boundary corners. Horn plays man on 15–20% of his snaps against Jackson's 11–13%.

Leaders pass the smell test.

- **Deep middle, 2025:** Ronnie Hickman Jr., Camryn Bynum, Thomas Harper, Calen Bullock and Kevin Byard.
- **Slot corner, 2025:** Upton Stout, Ja'Quan McMillian, Andru Phillips, Taron Johnson and Kenny Moore II.
- **Box safety, 2025:** Budda Baker, Jaden Hicks, Jordan Poyer and Jessie Bates.

## Extensions (registered in `docs/REGISTERED_phase3_extensions.md` before they ran)

| extension | result | paper or bar | verdict |
|---|---|---|---|
| GCOE, backers and strong safeties by PFF slot | RMSE 2.29 vs null 3.22; year-to-year 0.42 (n 121) | 2.47 vs 3.76; 0.66 | GO |
| BDUE, same population | RMSE 2.29 vs null 2.63; year-to-year 0.58 (n 133) | 2.23 vs 2.96; 0.57 | GO |
| GCOE × BDUE within season | −0.53 (n 234) | −0.40 | reported |
| GCOE destruction, shuffled within team-season | 0.19 paper slots (GO); 0.27 tracking roles vs a 0.25 bar (**NO-GO**) | < 0.5 × real | split |
| E2 disguise: shown vs played shell | AUC 0.838; snap shell alone 0.665; everything permuted 0.510 | ≥ 0.70 and baseline + 0.05 | GO |
| E3 zone-match vs spot drop on charted zone calls | AUC 0.880; pre-snap only 0.760; shuffled 0.503 | ≥ 0.70 and baseline + 0.05 | GO |
| E4 offensive roles vs PFF's offensive slot | 84.3% | 0.85 | **NO-GO** |

What these say in football terms:

- **The trade-off holds, and is stronger.** Flowing hard to the run and biting on play action are the same trait at −0.53, versus the paper's −0.40. BDUE repeats as well as the paper found (0.58 vs 0.57).
- **Half of GCOE's repeat is the team.** Across 20 shuffles within team-season, the shuffled year-to-year sits at a median 0.20–0.23 against a real 0.42–0.50. Ground covered over expected is part run fit and part player. It ships per play, never as a season ranking.
- **Disguise is readable.** 27.5% of plays show one shell and play another. The line-set shell plus safety movement in the first 2 seconds identifies them at 0.84.
- **Zone-match is readable, given a zone call.** Tracking separates pattern-matched reps from spot drops at 0.88. This is narrower than man coverage, which the sister project closed. Pre-snap alignment alone already carries 0.76.
- **Offense is close.** X, Z, slot and backfield agree with PFF at 92–97%. Wing is the miss: our wing lands on PFF's inline tight end 41% of the time and on its slot 34%.

## What shipped

- Per-player-season role mix and responsibility mix with peer percentiles, for 2,898 player-seasons (`role_mix.json`).
- The viewer, with the one-high / two-high split per safety.
- A board-shaped file for the sister app, written here and not copied into that repo.
- The NGS play-level check, built into `poshub features`.
- `poshub verify`, `extend` and `report`.
- Per-play GCOE and BDUE descriptors, kept local and not pushed.

## What NO-GO'd, and why

- **G2a** is void by construction (above).
- **E4 offensive roles** missed at 84.3% because of the wing definition.
- **GCOE destruction on tracking roles** missed by 0.02, because half of the repeat is the team.
- **The overhang class** is too narrow to be a job. Linebackers top out at 3% overhang, and apex players read as slot or boundary. This is v2 lead 1.

## Three options for Eric

1. **Ship v1 to the boards now.** The role mix as a deployment rating, with the tight-#1 caveat on safeties and nickels. Stable (0.96), his own (the shuffle drops it to 0.20), and it reads right on Hamilton, Fitzpatrick, Ramsey and DeJean.
2. **Register v2 first (about a week).** Train alignment on PFF's slot with NGS's role as the held-out check, so the per-snap field is actually soft, and fix the apex / overhang definition. This gives the "70% free safety, 20% strong safety" answer a real probability underneath.
3. **Build the game-plan layer instead.** Disguise (0.84) and zone-match (0.88) become per-play opponent tendencies, with GCOE and BDUE as per-play descriptors next to them. Answering "how late does this safety rotate, and does their nickel match or spot-drop" is closer to what coaches use weekly than a season mix.
