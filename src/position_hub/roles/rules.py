"""Rule roles — the transparent, geometric seed labels.

These are NOT the product. They are (a) the deterministic fallback when no model is fitted, and
(b) half of the consensus label the model trains on (rule ∧ PFF alignment family agree). Every
threshold is in yards and named so a coach can argue with it.
"""
from __future__ import annotations

import polars as pl

from .taxonomy import ALIGN_ROLES

# thresholds (yards) — registered with docs/REGISTERED_role_attribution_v1.md
ON_LINE_DEPTH = 2.0          # depth is measured from the snapper, ~0.5 yd behind the ball
LB_MAX_DEPTH = 7.0
SAFETY_MIN_DEPTH = 6.0
DEEP_MIN_DEPTH = 10.0
SLOT_MAX_DEPTH = 8.0
SLOT_MAX_LAT_TO_REC = 3.5     # within this laterally of a #2/#3 receiver = over him
CB_MAX_LAT_TO_REC = 4.0
DEEP_MIDDLE_MAX_LAT = 6.0     # a lone deep defender within this of the ball is the middle-of-field player


def rule_align_role(r: dict) -> str:
    d = r["depth"]
    lat = abs(r["lateral"])
    outside = bool(r.get("outside_tackle"))
    over = r.get("over_rec_num")
    lat_rec = abs(r.get("lat_to_nearest_rec") or 99.0)
    n_deep = int(r.get("n_deep") or 0)
    if d <= ON_LINE_DEPTH:
        return "EDGE" if outside else "INTERIOR_DL"
    if d >= DEEP_MIN_DEPTH:
        if n_deep <= 1 or lat <= DEEP_MIDDLE_MAX_LAT and n_deep == 3:
            return "DEEP_MIDDLE"
        return "DEEP_HALF" if n_deep >= 2 else "DEEP_MIDDLE"
    # 1.5 < depth < 10
    rec_detached = bool(r.get("nearest_rec_detached", True))
    if over == 1 and lat_rec <= CB_MAX_LAT_TO_REC and outside:
        return "BOUNDARY_CB"
    # a slot corner is OUTSIDE the box over a DETACHED #2/#3; a backer inside the tackles next to an
    # attached tight end is not a slot, whatever his distance to the tight end
    if over is not None and over >= 2 and lat_rec <= SLOT_MAX_LAT_TO_REC and d <= SLOT_MAX_DEPTH and outside and rec_detached:
        return "SLOT_CB"
    if d >= SAFETY_MIN_DEPTH:
        return "BOX_SAFETY"
    if outside:
        return "OVERHANG" if d <= LB_MAX_DEPTH else "BOX_SAFETY"
    return "OFF_BALL_LB" if d <= LB_MAX_DEPTH else "BOX_SAFETY"


def rule_responsibility(r: dict) -> str | None:
    """Geometric responsibility. Used for run plays and as fallback on passes without charting."""
    if r.get("bite_2s") is None:
        return None
    crossed = bool(r.get("crossed_los_2s")) or (r.get("min_depth_to_2s") is not None and r["min_depth_to_2s"] < -0.5)
    if not r.get("has_throw") and r.get("has_handoff"):
        return "RUN_FIT"
    if crossed:
        return "RUSH"
    if r.get("dist_aligned_rec_2s") is not None and r["dist_aligned_rec_2s"] <= 4.5 and r.get("ground_covered_2s", 0) >= 3.0:
        return "MAN"
    d2 = r.get("depth_2s")
    if d2 is not None and d2 >= DEEP_MIN_DEPTH + 1.0 and (r.get("bite_2s") or 0) >= 0.5:
        return "DEEP_ZONE"
    return "UNDER_ZONE"


def add_rule_roles(feats: pl.DataFrame) -> pl.DataFrame:
    rows = feats.to_dicts()
    return feats.with_columns(
        pl.Series("rule_align_role", [rule_align_role(r) for r in rows], dtype=pl.Utf8),
        pl.Series("rule_responsibility", [rule_responsibility(r) for r in rows], dtype=pl.Utf8),
    )


assert all(r in ALIGN_ROLES for r in ("EDGE", "INTERIOR_DL", "OFF_BALL_LB", "OVERHANG", "SLOT_CB", "BOUNDARY_CB",
                                      "BOX_SAFETY", "DEEP_HALF", "DEEP_MIDDLE"))
