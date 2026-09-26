import polars as pl

from position_hub.pff.vocab import align_family, assignment_class, parse_depth_string
from position_hub.roles.rules import rule_align_role, rule_responsibility


def test_pff_depth_strings_parse():
    assert parse_depth_string("LCB (5); SCBL (3); FSL (11)") == {"LCB": 5.0, "SCBL": 3.0, "FSL": 11.0}
    assert parse_depth_string("") == {} and parse_depth_string(None) == {}


def test_assignment_classes_and_match_modifiers():
    assert assignment_class("MAN") == "MAN"
    assert assignment_class("PRE") == "RUSH"
    assert assignment_class("3M") == "DEEP_ZONE"
    assert assignment_class("CFL") == "UNDER_ZONE"
    assert assignment_class("3M", "MAT") == "MAN_MATCH"          # zone call, man in effect
    assert assignment_class("HOL", None, "CAR") == "MAN_MATCH"
    assert assignment_class("MAN", "MAT") == "MAN"
    assert assignment_class("") is None and assignment_class("XYZ") is None


def test_alignment_families_fold_left_right():
    assert align_family("SCBiL") == align_family("SCBR") == "SLOT_CB"
    assert align_family("LEO") == align_family("ROLB") == "EDGE"
    assert align_family("FSL") == "DEEP_SAFETY" and align_family("SSR") == "BOX_SAFETY"
    assert align_family(None) is None


def _row(**kw):
    base = dict(depth=5.0, lateral=1.0, outside_tackle=False, over_rec_num=None, lat_to_nearest_rec=9.0, n_deep=1,
                nearest_rec_detached=True, tackle_half_width=3.3)
    base.update(kw)
    return base


def test_rule_roles_by_geometry():
    assert rule_align_role(_row(depth=1.0, lateral=6.0, outside_tackle=True)) == "EDGE"
    assert rule_align_role(_row(depth=1.0, outside_tackle=False)) == "INTERIOR_DL"
    assert rule_align_role(_row(depth=4.5)) == "OFF_BALL_LB"
    assert rule_align_role(_row(depth=4.5, outside_tackle=True)) == "OVERHANG"
    assert rule_align_role(_row(depth=8.5, lateral=6)) == "BOX_SAFETY"
    assert rule_align_role(_row(depth=14, lateral=0.5, n_deep=1)) == "DEEP_MIDDLE"
    assert rule_align_role(_row(depth=12.5, lateral=8, n_deep=2)) == "DEEP_HALF"
    assert rule_align_role(_row(depth=6, lateral=20, outside_tackle=True, over_rec_num=1, lat_to_nearest_rec=0.5)) == "BOUNDARY_CB"
    assert rule_align_role(_row(depth=5.5, lateral=11, outside_tackle=True, over_rec_num=2, lat_to_nearest_rec=0.5)) == "SLOT_CB"


def test_regression_backer_next_to_attached_tight_end_is_not_a_slot():
    """Defect caught on the first synthetic run: an inside backer 2 yd from an attached TE (#3)
    was called a slot corner. A slot is outside the box over a detached receiver."""
    lb = _row(depth=4.5, lateral=2.0, outside_tackle=False, over_rec_num=3, lat_to_nearest_rec=2.0, nearest_rec_detached=False)
    assert rule_align_role(lb) == "OFF_BALL_LB"


def test_rule_responsibility():
    assert rule_responsibility({"bite_2s": -2.0, "crossed_los_2s": True, "has_throw": True, "min_depth_to_2s": -1.0}) == "RUSH"
    assert rule_responsibility({"bite_2s": -2.0, "has_throw": False, "has_handoff": True}) == "RUN_FIT"
    assert rule_responsibility({"bite_2s": 4.0, "has_throw": True, "depth_2s": 16.0, "min_depth_to_2s": 12}) == "DEEP_ZONE"
    assert rule_responsibility({"bite_2s": 2.0, "has_throw": True, "depth_2s": 6.0, "min_depth_to_2s": 4}) == "UNDER_ZONE"
    assert rule_responsibility({"bite_2s": 3.0, "has_throw": True, "depth_2s": 9.0, "dist_aligned_rec_2s": 2.0, "ground_covered_2s": 5.0, "min_depth_to_2s": 6}) == "MAN"
    assert rule_responsibility({"bite_2s": None}) is None


def test_rule_accuracy_on_synthetic_truth(season):
    feats, _, _ = season
    acc = (feats["rule_align_role"] == feats["true_align_role"]).mean()
    assert acc >= 0.80, acc
    p = feats.filter(pl.col("rule_responsibility").is_not_null())
    assert (p["rule_responsibility"] == p["true_responsibility"]).mean() >= 0.80


# ── v1.1 regressions: each fix found on real frames in Phase 1 (2026-09-25), planted so it must stay caught ──
def test_v11_press_corner_is_not_an_edge():
    """A corner pressed at 1.5 yd over a detached #1 was EDGE because the on-line branch ran first."""
    press = _row(depth=1.5, lateral=14.6, outside_tackle=True, over_rec_num=1, lat_to_nearest_rec=0.1, nearest_rec_detached=True)
    assert rule_align_role(press) == "BOUNDARY_CB"
    press_slot = _row(depth=1.3, lateral=9.0, outside_tackle=True, over_rec_num=2, lat_to_nearest_rec=0.0, nearest_rec_detached=True)
    assert rule_align_role(press_slot) == "SLOT_CB"


def test_v11_five_technique_is_an_edge_three_technique_is_not():
    """Edge/interior boundary on the line is the tackle's centre line, not the box pad (+1.5)."""
    assert rule_align_role(_row(depth=1.0, lateral=3.3 + 0.76, outside_tackle=False)) == "EDGE"      # 5-tech
    assert rule_align_role(_row(depth=1.0, lateral=3.3 - 0.88, outside_tackle=False)) == "INTERIOR_DL"  # 3-tech


def test_v11_backer_at_six_and_a_half_inside_the_box_is_a_backer():
    assert rule_align_role(_row(depth=6.5, lateral=1.5, outside_tackle=False)) == "OFF_BALL_LB"
    assert rule_align_role(_row(depth=8.5, lateral=1.5, outside_tackle=False)) == "BOX_SAFETY"


def test_v11_off_corner_with_inside_leverage_is_a_corner():
    """Off corner at 8 yd, 4 yd inside his #1, widest man on his side: was BOX_SAFETY."""
    off = _row(depth=8.0, lateral=12.0, outside_tackle=True, over_rec_num=2, lat_to_nearest_rec=4.1, nearest_rec_detached=True,
               width_rank_side=1, over_rec_side="R")
    assert rule_align_role(off) == "BOUNDARY_CB"
    # the same spot without a receiver on his side (a safety rolled down to a trips-away side) is not
    assert rule_align_role({**off, "over_rec_side": "L"}) != "BOUNDARY_CB"


def test_v11_nine_technique_over_a_wing_is_still_an_edge():
    nine = _row(depth=1.3, lateral=6.0, outside_tackle=True, over_rec_num=2, lat_to_nearest_rec=0.8, nearest_rec_detached=True)
    assert rule_align_role(nine) == "EDGE"
