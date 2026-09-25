"""Viewer export — the JSON the static viewer (viewer/index.html) and the sister app read.

Shape mirrors web/public/dev/pos_boards.json in panthers_projects: {meta, players:[...]} with every
number documented once in `meta.metrics_doc`. Percentiles are within peer group × season. No
composite score: each column answers one question.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ..config import MIN_SNAPS_FOR_MIX, MIN_SNAPS_FOR_PERCENTILE
from ..roles.taxonomy import ALIGN_ROLES, PRIMARY_ROLES_OF_GROUP, RESPONSIBILITIES, ROLE_LABEL

CAVEATS = [
    "Role shares are DESCRIPTIVE: what the tracking says he did on his snaps this season. They are not a grade and not a projection.",
    "Alignment shares are mean probabilities over snaps (soft). Hard shares (argmax) are carried beside them; the gap between the two is the geometric ambiguity of his alignments.",
    "Responsibility on pass snaps is PFF's charted assignment where charted; otherwise the tracking model's estimate. Run snaps are geometric (run fit / rush).",
    "Percentiles are within roster position group and season, among players above the snap floor. A high percentile means MORE of that job than peers, not better at it.",
    f"Players under {MIN_SNAPS_FOR_MIX} snaps are not shown; percentiles need {MIN_SNAPS_FOR_PERCENTILE}.",
    "Left and right are folded: the mirror image of a job is the same job.",
]


def export_viewer_json(mix: pl.DataFrame, out: Path, gates: list[dict] | None = None, source: str = "",
                       team_mix: pl.DataFrame | None = None) -> dict:
    players = []
    for r in mix.iter_rows(named=True):
        align = {role: r.get(f"share_{role}") for role in ALIGN_ROLES if r.get(f"share_{role}") is not None}
        hard = {role: r.get(f"hard_share_{role}") for role in ALIGN_ROLES if r.get(f"hard_share_{role}") is not None}
        resp = {c: r.get(f"resp_{c}") for c in RESPONSIBILITIES if r.get(f"resp_{c}") is not None}
        pct = {k[4:]: v for k, v in r.items() if k.startswith("pct_") and v is not None}
        players.append({
            "nfl_id": r["nfl_id"], "name": r.get("player_name"), "roster_pos": r.get("roster_pos"), "peer_group": r.get("peer_group"),
            "team": r.get("team"), "season": r.get("season"), "snaps": r["snaps"], "pass_snap_share": r.get("pass_snap_share"),
            "primary_role": r.get("primary_role"), "align_entropy": r.get("align_entropy"),
            "mean_depth": r.get("mean_depth"), "box_rate": r.get("box_rate"),
            "mean_bite_2s": r.get("mean_bite_2s"), "mean_ground_covered_2s": r.get("mean_ground_covered_2s"),
            "align": align, "align_hard": hard, "resp": resp, "pct": pct,
        })
    doc = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(), "source": source,
            "attribution": "position-hub v0.1 — positional role attribution from NGS tracking geometry + PFF charting. "
                           "Method after Eager & Seth (2023) for the 2 s post-snap window; role taxonomy registered in docs/.",
            "caveats": CAVEATS,
            "roles": {"align": ALIGN_ROLES, "resp": RESPONSIBILITIES, "labels": ROLE_LABEL, "primary_by_group": PRIMARY_ROLES_OF_GROUP},
            "metrics_doc": {
                "align.<ROLE>": "mean P(alignment role) over his snaps",
                "align_hard.<ROLE>": "share of snaps where ROLE was the most likely alignment",
                "resp.<CLASS>": "share of snaps by responsibility (charted where PFF charted it, else modelled/geometric)",
                "pct.<col>": "percentile within peer_group × season among players ≥ snap floor (100 × share of peers ≤ his value)",
                "align_entropy": "entropy of the alignment mix in nats: 0 = one job every snap",
                "mean_depth": "mean depth off the ball at the snap, yards",
                "box_rate": "share of snaps inside the tackle box (≤ 7 yd, inside the tackles' width + 1.5)",
                "mean_bite_2s": "mean change in depth 2 s after the snap; negative = toward the line (Eager & Seth's bite)",
                "mean_ground_covered_2s": "mean yards moved in the first 2 s",
            },
            "gates": gates or [],
        },
        "players": players,
    }
    if team_mix is not None:
        doc["teams"] = team_mix.to_dicts()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=_json_default))
    return doc


def _json_default(o):
    import math

    if isinstance(o, float) and math.isnan(o):
        return None
    return str(o)
