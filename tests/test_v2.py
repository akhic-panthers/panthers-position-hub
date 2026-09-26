import numpy as np
import polars as pl

from position_hub.roles.v2 import PFF_SLOT_TO_V2, V2_ROLES, ece, v2_label


def test_v2_label_folds_pff_slots():
    df = pl.DataFrame({"pff_alignment": ["LEO", "LE", "DRT", "RILB", "SCBoL", "LCB", "FS", "FSR", "SSL", "PDR1", None]})
    assert v2_label(df).to_list() == ["EDGE", "INTERIOR_DL", "INTERIOR_DL", "OFF_BALL_LB", "SLOT_CB", "BOUNDARY_CB",
                                      "DEEP_MIDDLE", "DEEP_HALF", "BOX_SAFETY", None, None]
    assert set(PFF_SLOT_TO_V2.values()) == set(V2_ROLES) and "OVERHANG" not in V2_ROLES


def test_ece_catches_overconfidence():
    """Planted defect: a model that says 0.95 and is right half the time must fail the 0.05 bar."""
    rng = np.random.default_rng(0)
    conf = np.full(10_000, 0.95)
    assert ece(conf, rng.random(10_000) < 0.95) < 0.02
    assert ece(conf, rng.random(10_000) < 0.50) > 0.40
