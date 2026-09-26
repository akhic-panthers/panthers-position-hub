"""v2 alignment — a geometry-only model of how PFF's charter labels the snap (docs/REGISTERED_role_attribution_v2.md).

v1's label was the rule, so the model became the rule. v2's label is PFF's charted slot folded to eight roles, so the
probability means "how often a charter calls a snap that looks like this one each role". NGS's own per-snap role is the
independent check; it is never a feature and never a label.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier

from .model import ALIGN_FEATURES, _matrix

V2_ROLES = ["EDGE", "INTERIOR_DL", "OFF_BALL_LB", "SLOT_CB", "BOUNDARY_CB", "BOX_SAFETY", "DEEP_HALF", "DEEP_MIDDLE"]
PFF_SLOT_TO_V2 = {
    **{s: "EDGE" for s in ("LEO", "REO", "LOLB", "ROLB", "DLE", "DRE")},
    **{s: "INTERIOR_DL" for s in ("DLT", "DRT", "NT", "NLT", "NRT", "LE", "RE")},
    **{s: "OFF_BALL_LB" for s in ("MLB", "LILB", "RILB", "LLB", "RLB")},
    **{s: "SLOT_CB" for s in ("SCBL", "SCBR", "SCBiL", "SCBiR", "SCBoL", "SCBoR")},
    **{s: "BOUNDARY_CB" for s in ("LCB", "RCB")},
    "FS": "DEEP_MIDDLE", "FSL": "DEEP_HALF", "FSR": "DEEP_HALF",
    **{s: "BOX_SAFETY" for s in ("SS", "SSL", "SSR")},
}
RULE_TO_V2 = {"OVERHANG": "OFF_BALL_LB"}
NGS_FAMILY = {"CB": "BOUNDARY_CB", "SLOT_CB": "SLOT_CB", "HIGH_SAFETY": "DEEP_SAFETY", "BOX_SAFETY": "BOX_SAFETY",
              "MLB": "OFF_BALL_LB", "OLB": "OFF_BALL_LB", "EDGE": "EDGE", "INTERIOR_LINE": "INTERIOR_DL"}
FEATURES = ALIGN_FEATURES


def v2_label(df: pl.DataFrame) -> pl.Series:
    return df["pff_alignment"].replace_strict(PFF_SLOT_TO_V2, default=None).alias("label_v2")


def _clf(seed: int = 0) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                          l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=seed)


def fit_v2(f: pl.DataFrame, holdout: list[int], seed: int = 0, shuffle_within_game: bool = False) -> HistGradientBoostingClassifier:
    tr = f.filter(~pl.col("game_key").is_in(holdout) & pl.col("label_v2").is_not_null())
    y = tr["label_v2"].to_numpy()
    if shuffle_within_game:                      # the V1 destruction control
        rng = np.random.default_rng(seed)
        g = tr["game_key"].to_numpy()
        y = y.copy()
        for gk in np.unique(g):
            i = np.where(g == gk)[0]
            y[i] = rng.permutation(y[i])
    return _clf(seed).fit(_matrix(tr, FEATURES), y)


def predict_v2(clf: HistGradientBoostingClassifier, f: pl.DataFrame) -> pl.DataFrame:
    P = clf.predict_proba(_matrix(f, FEATURES))
    cls = list(clf.classes_)
    cols = [pl.Series(f"p_align_{c}", P[:, cls.index(c)] if c in cls else np.zeros(f.height)) for c in V2_ROLES]
    cols.append(pl.Series("p_align_OVERHANG", np.zeros(f.height)))     # kept at zero so v1 aggregation code runs unchanged
    out = f.drop([c for c in f.columns if c.startswith("p_align_")] + (["align_role"] if "align_role" in f.columns else []))
    out = out.with_columns(cols).with_columns(pl.Series("align_role", [cls[i] for i in P.argmax(1)]),
                                              pl.Series("align_top_p", P.max(1)))
    return out


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(e)


def gates_v2(scored: pl.DataFrame, holdout: list[int], null_acc: float | None) -> tuple[list[dict], dict]:
    fold = {"DEEP_HALF": "DEEP_SAFETY", "DEEP_MIDDLE": "DEEP_SAFETY"}
    h = scored.filter(pl.col("game_key").is_in(holdout))
    lab = h.filter(pl.col("label_v2").is_not_null())
    rule = lab["rule_align_role"].replace(RULE_TO_V2)
    acc_m = float((lab["align_role"] == lab["label_v2"]).mean())
    acc_r = float((rule == lab["label_v2"]).mean())
    maj = float(lab["label_v2"].value_counts()["count"].max() / lab.height)

    n = h.filter(pl.col("ngs_align_family").is_not_null())
    def ngs_agree(col: pl.Series) -> float:
        return float((col.replace(fold).replace(RULE_TO_V2) == n["ngs_align_family"]).mean())
    ngs_m, ngs_r = ngs_agree(n["align_role"]), ngs_agree(n["rule_align_role"])
    nl = n.filter(pl.col("label_v2").is_not_null())
    ceil = float((nl["label_v2"].replace(fold) == nl["ngs_align_family"]).mean())

    conf = lab["align_top_p"].to_numpy()
    e = ece(conf, (lab["align_role"] == lab["label_v2"]).to_numpy())
    soft = float((h["align_top_p"] < 0.8).mean())

    g = [
        {"name": "V1_heldout_vs_charter", "value": acc_m, "bar": acc_r + 0.02, "pass": acc_m >= acc_r + 0.02, "n": lab.height,
         "note": f"rule {acc_r:.3f} on the same snaps; majority {maj:.3f}"},
        {"name": "V2_heldout_vs_NGS", "value": ngs_m, "bar": ngs_r - 0.01, "pass": ngs_m >= ngs_r - 0.01, "n": n.height,
         "note": f"rule {ngs_r:.3f}; ceiling (PFF label vs NGS) {ceil:.3f}" + ("  ⛔ model beats its label source by > 0.02" if ngs_m > ceil + 0.02 else "")},
        {"name": "V3_calibration_ECE", "value": e, "bar": 0.05, "pass": e <= 0.05, "n": lab.height, "note": "top-label, 10 bins"},
        {"name": "V4_field_is_soft", "value": soft, "bar": 0.05, "pass": soft >= 0.05, "n": h.height, "note": "share of held-out snaps with top probability < 0.8"},
    ]
    if null_acc is not None:
        g.append({"name": "V1_null_shuffled_labels", "value": null_acc, "bar": maj + 0.02, "pass": null_acc <= maj + 0.02, "n": lab.height,
                  "note": "labels shuffled within game, identical fit — must collapse to the majority class"})
    extra = {"rule_acc": acc_r, "majority": maj, "ngs_rule": ngs_r, "ceiling": ceil}
    return g, extra


def run_v2(out: Path, run_dir: Path, seed: int = 0) -> dict:
    from ..eval.gates import destruction_control, format_gates, split_half_stability

    f = pl.read_parquet(out / "features.parquet")
    f = f.with_columns(v2_label(f))
    if "ngs_align_family" not in f.columns and "ngs_role" in f.columns:
        f = f.with_columns(pl.col("ngs_role").replace_strict(NGS_FAMILY, default=None).alias("ngs_align_family"))
    hold = json.loads((out / "model.json").read_text())["holdout_games"]
    clf = fit_v2(f, hold, seed)
    null = fit_v2(f, hold, seed, shuffle_within_game=True)
    h = f.filter(pl.col("game_key").is_in(hold) & pl.col("label_v2").is_not_null())
    null_acc = float((pl.Series(null.predict(_matrix(h, FEATURES))) == h["label_v2"]).mean())

    v1 = pl.read_parquet(out / "scored.parquet")                     # carries v1 responsibility, unchanged in v2
    keep = ["game_key", "gsis_play_id", "nfl_id"] + [c for c in v1.columns if c.startswith("p_resp_")] + ["resp_role", "resp_model_role"]
    s = predict_v2(clf, f).join(v1.select([c for c in keep if c in v1.columns]), on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    v2dir = out / "v2"
    v2dir.mkdir(parents=True, exist_ok=True)
    s.write_parquet(v2dir / "scored.parquet")

    gates, extra = gates_v2(s, hold, null_acc)
    g3 = split_half_stability(s)
    g4 = destruction_control(s)
    g3["name"], g4["name"] = "V5_split_half", "V6_destruction"
    gates += [g3, g4]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "gates_v2.md").write_text(format_gates(gates) + "\n\n" + "\n".join(f"- {g['name']}: {g['note']}" for g in gates) + "\n")
    from ..viewer.export import _clean
    (run_dir / "gates_v2.json").write_text(json.dumps(_clean(gates), indent=1, default=str, allow_nan=False))
    print(format_gates(gates))
    for g in gates:
        print(f"- {g['name']}: {g['note']}")
    return {"gates": gates, **extra}
