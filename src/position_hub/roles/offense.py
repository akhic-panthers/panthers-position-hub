"""Offensive roles (docs/REGISTERED_offense_roles_v1.md): a geometry-only model of how PFF charts the skill player's
slot, plus the descriptive layer a coach reads beside it — routes, targets, motion, who covered him, whom he blocked.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from .model import _matrix
from .v2 import _clf, ece
from ..eval.extensions import offense_role

OFF_ROLES = ["WIDE", "SLOT", "FLEX", "INLINE_TE", "H_BACK", "TAILBACK"]
PFF_OFF_TO_ROLE = {
    **{s: "WIDE" for s in ("LWR", "RWR", "SLoWR", "SRoWR")},
    **{s: "SLOT" for s in ("SLWR", "SRWR")},
    **{s: "FLEX" for s in ("SLiWR", "SRiWR")},
    **{s: "INLINE_TE" for s in ("TE-L", "TE-R", "TE-iL", "TE-iR", "TE-oL", "TE-oR")},
    **{s: "H_BACK" for s in ("FB", "FB-L", "FB-R", "FB-oL", "FB-oR", "FB-iL", "FB-iR")},
    **{s: "TAILBACK" for s in ("HB", "HB-L", "HB-R", "HB-oL", "HB-oR", "HB-iL", "HB-iR")},
}
E4_TO_ROLE = {"X": "WIDE", "Z": "WIDE", "SLOT": "SLOT", "WING": "INLINE_TE", "INLINE_TE": "INLINE_TE", "BACKFIELD": "TAILBACK"}
FEATURES = ["x_snap", "y_snap", "abs_lateral", "outside_tackle_by", "tackle_half_width", "on_line", "in_backfield", "rec_num",
            "n_rec_side", "sideline_dist", "presnap_lateral_change", "x_line_set", "y_line_set", "speed_snap"]
PEER = {"WR": "WR", "TE": "TE", "RB": "RB", "HB": "RB", "FB": "RB"}


def motion_kind(code: str | None) -> str | None:
    """PFF Shift & Motion Key: '*' = moving at the snap (vs a shift that reset), 'x' = crossed the ball,
    'B:' = from the backfield, ':B' = into the backfield."""
    if not code:
        return None
    at_snap = code.startswith("*")
    c = code.lstrip("*").split(">")[-1]
    if c.startswith("B:") and c != "B:B":
        kind = "out of the backfield"
    elif c.endswith(":B"):
        kind = "into the backfield"
    elif "x" in c:
        kind = "across the formation"
    else:
        kind = "same side"
    return f"{'motion at the snap' if at_snap else 'shift'}, {kind}"


def load_offense(out: Path) -> pl.DataFrame:
    o = pl.read_parquet(out / "offense_alignment.parquet")
    plays = pl.read_parquet(out / "v2" / "scored.parquet", columns=["game_key", "gsis_play_id", "season", "week", "pff_DOWN", "pff_DISTANCE",
                                                                    "is_pass", "is_play_action", "pff_MOFOCPLAYED"]).unique(["game_key", "gsis_play_id"])
    o = o.drop([c for c in ("season", "week") if c in o.columns]).join(plays, on=["game_key", "gsis_play_id"], how="inner")
    pf = pl.read_parquet(out / "cache" / "pffoffense_full_2022_2025.parquet").select(
        pl.col("pff_GSISGAMEKEY").cast(pl.Int64).alias("game_key"), pl.col("pff_GSISPLAYID").cast(pl.Int64).alias("gsis_play_id"),
        pl.col("pff_GSISPLAYERID").cast(pl.Int64, strict=False).alias("nfl_id"), pl.col("pff_POSITION").alias("pff_off_position"),
        pl.col("pff_ROLE").alias("pff_off_role"), pl.col("pff_PASSROUTENAME").alias("route"),
        pl.col("pff_PASSROUTEDEPTH").cast(pl.Float64, strict=False).alias("route_depth"),
        (pl.col("pff_TARGETEDRECEIVER") == "Y").alias("targeted"), (pl.col("pff_BALLCARRIER") == "Y").alias("carrier"),
        pl.col("pff_MOTION").alias("motion_code")).unique(["game_key", "gsis_play_id", "nfl_id"])
    o = o.join(pf, on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    o = o.with_columns(pl.col("pff_off_position").replace_strict(PFF_OFF_TO_ROLE, default=None).alias("label_off"),
                       pl.col("route").replace("", None), pl.col("motion_code").replace("", None))
    rule = [E4_TO_ROLE[offense_role(r)] for r in o.select("in_backfield", "outside_tackle_by", "on_line", "x_snap", "rec_num").iter_rows(named=True)]
    return o.with_columns(pl.Series("rule_off_role", rule))


def _split_half(s: pl.DataFrame, min_snaps: int = 100) -> tuple[float, int, dict]:
    def mix(df):
        return df.group_by("nfl_id", "season").agg([pl.len().alias("n")] + [pl.col(f"p_off_{r}").mean().alias(r) for r in OFF_ROLES]).filter(pl.col("n") >= min_snaps // 2)
    j = mix(s.filter(pl.col("game_key") % 2 == 0)).join(mix(s.filter(pl.col("game_key") % 2 == 1)), on=["nfl_id", "season"], suffix="_o")
    rs = {}
    for r in OFF_ROLES:
        a, b = j[r].to_numpy(), j[f"{r}_o"].to_numpy()
        if a.std() > 0.01:
            rs[r] = float(np.corrcoef(a, b)[0, 1])
    return (float(np.median(list(rs.values()))) if rs else float("nan")), j.height, rs


def run_offense(out: Path, run_dir: Path, seed: int = 0) -> dict:
    from ..eval.gates import format_gates
    from ..viewer.export import _clean

    o = load_offense(out)
    hold = json.loads((out / "model.json").read_text())["holdout_games"]
    tr = o.filter(~pl.col("game_key").is_in(hold) & pl.col("label_off").is_not_null())
    clf = _clf(seed).fit(_matrix(tr, FEATURES), tr["label_off"].to_numpy())
    y = tr["label_off"].to_numpy().copy()
    rng = np.random.default_rng(seed)
    g = tr["game_key"].to_numpy()
    for gk in np.unique(g):
        i = np.where(g == gk)[0]
        y[i] = rng.permutation(y[i])
    null = _clf(seed).fit(_matrix(tr, FEATURES), y)

    P = clf.predict_proba(_matrix(o, FEATURES))
    cls = list(clf.classes_)
    o = o.with_columns([pl.Series(f"p_off_{r}", P[:, cls.index(r)] if r in cls else np.zeros(o.height)) for r in OFF_ROLES])
    o = o.with_columns(pl.Series("off_role", [cls[i] for i in P.argmax(1)]), pl.Series("off_top_p", P.max(1)))

    h = o.filter(pl.col("game_key").is_in(hold) & pl.col("label_off").is_not_null())
    acc = float((h["off_role"] == h["label_off"]).mean())
    acc_rule = float((h["rule_off_role"] == h["label_off"]).mean())
    maj = float(h["label_off"].value_counts()["count"].max() / h.height)
    acc_null = float((pl.Series(null.predict(_matrix(h, FEATURES))) == h["label_off"]).mean())
    e = ece(h["off_top_p"].to_numpy(), (h["off_role"] == h["label_off"]).to_numpy())
    r_half, n_half, per = _split_half(o)
    parts = []
    for _, grp in o.group_by("game_key", "gsis_play_id"):
        perm = rng.permutation(grp.height)
        parts.append(grp.with_columns([pl.Series(f"p_off_{r}", grp[f"p_off_{r}"].to_numpy()[perm]) for r in OFF_ROLES]))
    r_null, _, _ = _split_half(pl.concat(parts))
    bar1 = max(acc_rule + 0.02, maj + 0.15)
    gates = [
        {"name": "O1_heldout_vs_PFF_slot", "value": acc, "bar": bar1, "pass": acc >= bar1, "n": h.height, "note": f"E4 rule {acc_rule:.3f}; majority {maj:.3f}"},
        {"name": "O1_null_shuffled_labels", "value": acc_null, "bar": maj + 0.02, "pass": acc_null <= maj + 0.02, "n": h.height, "note": "labels shuffled within game, identical fit"},
        {"name": "O2_calibration_ECE", "value": e, "bar": 0.05, "pass": e <= 0.05, "n": h.height, "note": "top-label, 10 bins"},
        {"name": "O3_split_half", "value": r_half, "bar": 0.70, "pass": r_half >= 0.70, "n": n_half, "note": "per-role: " + ", ".join(f"{k} {v:.2f}" for k, v in per.items())},
        {"name": "O4_destruction", "value": r_null, "bar": f"< 0.5 × {r_half:.3f}", "pass": r_null < 0.5 * r_half, "n": n_half, "note": "role vectors shuffled across the offense within the play"},
    ]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "gates_offense.md").write_text(format_gates(gates) + "\n\n" + "\n".join(f"- {x['name']}: {x['note']}" for x in gates) + "\n")
    (run_dir / "gates_offense.json").write_text(json.dumps(_clean(gates), indent=1, default=str, allow_nan=False))
    (out / "offense").mkdir(exist_ok=True)
    o.write_parquet(out / "offense" / "scored.parquet")
    print(format_gates(gates))
    for x in gates:
        print(f"- {x['name']}: {x['note']}")
    return {"gates": gates}
