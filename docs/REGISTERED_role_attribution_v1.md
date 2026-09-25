# REGISTERED — positional role attribution v1

Gates committed before any real snap is scored. Filled in the sister project's required-block form
(`evaluation/REQUIRED_BLOCK.md`). A NO-GO is a shippable finding.

```
claim:               a defender's per-snap alignment role and responsibility can be read from NGS
                     geometry well enough that his season ROLE MIX is a stable, rankable rating
baseline:            PFF's single charted label per snap (pff_POSITION → family) and per season
                     (pff_GAMEPOSITION); a "mix" from PFF alone is the share of snaps per charted slot
ceiling:             the charted label itself, on the snaps where charter and geometry agree —
                     construction: agreement rate of rule vs PFF family (an upper bound on what a
                     model trained on that consensus can be asked to reproduce)
containment check:   [ ] ceiling ≥ every model number on the same held-out games (arithmetic tripwire:
                     if the model "beats" its own label source, the label source is wrong, stop)
bar:                 G1 ≥ 0.80 · G2 alignment ≥ majority + 0.15 on held-out GAMES · G2 responsibility
                     ≥ majority + 0.15 on charted held-out pass snaps · G3 split-half median r ≥ 0.70
                     (players ≥ 100 snaps) · G4 destruction null < 0.5 × G3
destruction control: within-play shuffle of the role vectors across the eleven defenders (play kept,
                     identity broken) — G3 must collapse; a G3 that survives it was team/formation
population:          tracking 2022–2025 ∩ pffdefense ∩ coverage_defense (2019+) ⇒ 2022–2025;
                     preseason excluded; 2024 wk 2 + postseason absent at source; holdout = the last
                     two regular-season weeks of each season, by game
```

## Gates

| id | question | construction | bar |
|---|---|---|---|
| G1 | does the geometry mean what the charter means? | top-1 alignment role vs PFF alignment family, safety depth classes folded | ≥ 0.80 agreement (sanity; below it, re-read the taxonomy before anything else) |
| G2a | does the alignment model generalise? | accuracy on held-out games vs the consensus label | ≥ majority class + 0.15 |
| G2b | does the responsibility model generalise? | accuracy on held-out charted pass snaps vs `coverage_defense` | ≥ majority class + 0.15 |
| G3 | does a man's role mix REPEAT? | even-game vs odd-game player-season shares, median Pearson r over roles that vary | ≥ 0.70 |
| G4 | is the repeat HIS? | G3 on within-play-shuffled vectors | < 0.5 × G3 |

Also reported, not gated: per-role r in G3; the soft-vs-hard share gap distribution; the label coverage of the consensus (share of snaps where rule and PFF agree); how the mix moves between one-high and two-high calls for the same man (a role mix that is entirely explained by the call is a team fact, and the viewer must say so).

## Rules of the run
- Held-out by **game**, never by row. The last two regular-season weeks of each season are never trained on.
- No threshold in `rules.py` is tuned after a gate is read. A change is a v2 registration.
- Real beats generated: the synthetic generator proves plumbing and that the gates can fail; **no synthetic number is ever quoted as a result.**
- Descriptive vs predictive: shares and percentiles ship as **ratings of deployment**. Nothing here is a projection or a grade, and the viewer's copy says so.
- A bug is never a finding.

## Amendment v1.1 — rule defects fixed in Phase 1, BEFORE any gate was read (2026-09-25)
The first two real games (2025 wk 1) were checked against PFF's charted slot and against NGS's own per-snap
defender role (`ngsdb.bronze.player_play.ngs_position`, found by `poshub discover`). Five rule defects were
ordering or mis-applied constants, not new thresholds; each has a planted regression test in
`tests/test_rules_vocab.py` and is written out in the `roles/rules.py` docstring:
press corners read EDGE · 5/6/7-techniques read INTERIOR (the box pad was the on-line edge line) · backers at
6–7 yd in the box read BOX_SAFETY · off corners with inside leverage read BOX_SAFETY · a head-up 0.0 yd became
99 yd. One constant is reused in a new place: the registered 4 yd corner constant as the minimum width outside
the tackle for a corner on the line or an off corner (measured: press corners p5 4.1 yd, on-line edges p90 3.2).
Rule vs PFF family on the smoke games 73% → 86%; vs NGS role 78% → 89%.

Two gate constructions were also defective and are fixed: **G2b scored `resp_role`, which is overwritten by the
charted label where one exists** (the synthetic 1.000 below was that tautology; G2b now scores
`resp_model_role`, the model's own answer), and G2a had no real-data truth column (now the consensus label on
held-out games). The bars are unchanged. After this amendment nothing in `rules.py` moves until a v2 registration.

## Synthetic dry run (plumbing only, 2026-09-25)
Eight synthetic games, 3,960 defender-snaps, safeties designed to swap box/deep jobs on 35% of snaps:
G1 0.969 · G2a 0.946 (majority 0.18) · G2b 1.000 · G3 0.999 · G4 −0.06. The designed 65/35 safety
split was recovered. **This proves the code runs and the destruction control bites. It says nothing
about NFL football.** First real run: fill the table below.

| gate | value | bar | n | verdict |
|---|---|---|---|---|
| G1 | | 0.80 | | |
| G2a | | maj + 0.15 | | |
| G2b | | maj + 0.15 | | |
| G3 | | 0.70 | | |
| G4 | | < 0.5 × G3 | | |
