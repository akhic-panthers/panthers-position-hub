import numpy as np
import polars as pl

from conftest import frames_to_game
from position_hub.ngs.features import defender_features_for_play
from position_hub.ngs.standardize import standardize_play
from position_hub.synth import make_game


def _one_play(seed, flip_wanted=None):
    fr, truth = make_game(59100, n_plays=6, seed=seed)
    g = frames_to_game(fr)
    for pid in g["gsis_play_id"].unique().to_list():
        pf = standardize_play(g.filter(pl.col("gsis_play_id") == pid))
        if pf is not None and (flip_wanted is None or pf.is_flipped == flip_wanted):
            return pf, truth.filter(pl.col("gsis_play_id") == pid)
    raise AssertionError("no play")


def test_snap_and_direction_are_found():
    pf, _ = _one_play(1)
    assert pf.snap_frame > 0
    assert pf.ball_proxy == "center"
    # the offense moves +x: every offensive player is at or behind the line at the snap, defenders in front
    snap = pf.at(pf.snap_frame)
    assert snap.filter(pl.col("is_offense"))["x"].max() < 1.0
    assert snap.filter(~pl.col("is_offense"))["x"].min() > 0.0


def test_flipped_and_unflipped_plays_agree_in_standardized_frame():
    """A right-to-left play is the mirror of a left-to-right one; after standardization the
    defensive depths must be the same distribution (the template is identical)."""
    pf_r, _ = _one_play(2, flip_wanted=False)
    pf_l, _ = _one_play(2, flip_wanted=True)
    dr = sorted(pf_r.defenders_at(pf_r.snap_frame)["x"].round(0).to_list())
    dl = sorted(pf_l.defenders_at(pf_l.snap_frame)["x"].round(0).to_list())
    assert len(dr) == len(dl) == 11
    assert np.allclose(np.median(dr), np.median(dl), atol=1.5)


def test_defender_features_have_the_registered_geometry():
    pf, truth = _one_play(3)
    f = defender_features_for_play(pf)
    assert f.height == 11
    assert (f["depth"] > 0).all()
    assert f["n_deep"].n_unique() == 1
    j = f.join(truth, on=["game_key", "gsis_play_id", "nfl_id"])
    # an edge rusher on a pass play moves toward the line: bite is negative; a deep safety bails: positive
    if j.filter(pl.col("is_pass")).height:
        edge = j.filter((pl.col("true_align_role") == "EDGE") & pl.col("is_pass"))
        deep = j.filter(pl.col("true_align_role").is_in(["DEEP_MIDDLE", "DEEP_HALF"]) & pl.col("is_pass"))
        if edge.height:
            assert edge["bite_2s"].max() < 0
        if deep.height:
            assert deep["bite_2s"].min() > 0
    # the boundary corner is over #1
    cb = j.filter(pl.col("true_align_role") == "BOUNDARY_CB")
    assert (cb["over_rec_num"] == 1).all()
    assert cb["outside_tackle"].all()
