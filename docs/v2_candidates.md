# v2 candidates — NOT registered, written after the first real run (2026-09-25)

The v1 rules and bars are frozen after the gates were read. Everything below is a lead from reading the four-season
output as a coach would. Each one becomes a v2 registration, with its own gates, before anything in `rules.py` moves.

1. **A defender over a tight #1 is read as a boundary corner.** 8% of safety snaps land on BOUNDARY_CB at a median
   4.7 yd deep, 7 yd from the ball, over a #1 who is only a yard and a half away laterally: a tight split, a flexed
   tight end, or a lone receiver on a condensed side. PFF charts most of them LLB/RLB and NGS calls them OLB. That is an
   apex / overhang job. Candidate: a boundary corner must be the widest defender on his side AND outside the numbers
   (sideline distance), or ≥ 4 yd outside the tackle over a receiver who is himself ≥ 8 yd from the ball.
2. **The alignment model is the rule.** Trained on rule ∧ PFF consensus, it reproduces the rule on 98.9% of held-out
   snaps and its top probability is ≥ 0.9 on 98.8% of snaps, so the "soft" position field is a hard count. Candidate:
   train on the charted labels directly (PFF slot family, with NGS's `ngs_position` as a second labeller) so the model
   is free to disagree with the rule, then register G2a as held-out agreement with the label it did NOT train on.
3. **PFF charts 4-technique ends as LE/RE (EDGE family); geometry and NGS both say interior.** 25% of rule-INTERIOR
   snaps are PFF EDGE; NGS agrees with the rule on 96%. Candidate: fold PFF LE/RE by their technique, or accept NGS as the
   check label for the defensive line.
4. **WING in the offensive rule (E4 NO-GO at 84.3% vs 0.85).** Rule WING lands 41% on PFF inline TE and 34% on PFF slot.
   PFF's TE-o/TE-i slots are not the wing we defined. Candidate: learn the offensive fold from `ngsdb.bronze.player_play`
   (`receiver_location_type`) before writing a rule.
5. **The ball.** `ngsdb.bronze.ball_position_data` is a real ball track. The snapper proxy measured 0.00 yd from NGS's
   ball at the snap, so depth changes nothing today, but the throw target and ball-carrier identity on RPOs would.
