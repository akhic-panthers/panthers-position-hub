# REGISTERED — Phase 3 extensions (written 2026-09-25, before any four-season number was read)

Each block is filled before a line of its model is run on the full population. Population for every block:
tracking 2022–2025 ∩ pffplays ∩ pffdefense (`handoff/POPULATION_MAP.md`, seq_v1 row), regular season + postseason
files, preseason excluded, 2024 wk 2 and postseason absent at source. Holdout and CV are **by game or week, never by
row**. Player identity is never a feature. Nothing here is a grade.

---

## E1 · GCOE and BDUE (Eager & Seth 2023), rebuilt on 2022–2025

```
claim:               a context-only model of how far a box player moves in 2 s leaves a per-play residual whose
                     player-season mean repeats year to year (descriptor, NOT a leaderboard)
responses:           GCOE — closed_on_carrier_2s (yards of distance to the ball carrier closed, snap → 2 s), PFF
                     run plays with a handoff. BDUE — bite_2s (depth change snap → 2 s; negative = toward the line),
                     PFF play-action passes. Residual = observed − expected (GCOE + = flowed more; BDUE + = bit less)
box players:         PFF slot on the snap ∈ {MLB, LILB, RILB, LLB, RLB, SS, SSL, SSR} (the paper's population, so
                     the numbers compare), AND a second arm on our tracking roles {OFF_BALL_LB, BOX_SAFETY, OVERHANG}
context features:    depth, lateral, ball-carrier x/y at the snap (GCOE), PFF slot, box count, down, distance,
                     shotgun, run concept, RB direction, dropback type, defensive personnel, blitz, RPO, n_deep
baseline:            null model (mean response) RMSE, by week CV
ceiling:             not a prediction task with a label ceiling; the paper's RMSE (GCOE 2.47 / null 3.76,
                     BDUE 2.23 / null 2.96) is the reference, not a bound
bar:                 E1a model RMSE ≤ 0.90 × null RMSE on held-out weeks (each response)
                     E1b year-to-year r of player-season mean residual ≥ 0.30 (GCOE ≥ 200 run snaps, BDUE ≥ 75 PA snaps)
destruction control: shuffle residuals across players within (season, team) and recompute E1b → must fall below 0.5 × E1b
reported, not gated: the paper's 0.66 / 0.57 year-to-year and −0.40 within-season GCOE×BDUE, side by side
surface:             per-play descriptors with instability stated. No season ranking ships.
```

## E2 · Disguise — shows one shell, plays another

```
claim:               tracking recovers PFF's shown-vs-played middle-of-field call from the safeties' movement
                     between line set and 2 s after the snap
truth:               pff_MOFOCSHOWN ≠ pff_MOFOCPLAYED (membership tests on 'O'/'C', empty string = missing, excluded)
treatment:           n_deep at line set vs at the snap vs at 2 s; the deepest two defenders' depth and width change
baseline:            the snap-only shell (n_deep at the snap) — what the defense looked like when the ball moved
bar:                 E2 AUC of tracking rotation for "shown ≠ played" ≥ 0.70 on held-out games, and ≥ baseline + 0.05
destruction control: permute the rotation feature across plays within game → AUC ≤ 0.55
                     AMENDED 2026-09-25 (smoke plumbing run, 2 games, before the population run): as written the null keeps
                     the snap shell, so it cannot fall below the baseline and the bar could not be met by construction
                     (REQUIRED_BLOCK §3⃞). Gated control: permute ALL features within game → AUC ≤ 0.55. The movement-only
                     permutation is reported beside it and must land within 0.02 of the baseline.
player surface:      share of a safety's snaps where he is the rotating defender (depth change ≥ 3 yd line set → 2 s),
                     split rotated DOWN vs rotated UP, with the median frame the rotation started. Descriptive.
```

## E3 · Zone-match detector — MAN_MATCH from post-snap geometry

```
claim:               on charted zone calls, tracking separates pattern-matched reps (MAT/SEA/CAR/TAM) from spot-drop reps
truth:               coverage_defense: zone assignment; label = modifier ∈ {MAT, SEA, CAR, TAM}
baseline:            pre-snap geometry only (alignment features)
treatment:           baseline + 2 s and throw-time distance to the aligned / nearest receiver, bite, ground covered
bar:                 E3 held-out-game AUC ≥ 0.70 AND ≥ baseline AUC + 0.05
destruction control: label shuffled within game, identical fit → AUC ≤ 0.55
prior:               the sister project closed "man coverage from tracking" as not decision-grade. This is a narrower
                     question (match vs drop GIVEN a zone call); a NO-GO here closes it too.
```

## E4 · Offensive alignment roles

```
roles:               BACKFIELD · INLINE_TE (on the line, ≤ 2 yd outside the tackle) · WING (off the line, ≤ 3 yd outside
                     the tackle) · SLOT (detached, #2/#3) · X (detached #1, on the line) · Z (detached #1, off the line)
truth:               pffoffense.pff_POSITION folded to the same six (e.g. LWR/RWR → X or Z by on/off, SLWR/SRWR → SLOT,
                     TE-L/TE-R → INLINE_TE, TE-oL/TE-oR/TE-iL/TE-iR → WING, HB/FB → BACKFIELD)
bar:                 E4 top-1 agreement ≥ 0.85 with X/Z folded to WIDE (on/off the line is a rule PFF does not chart)
destruction control: none needed for a rule; the agreement table is the check
```

## E5 · Team role mix and shell mix by opponent, by down and distance, conditional on the call

Descriptive tables only; no gate. Floors: ≥ 100 plays per cell. A safety's role mix under one-high vs two-high
calls (`pff_MOFOCPLAYED`) is reported with the share of his mix the call explains
(1 − within-call variance / total variance of his per-snap deep probability). A mix fully explained by the call is a
TEAM fact and the viewer says so.
