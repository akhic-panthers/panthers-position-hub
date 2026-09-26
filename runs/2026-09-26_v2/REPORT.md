# Position hub v2: the charter's call, the film, and the field

**Bottom line.** v2 does what v1 could not: every snap now carries a real probability of how a PFF charter would call
it, learned from where the man stood. It clears all seven registered gates. Every snap on the board opens its film
from Thunder, all five angles, cued to that snap. The Player Room shows four views: the alignment map, a heatmap
against his position, his first two seconds, and a block map from PFF's blocking chart.

Everything is descriptive: shares and percentiles rate deployment, not play.

## v2 gates (registered in `docs/REGISTERED_role_attribution_v2.md` before the fit)

| gate | result | bar | verdict |
|---|---|---|---|
| V1 held-out games, vs PFF's charted slot | 0.942 | rule 0.824 + 0.02 | GO |
| V2 held-out, vs NGS's own role (never trained on) | 0.896 | rule 0.864 − 0.01 | GO |
| V3 calibration error | 0.003 | ≤ 0.05 | GO |
| V4 snaps where the call is genuinely uncertain (top probability < 0.8) | 10.6% | ≥ 5% | GO |
| V1 destruction, labels shuffled within game | 0.219 | ≤ majority 0.205 + 0.02 | GO |
| V5 mix repeats, even vs odd games | 0.977 | ≥ 0.70 | GO |
| V6 same, defenders shuffled within the play | 0.279 | < 0.49 | GO |

The model agrees with NGS at 0.896. PFF's own label agrees with NGS at 0.886, so the model sits 0.010 above its
label source, inside the 0.02 tripwire. It trains on PFF but ends slightly closer to the other labeller, which is what
smoothing out one charter's noise should do.

**What changed from v1.**
- **The label.** It is now PFF's charted slot, folded to eight roles, not the geometric rule.
- **Ends.** PFF's LE and RE are ends lined up inside the tackle, and NGS calls them interior on 98% of snaps, so they now count as interior line.
- **Overhang.** The role is dropped. It was under 3% for every linebacker and the least stable role.
- **Peer groups.** A player listed DE who plays inside is now compared with interior linemen.

## v2 readings

| player | team | season | where he lined up | jobs |
|---|---|---|---|---|
| Tre'von Moehrig | CAR | 2025 | 31% slot · 25% off-ball LB · 19% box · 9% deep half · 9% edge | 1.70 |
| Nick Scott | CAR | 2025 | 41% deep half · 31% post · 16% box · 7% slot | 1.36 |
| Chau Smith-Wade | CAR | 2025 | 57% slot · 15% off-ball LB · 13% deep half · 7% boundary | 1.34 |
| Kyle Hamilton | BAL | 2025 | 30% slot · 29% off-ball LB · 16% edge · 10% deep half | 1.71 |
| Minkah Fitzpatrick | PIT → MIA | 2024 → 2025 | 41% post → 40% slot | 1.53 → 1.69 |
| Jalen Ramsey | MIA → PIT | 2024 → 2025 | 71% boundary → 29% slot · 23% deep half · 16% post · 15% boundary | 0.91 → 1.75 |
| Cooper DeJean | PHI | 2024 → 2025 | 82% slot → 59% slot · 21% boundary | 0.66 → 1.11 |
| Jessie Bates | ATL | 2024 → 2025 | 41% deep half → 25% box · 21% off-ball LB · 19% deep half · 19% post | 1.53 → 1.65 |

**v1's worst misread is gone.** v1 read a defender walked over a tight #1 as a boundary corner (Moehrig 16%). v2 reads
him as the backer PFF charts him as (25% off-ball linebacker), which is the apex job he plays. Listed safeties who
play nickel (Pitre, Emmanwori, Hamilton) now split between slot and off-ball linebacker. That matches PFF's charting,
where a dime backer walked into the box is charted in a linebacker slot.

## Film

Thunder works with the club's login. For every snap on the board:
- The server searches Thunder by the GSIS game key.
- It matches the snap on the play id PFF stores in Thunder (`PFF.pff_GSISPLAYID`, the same id as our tracking).
- It returns signed video links for all five angles (end zone, sideline, broadcast, second end zone, scoreboard) with the snap's start and end time.

Coverage checked on regular-season snaps in every season: 2022 (ATL at CAR, three angles: end zone, sideline, scoreboard), 2023 (IND at NE, five angles), 2024 and 2025 (non-Panthers games and CAR at JAX, five angles). A new game takes about 7 seconds the first time and is cached for 30 minutes after.

**Seek verified.** Headless screenshots render video black, so the build could only check the windows structurally. On 2026-09-26 Akhi opened the film in the app and confirmed it starts at the snap. Seek time = the clip's media start frame ÷ its FPS (59.94).

## Block map

This comes from PFF's blocking chart, 1.96M rows for the 1,139 tracked games. For each defender and season it shows:
- which gap he was assigned
- who blocked him, and how
- double-team, unblocked and looper rates
- for rushers, his first move
- for safeties and backers, his run-support job (force, primary and secondary run support, middle-of-the-field safety)

Every code uses PFF's own definition from their data reference guide. My first draft guessed three of them wrong, and the guide caught it before anything shipped.

## How to open it

```bash
cd ~/panthers-position-hub/web && pnpm install && pnpm dev
```

Open http://localhost:3100. The data under `web/public/ph/` is rebuilt by `poshub export-web` and stays on this Mac
(gitignored, per-snap rows). The Thunder login is read on the server from the repo `.env` and never reaches the browser.
