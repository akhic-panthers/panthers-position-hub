"""Rule roles — the transparent, geometric seed labels.

These are NOT the product. They are (a) the deterministic fallback when no model is fitted, and
(b) half of the consensus label the model trains on (rule ∧ PFF alignment family agree). Every
threshold is in yards and named so a coach can argue with it.

v1.1 (2026-09-25, Phase 1 of the first real run, BEFORE any gate was read). Four defects found on real
frames, each flagged independently by PFF's charted slot and by NGS's own per-snap role, each a rule
ORDERING or a mis-applied constant rather than a new threshold:
  1. a press corner over a detached receiver at 1–2 yd was called EDGE (the on-line branch ran first);
     129 of 129 such snaps had a detached receiver within 4 yd, PFF LCB/RCB/SCB, NGS CB/SLOT_CB.
  2. the box pad (+1.5 yd, an off-ball concept) was used as the EDGE / INTERIOR boundary on the line, so
     5-, 6- and 7-techniques read INTERIOR. Measured vs NGS technique: 4-tech sits at the tackle's centre
     (median −0.26 yd), 5-tech +0.76, 6 +1.26, 7 +1.83, 9 +2.55. The boundary is the tackle's centre line.
  3. a backer at 6.0–7.2 yd INSIDE the box read BOX_SAFETY because the safety branch ran before the box
     branch; the registered table says OFF_BALL_LB is 2–7 inside the tackles' width. Ordering fixed.
  4. an off corner at 6–9 yd plays 5–7 yd inside the #1; the head-up tolerance (4 yd) missed him and he
     fell to BOX_SAFETY. A defender who is the widest on his side, ≥ 4 yd outside the tackle, with a
     detached receiver on his side, under 10 yd, is a boundary corner. (4 yd is the registered corner
     leverage constant, reused; no new number.)
  1b. fix 1 overshot on first re-read: 7- and 9-techniques over a wing or flexed TE became corners. On the line a
     corner must be ≥ 4 yd outside the tackle's centre (the same registered 4 yd). Press corners measured p5 4.1.
  5. `abs(lat_to_nearest_rec or 99)` turned a defender exactly head-up (0.0 yd) into "99 yd away". Caught by
     the planted press-slot regression test, not by a gate.
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
CB_MAX_LAT_TO_REC = 4.0       # head-up tolerance on the #1; also the minimum width outside the tackle for an off corner
DEEP_MIDDLE_MAX_LAT = 6.0     # a lone deep defender within this of the ball is the middle-of-field player


def rule_align_role(r: dict) -> str:
    d = r["depth"]
    lat = abs(r["lateral"])
    thw = float(r.get("tackle_half_width") or 4.0)
    outside_box = bool(r.get("outside_tackle"))            # beyond the tackle + 1.5 yd (the box edge)
    outside_shoulder = lat > thw                            # beyond the tackle's centre line (5-tech and wider)
    over = r.get("over_rec_num")
    _lr = r.get("lat_to_nearest_rec")
    lat_rec = 99.0 if _lr is None or _lr != _lr else abs(_lr)   # a head-up defender has 0.0, which `or` would turn into 99
    rec_detached = bool(r.get("nearest_rec_detached", False))
    same_side = (r.get("over_rec_side") == ("R" if r["lateral"] >= 0 else "L")) if r.get("over_rec_side") else False
    n_deep = int(r.get("n_deep") or 0)
    wrank = r.get("width_rank_side")

    if d >= DEEP_MIN_DEPTH:
        if n_deep <= 1 or lat <= DEEP_MIDDLE_MAX_LAT and n_deep == 3:
            return "DEEP_MIDDLE"
        return "DEEP_HALF" if n_deep >= 2 else "DEEP_MIDDLE"
    # (1) over a DETACHED receiver = a corner, whatever the depth: press corners live at 1–2 yd. ON the line he must
    #     also be ≥ 4 yd outside the tackle's centre (CB_MAX_LAT_TO_REC reused): a 7- or 9-technique over a wing or a
    #     flexed tight end is an edge. Measured: press corners p5 = 4.1 yd outside the tackle, on-line edges p90 = 3.2.
    wide_enough = d > ON_LINE_DEPTH or lat >= thw + CB_MAX_LAT_TO_REC
    if outside_box and rec_detached and over is not None and wide_enough:
        if over == 1 and lat_rec <= CB_MAX_LAT_TO_REC:
            return "BOUNDARY_CB"
        if over >= 2 and lat_rec <= SLOT_MAX_LAT_TO_REC and d <= SLOT_MAX_DEPTH:
            return "SLOT_CB"
    # (2) on the line: outside the tackle's centre line is the edge
    if d <= ON_LINE_DEPTH:
        return "EDGE" if outside_shoulder else "INTERIOR_DL"
    # (4) off corner with inside leverage: widest man on his side, well outside the box, a detached receiver on his side
    if outside_box and wrank == 1 and lat >= thw + CB_MAX_LAT_TO_REC and rec_detached and same_side:
        return "BOUNDARY_CB"
    # (3) in the box at the second level = a backer (2 < depth ≤ 7 inside the tackles' width, per the registered table)
    if not outside_box and d <= LB_MAX_DEPTH:
        return "OFF_BALL_LB"
    if d >= SAFETY_MIN_DEPTH:
        return "BOX_SAFETY"
    if outside_box:
        return "OVERHANG"
    return "BOX_SAFETY"


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
