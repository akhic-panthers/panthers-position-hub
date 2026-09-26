| gate | value | bar | n | verdict |
|---|---|---|---|---|
| O1_heldout_vs_PFF_slot | 0.904 | 0.811 | 79326 | GO |
| O1_null_shuffled_labels | 0.413 | 0.433 | 79326 | GO |
| O2_calibration_ECE | 0.004 | 0.050 | 79326 | GO |
| O3_split_half | 0.972 | 0.700 | 1331 | GO |
| O4_destruction | 0.533 | < 0.5 × 0.972 | 1331 | NO-GO |

- O1_heldout_vs_PFF_slot: E4 rule 0.791; majority 0.413
- O1_null_shuffled_labels: labels shuffled within game, identical fit
- O2_calibration_ECE: top-label, 10 bins
- O3_split_half: per-role: WIDE 0.99, SLOT 0.93, FLEX 0.85, INLINE_TE 0.99, H_BACK 0.96, TAILBACK 1.00
- O4_destruction: role vectors shuffled across the offense within the play
