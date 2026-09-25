"""Soft role attribution — probabilities per snap, on both axes.

ALIGNMENT model. Target = the consensus label on snaps where the geometric rule and PFF's charted
alignment family agree (the two were produced independently: one from x/y, one by a charter). The
classifier then scores EVERY snap, including the disagreements, and its probability vector is the
snap's position field. A safety at 8.5 yards, 5 yards off the hash, comes back e.g.
BOX_SAFETY 0.55 · DEEP_HALF 0.30 · DEEP_MIDDLE 0.10 — which is the honest answer.

RESPONSIBILITY model. Target = coverage_defense.assignment folded to 6 classes (charted truth,
pass plays 2019+; here 2022+ where tracking exists). Scores every pass snap, so a player with no
charting still gets a played-role estimate; run plays are geometric (RUN_FIT / RUSH by the rule).

Both are HistGradientBoosting (monotone-free, handles NaN natively, no scaling). Evaluation is by
HELD-OUT GAMES, never random rows — rows from one play are not independent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier

from .taxonomy import ALIGN_ROLES, RESPONSIBILITIES
from .rules import add_rule_roles

ALIGN_FEATURES = ["depth", "lateral", "abs_lateral", "sideline_dist", "on_line", "in_box", "outside_tackle",
                  "tackle_half_width", "depth_rank", "n_deep", "n_box", "n_on_line", "on_strong_side",
                  "dist_nearest_rec", "over_rec_num", "lat_to_nearest_rec", "cushion_nearest_rec",
                  "nearest_rec_is_te", "nearest_rec_detached", "presnap_depth_change", "presnap_lateral_change",
                  "width_rank_side"]
RESP_FEATURES = ALIGN_FEATURES + ["bite_2s", "lateral_move_2s", "ground_covered_2s", "speed_2s", "crossed_los_2s",
                                  "min_depth_to_2s", "depth_2s", "dist_qb_2s", "dist_aligned_rec_2s",
                                  "dist_nearest_rec_2s", "depth_thr", "dist_nearest_rec_thr", "dist_qb_thr",
                                  "time_to_throw_s"]


def _matrix(df: pl.DataFrame, cols: list[str]) -> np.ndarray:
    out = np.full((df.height, len(cols)), np.nan, dtype=float)
    for j, c in enumerate(cols):
        if c in df.columns:
            s = df.get_column(c)
            if s.dtype == pl.Boolean:
                s = s.cast(pl.Float64)
            elif s.dtype == pl.Utf8:
                continue
            out[:, j] = s.cast(pl.Float64, strict=False).fill_null(np.nan).to_numpy()
    return out


def _hgb(seed: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                          l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
                                          random_state=seed)


@dataclass
class RoleAttributionModel:
    seed: int = 0
    align_clf: HistGradientBoostingClassifier | None = None
    resp_clf: HistGradientBoostingClassifier | None = None
    align_classes: list[str] = field(default_factory=list)
    resp_classes: list[str] = field(default_factory=list)
    fit_report: dict = field(default_factory=dict)

    # ── training labels ────────────────────────────────────────────────────────────────────────
    @staticmethod
    def consensus_align_labels(feats: pl.DataFrame) -> pl.DataFrame:
        """rule ∧ PFF family. PFF FS/SS is a role guess, so for safeties the rule alone decides the
        depth class but PFF must at least agree it is a safety."""
        f = feats if "rule_align_role" in feats.columns else add_rule_roles(feats)
        if "pff_align_family" not in f.columns:
            return f.with_columns(pl.col("rule_align_role").alias("label_align"))
        rule, fam = pl.col("rule_align_role"), pl.col("pff_align_family")
        safety_rule = rule.is_in(["BOX_SAFETY", "DEEP_HALF", "DEEP_MIDDLE"])
        safety_fam = fam.is_in(["BOX_SAFETY", "DEEP_SAFETY"])
        agree = (rule == fam) | (safety_rule & safety_fam) | ((rule == "OVERHANG") & fam.is_in(["OFF_BALL_LB", "EDGE", "BOX_SAFETY"]))
        return f.with_columns(pl.when(agree | fam.is_null()).then(rule).otherwise(None).alias("label_align"))

    # ── fit ────────────────────────────────────────────────────────────────────────────────────
    def fit(self, feats: pl.DataFrame, holdout_games: list[int] | None = None) -> "RoleAttributionModel":
        f = self.consensus_align_labels(feats)
        if holdout_games:
            f = f.filter(~pl.col("game_key").is_in(holdout_games))
        a = f.filter(pl.col("label_align").is_not_null())
        Xa, ya = _matrix(a, ALIGN_FEATURES), a.get_column("label_align").to_numpy()
        self.align_clf = _hgb(self.seed).fit(Xa, ya)
        self.align_classes = list(self.align_clf.classes_)
        self.fit_report["align_n"] = int(a.height)
        self.fit_report["align_label_coverage"] = float(a.height / max(f.height, 1))

        if "responsibility" in f.columns:
            r = f.filter(pl.col("responsibility").is_not_null() & pl.col("has_throw"))
            if r.height >= 200 and r.get_column("responsibility").n_unique() >= 2:
                Xr, yr = _matrix(r, RESP_FEATURES), r.get_column("responsibility").to_numpy()
                self.resp_clf = _hgb(self.seed).fit(Xr, yr)
                self.resp_classes = list(self.resp_clf.classes_)
                self.fit_report["resp_n"] = int(r.height)
        return self

    # ── score ──────────────────────────────────────────────────────────────────────────────────
    def predict(self, feats: pl.DataFrame) -> pl.DataFrame:
        """Adds p_align_<ROLE>, align_role (argmax), p_resp_<CLS>, resp_role. Missing columns = 0."""
        f = feats if "rule_align_role" in feats.columns else add_rule_roles(feats)
        f = self.consensus_align_labels(f) if "label_align" not in f.columns else f
        out = f
        if self.align_clf is not None:
            P = self.align_clf.predict_proba(_matrix(f, ALIGN_FEATURES))
            cols = {f"p_align_{c}": P[:, i] for i, c in enumerate(self.align_classes)}
            for role in ALIGN_ROLES:
                cols.setdefault(f"p_align_{role}", np.zeros(f.height))
            out = out.with_columns([pl.Series(k, v) for k, v in cols.items()])
            out = out.with_columns(pl.Series("align_role", [self.align_classes[i] for i in P.argmax(1)]))
        else:  # no model: one-hot the rule
            out = out.with_columns([pl.Series(f"p_align_{role}", (f.get_column("rule_align_role") == role).cast(pl.Float64)) for role in ALIGN_ROLES])
            out = out.with_columns(pl.col("rule_align_role").alias("align_role"))

        # responsibility: charted where present, model on other pass snaps, rule on the rest
        pass_mask = out.get_column("has_throw").fill_null(False).to_numpy() if "has_throw" in out.columns else np.zeros(out.height, bool)
        P = np.zeros((out.height, len(RESPONSIBILITIES)))
        idx = {c: i for i, c in enumerate(RESPONSIBILITIES)}
        if self.resp_clf is not None and pass_mask.any():
            pm = self.resp_clf.predict_proba(_matrix(out.filter(pl.Series(pass_mask)), RESP_FEATURES))
            rows = np.where(pass_mask)[0]
            for j, c in enumerate(self.resp_classes):
                if c in idx:
                    P[rows, idx[c]] = pm[:, j]
        # the model's own answer, BEFORE charted truth overwrites it — the only column G2b may score
        # (defect fixed 2026-09-25: G2b used to score resp_role, which IS the charted label where one exists)
        model_role = None
        if self.resp_clf is not None and pass_mask.any():
            model_role = [None] * out.height
            for i in np.where(pass_mask)[0]:
                model_role[i] = RESPONSIBILITIES[int(P[i].argmax())] if P[i].sum() > 0 else None
        rule = out.get_column("rule_responsibility").to_list() if "rule_responsibility" in out.columns else [None] * out.height
        charted = out.get_column("responsibility").to_list() if "responsibility" in out.columns else [None] * out.height
        for i in range(out.height):
            if charted[i] in idx:                       # a charted rep is the truth: hard one-hot
                P[i] = 0.0
                P[i, idx[charted[i]]] = 1.0
            elif P[i].sum() == 0 and rule[i] in idx:    # no charting, no model → the rule
                P[i, idx[rule[i]]] = 1.0
        out = out.with_columns([pl.Series(f"p_resp_{c}", P[:, idx[c]]) for c in RESPONSIBILITIES])
        resp_role = [RESPONSIBILITIES[k] if P[i].sum() > 0 else None for i, k in enumerate(P.argmax(1))]
        out = out.with_columns(pl.Series("resp_role", resp_role, dtype=pl.Utf8))
        return out.with_columns(pl.Series("resp_model_role", model_role if model_role is not None else [None] * out.height, dtype=pl.Utf8))

    # ── persistence ────────────────────────────────────────────────────────────────────────────
    def save(self, path: Path) -> None:
        import pickle

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(self, fh)
        path.with_suffix(".json").write_text(json.dumps(self.fit_report, indent=2))

    @staticmethod
    def load(path: Path) -> "RoleAttributionModel":
        import pickle

        with open(path, "rb") as fh:
            return pickle.load(fh)
