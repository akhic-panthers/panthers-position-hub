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
                nearest_rec_detached=True)
    base.update(kw)
    return base


def test_rule_roles_by_geometry():
    assert rule_align_role(_row(depth=1.0, outside_tackle=True)) == "EDGE"
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
