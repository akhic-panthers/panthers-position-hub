import numpy as np
import polars as pl
import pytest

from position_hub.eval.gates import destruction_control, heldout_accuracy, run_gates, split_half_stability
from position_hub.roles.aggregate import add_peer_percentiles, player_role_mix, team_role_mix
from position_hub.roles.model import RoleAttributionModel
from position_hub.roles.taxonomy import ALIGN_ROLES, RESPONSIBILITIES


@pytest.fixture(scope="module")
def fitted(season):
    feats, truth, _ = season
    hold = sorted(feats["game_key"].unique().to_list())[-2:]
    m = RoleAttributionModel(seed=0).fit(feats, holdout_games=hold)
    return m, m.predict(feats), hold


def test_model_beats_rule_on_heldout_games(fitted):
    m, scored, hold = fitted
    h = scored.filter(pl.col("game_key").is_in(hold))
    model_acc = (h["align_role"] == h["true_align_role"]).mean()
    rule_acc = (h["rule_align_role"] == h["true_align_role"]).mean()
    assert model_acc >= 0.90 and model_acc >= rule_acc, (model_acc, rule_acc)


def test_probabilities_are_distributions(fitted):
    _, scored, _ = fitted
    P = np.stack([scored[f"p_align_{r}"].to_numpy() for r in ALIGN_ROLES], 1)
    assert np.allclose(P.sum(1), 1.0, atol=1e-6)
    R = np.stack([scored[f"p_resp_{c}"].to_numpy() for c in RESPONSIBILITIES], 1)
    assert np.allclose(R.sum(1), 1.0, atol=1e-6)
    # a charted rep is the truth: one-hot on the charted class
    ch = scored.filter(pl.col("responsibility").is_not_null())
    assert (ch["resp_role"] == ch["responsibility"]).all()


def test_uncharted_pass_snaps_get_modelled_responsibility(fitted):
    _, scored, hold = fitted
    u = scored.filter(pl.col("game_key").is_in(hold) & pl.col("has_throw") & pl.col("responsibility").is_null())
    assert u.height > 0
    assert (u["resp_role"] == u["true_responsibility"]).mean() >= 0.85


def test_player_role_mix_recovers_the_designed_safety_split(fitted):
    """The synthetic safeties trade jobs on 35% of snaps: the FS should read ~65% deep, ~35% box."""
    _, scored, _ = fitted
    mix = player_role_mix(scored, min_snaps=40)
    assert mix.height > 0
    s = mix.filter(pl.col("roster_pos") == "FS")
    assert s.height >= 2
    deep = (s["share_DEEP_MIDDLE"] + s["share_DEEP_HALF"]).mean()
    box = s["share_BOX_SAFETY"].mean()
    assert 0.5 < deep < 0.85 and 0.15 < box < 0.5, (deep, box)
    # soft shares sum to one; entropy is positive for a man with two jobs
    shares = mix.select([f"share_{r}" for r in ALIGN_ROLES]).sum_horizontal()
    assert np.allclose(shares.to_numpy(), 1.0, atol=1e-6)
    assert (s["align_entropy"] > 0.3).all()


def test_percentiles_are_within_peer_group(fitted):
    _, scored, _ = fitted
    mix = add_peer_percentiles(player_role_mix(scored, min_snaps=40), min_snaps=40)
    pc = mix["pct_share_BOX_SAFETY"].drop_nulls()
    assert pc.min() >= 0 and pc.max() <= 100
    # within one peer group and season the top man is at 100
    s = mix.filter(pl.col("peer_group") == "S")
    assert s["pct_mean_depth"].max() == 100.0
    assert set(mix["peer_group"].unique().to_list()) <= {"S", "CB", "LB", "EDGE", "IDL", "DB"}


def test_team_role_mix_has_shells(fitted):
    _, scored, _ = fitted
    tm = team_role_mix(scored)
    assert tm.height >= 2
    assert np.allclose((tm["shell_0_high"] + tm["shell_1_high"] + tm["shell_2_high"] + tm["shell_3plus_high"]).to_numpy(), 1.0)


def test_gates_run_and_destruction_control_can_fail(fitted):
    """§3 of the required block: a check never shown to fail is not evidence. The destruction
    control shuffles role vectors within a play; stability must collapse. We also plant the defect
    the other way: feed the SHUFFLED table to the stability gate as if it were real and it must NO-GO."""
    _, scored, hold = fitted
    gates = run_gates(scored, holdout_games=hold, min_snaps=40)
    by = {g["name"]: g for g in gates}
    assert by["G3_split_half"]["pass"] is True
    assert by["G4_destruction"]["pass"] is True          # i.e. the null collapsed
    assert by["G4_destruction"]["value"] < 0.5 * by["G3_split_half"]["value"]
    # planted defect: identity broken → G3 must fail
    rng = np.random.default_rng(0)
    parts = []
    pcols = [c for c in scored.columns if c.startswith("p_align_")] + ["align_role"]
    for _, g in scored.group_by(["game_key", "gsis_play_id"], maintain_order=True):
        perm = rng.permutation(g.height)
        parts.append(g.with_columns([pl.Series(c, g[c].to_numpy()[perm]) for c in pcols]))
    broken = split_half_stability(pl.concat(parts), min_snaps=40)
    assert broken["pass"] is False


def test_heldout_gate_uses_games_not_rows(fitted):
    _, scored, hold = fitted
    g = heldout_accuracy(scored, hold, "true_align_role", "align_role")
    assert g["n"] == scored.filter(pl.col("game_key").is_in(hold)).height


def test_viewer_json_has_no_bare_nan(tmp_path):
    """Planted defect: a NaN share must come out as null, or JSON.parse fails in the viewer."""
    import json

    import polars as pl

    from position_hub.viewer.export import export_pos_boards, export_viewer_json

    mix = pl.DataFrame({"nfl_id": [1], "season": [2025], "snaps": [300], "player_name": ["X"], "peer_group": ["S"], "team": ["CAR"],
                        "share_DEEP_MIDDLE": [float("nan")], "pct_share_DEEP_MIDDLE": [float("nan")], "mean_depth": [float("inf")]})
    for fn, name in ((export_viewer_json, "v.json"), (export_pos_boards, "b.json")):
        txt = (tmp_path / name).read_text() if fn(mix, tmp_path / name) is not None else ""
        assert "NaN" not in txt and "Infinity" not in txt
        json.loads(txt)
