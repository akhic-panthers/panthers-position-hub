# G2a replacement — held-out games (weeks 17–18), what the model adds over the rule

| label (independent of our geometry) | rule top-1 | model top-1 | n |
|---|---|---|---|
| PFF charted slot → family | 0.814 | 0.824 | 178,792 |
| NGS ngs_position → family | 0.865 | 0.870 | 176,548 |

- model = rule on 98.857% of held-out snaps; on the consensus snaps (the registered G2a population) 0.9996
- on the 31,181 held-out snaps where the rule and PFF disagree (never trained on), the model keeps the rule's answer on 93.3%
- max probability per snap: median 1.000, share of snaps with max < 0.9: 1.18%, < 0.6: 0.22%
