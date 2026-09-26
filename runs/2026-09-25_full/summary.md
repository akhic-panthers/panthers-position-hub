# run summary · out

## features

| season | games | plays | defender-snaps | defenders | PFF alignment joined | charted coverage | pass share | ball proxy = center |
|---|---|---|---|---|---|---|---|---|
| 2022 | 284 | 36,701 | 403,616 | 1,001 | 100.0% | 99.9% | 53.6% | 88.4% |
| 2023 | 285 | 37,298 | 410,236 | 995 | 100.0% | 99.9% | 54.2% | 93.2% |
| 2024 | 285 | 36,983 | 406,756 | 1,011 | 100.0% | 99.5% | 53.4% | 86.0% |
| 2025 | 285 | 36,190 | 398,058 | 1,025 | 100.0% | 99.1% | 52.7% | 95.1% |

### rule alignment role × PFF family (row %)

- **BOUNDARY_CB** → BOUNDARY_CB 79%, OFF_BALL_LB 10%, SLOT_CB 5%, EDGE 3%
- **BOX_SAFETY** → BOX_SAFETY 53%, SLOT_CB 29%, OFF_BALL_LB 10%, DEEP_SAFETY 6%
- **DEEP_HALF** → DEEP_SAFETY 80%, BOX_SAFETY 10%, BOUNDARY_CB 5%, SLOT_CB 5%
- **DEEP_MIDDLE** → DEEP_SAFETY 93%, BOX_SAFETY 5%, SLOT_CB 2%, BOUNDARY_CB 0%
- **EDGE** → EDGE 98%, SLOT_CB 1%, BOUNDARY_CB 1%, OFF_BALL_LB 0%
- **INTERIOR_DL** → INTERIOR_DL 70%, EDGE 25%, OFF_BALL_LB 5%, DEEP_SAFETY 0%
- **OFF_BALL_LB** → OFF_BALL_LB 93%, SLOT_CB 3%, EDGE 2%, INTERIOR_DL 1%
- **OVERHANG** → OFF_BALL_LB 62%, SLOT_CB 23%, EDGE 10%, BOUNDARY_CB 5%
- **SLOT_CB** → SLOT_CB 69%, OFF_BALL_LB 15%, BOUNDARY_CB 9%, EDGE 6%

## fit

```
{
  "align_n": 1202164,
  "align_label_coverage": 0.8336759121333921,
  "resp_n": 771335,
  "holdout_games": [
    59078,
    59079,
    59080,
    59081,
    59082,
    59083,
    59084,
    59085,
    59086,
    59087,
    59088,
    59089,
    59090,
    59091,
    59092,
    59094,
    59095,
    59096,
    59097,
    59098,
    59099,
    59100,
    59101,
    59102,
    59103,
    59104,
    59105,
    59106,
    59107,
    59108,
    59109,
    59413,
    59414,
    59415,
    59416,
    59417,
    59418,
    59419,
    59420,
    59421,
    59422,
    59423,
    59424,
    59425,
    59426,
    59427,
    59428,
    59429,
    59430,
    59431,
    59432,
    59433,
    59434,
    59435,
    59436,
    59437,
    59438,
    59439,
    59440,
    59441,
    59442,
    59443,
    59444,
    59748,
    59749,
    59750,
    59751,
    59752,
    59753,
    59754,
    59755,
    59756,
    59757,
    59758,
    59759,
    59760,
    59761,
    59762,
    59763,
    59764,
    59765,
    59766,
    59767,
    59768,
    59769,
    59770,
    59771,
    59772,
    59773,
    59774,
    59775,
    59776,
    59777,
    59778,
    59779,
    60083,
    60084,
    60085,
    60086,
    60087,
    60088,
    60089,
    60090,
    60091,
    60092,
    60093,
    60094,
    60095,
    60096,
    60097,
    60098,
    60099,
    60100,
    60101,
    60102,
    60103,
    60104,
    60105,
    60106,
    60107,
    60108,
    60109,
    60110,
    60111,
    60112,
    60113,
    60114
  ]
}
```

## gates

| gate | value | bar | n | verdict |
|---|---|---|---|---|
| G1_pff_agreement | 0.836 | 0.800 | 1618404 | GO |
| G2a_heldout_alignment | 1.000 | 0.370 | 145919 | VOID |
| G2b_heldout_responsibility | 0.804 | 0.532 | 54830 | GO |
| G3_split_half | 0.963 | 0.700 | 2575 | GO |
| G4_destruction | 0.204 | < 0.5 × real (0.963) | 2575 | GO |

## role mix

2898 player-seasons above the snap floor; by peer group: CB 641, DB 6, EDGE 833, IDL 555, LB 372, S 491

| safety | team | snaps | deep middle | deep half | box | slot | entropy |
|---|---|---|---|---|---|---|---|
| Kam Curl | LA | 1323 | 17% | 49% | 10% | 8% | 1.58 |
| Justin Reid | KC | 1303 | 10% | 39% | 10% | 14% | 1.83 |
| Juan Thornhill | KC | 1236 | 28% | 50% | 10% | 5% | 1.35 |
| Justin Reid | KC | 1234 | 10% | 29% | 17% | 15% | 1.95 |
| Marcus Epps | PHI | 1233 | 24% | 44% | 10% | 8% | 1.55 |
| Camryn Bynum | MIN | 1224 | 27% | 56% | 7% | 4% | 1.21 |
| Talanoa Hufanga | DEN | 1223 | 28% | 26% | 13% | 13% | 1.82 |
| Jaquan Brisker | CHI | 1218 | 11% | 37% | 8% | 11% | 1.83 |
| Kevin Byard | CHI | 1217 | 40% | 38% | 7% | 4% | 1.43 |
| Antoine Winfield | TB | 1216 | 37% | 28% | 9% | 8% | 1.69 |
| Xavier Woods | CAR | 1211 | 22% | 40% | 14% | 6% | 1.65 |
| Quandre Diggs | SEA | 1205 | 41% | 44% | 7% | 3% | 1.23 |
