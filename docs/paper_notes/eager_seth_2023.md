# Eager & Seth (2023) — *Investigating trade-offs made by American football linebackers using tracking data*

J. Quant. Anal. Sports, doi 10.1515/jqas-2022-0091. Eric's paper (SumerSports). Read from the corrected proof.

## What it does
Two per-play metrics for box players, each "observed − expected" from a context-only model:

| metric | response | plays | window | best model | RMSE |
|---|---|---|---|---|---|
| **GCOE** ground covered over expected | yards moved toward the ball carrier | runs | snap → 2.0 s | XGBoost (depth 3–6, eta 0.20–0.30) | 2.47 yd (null 3.76) |
| **BDUE** bite distance under expected | end-zone-to-end-zone displacement; negative = toward the line | play-action passes | snap → 2.0 s | random forest | 2.23 yd (null 2.96) |

Cross-validation is **by week (22 folds)**, never by row, because rows within a week are dependent. Player identity is never a feature.

## Features (the ones this project reuses)
- **Tracking:** relative x and y of the player at the snap (ball = origin; "a proxy for a player's role" — their words), ball-carrier relative x/y, displacement/ground covered at 2 s. Speed and orientation at the snap were deliberately left out for box players.
- **Charting (PFF):** the player's charted position on the play (MLB, LLB, RLB, LILB, RILB, SS, SSL, SSR only), box count, coverage scheme, dropback type/depth, blitz, run concept, run direction, rusher position, RPO, shotgun/pistol/motion, down/distance/quarter/clock/score, dome/turf/rest, and the offense's season-to-date run-concept mix.
- The **snap-relative x coordinate was the most important feature** in the GCOE model, followed by the ball carrier's depth. Position label mattered for BDUE: strong safeties moved up, inside backers moved back (their Figure 5).

## Findings worth carrying
- Year-to-year: GCOE r = 0.66, BDUE r = 0.57 (min 200 run snaps / 75 play-action snaps). PFF run-stop rate 0.41, PFF ± grade 0.46; play-action pass-breakup rate 0.09, coverage grade 0.04.
- GCOE and BDUE correlate **−0.40** within season: flowing hard to the run and biting on play action are the same trait. "Aggressive vs conservative" is a real axis of box play.
- Team-level: max GCOE against and min BDUE against describe how offenses move linebackers (Carolina 2021 was 2nd in max GCOE against at 1.62).

## What this project takes from it, and what it changes
1. **The 2 s window and the snap-relative frame are adopted as-is** (`FRAMES_AT_2S`, `bite_2s`, `ground_covered_2s`, `closed_on_carrier_2s`).
2. **Their limitation is our question.** They restrict to eight charted positions and note that "some of these position labels might not always necessarily play in the box (strong safeties for example)". PFF's one label per snap is the input they had to trust; here the tracking geometry decides the role per snap and PFF's label is a check, not the truth.
3. **Over-expected numbers are descriptors, not ratings** (house rule). The role MIX is a rating (stable, rankable); GCOE/BDUE-style residuals, when built in phase 2, ship as per-play descriptors with their instability stated.
4. **Week-level (here game-level) cross-validation** is kept for every model and every gate.
