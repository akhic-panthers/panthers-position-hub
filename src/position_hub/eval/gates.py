"""Registered gates — written before the numbers, run after. See docs/REGISTERED_role_attribution_v1.md.

Every gate returns {name, value, bar, pass, n, note}. A NO-GO is a shippable finding; a gate that
has never been shown to fail is not evidence, so `destruction_control` exists to fail on purpose
(shuffled inputs must collapse the stability), and tests plant that failure.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from ..roles.aggregate import player_role_mix
from ..roles.taxonomy import ALIGN_ROLES

SHARE_COLS = [f"share_{r}" for r in ALIGN_ROLES]


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < 3 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1])


def agreement_with_pff(scored: pl.DataFrame, bar: float = 0.80) -> dict:
    """G1 · SANITY, not the claim. Top-1 alignment role vs PFF's charted family, folding the
    safety depth classes to PFF's two. Below the bar = the geometry and the charter disagree on
    what a slot / box / deep player is, and the taxonomy must be re-read before anything ships."""
    if "pff_align_family" not in scored.columns:
        return {"name": "G1_pff_agreement", "value": None, "bar": bar, "pass": None, "n": 0, "note": "no PFF alignment column"}
    fold = {"DEEP_HALF": "DEEP_SAFETY", "DEEP_MIDDLE": "DEEP_SAFETY", "OVERHANG": "OFF_BALL_LB"}
    s = scored.filter(pl.col("pff_align_family").is_not_null())
    mine = [fold.get(r, r) for r in s.get_column("align_role").to_list()]
    theirs = s.get_column("pff_align_family").to_list()
    ok = [a == b or (a == "OFF_BALL_LB" and b in ("EDGE",)) for a, b in zip(mine, theirs)]
    v = float(np.mean(ok)) if ok else float("nan")
    return {"name": "G1_pff_agreement", "value": v, "bar": bar, "pass": bool(v >= bar), "n": len(ok),
            "note": "top-1 alignment role vs PFF alignment family (safety depth classes folded)"}


def heldout_accuracy(scored: pl.DataFrame, holdout_games: list[int], truth_col: str, pred_col: str,
                     mask: pl.Expr | None = None, bar_over_majority: float = 0.15) -> dict:
    """G2 · held-out GAMES (never rows). Bar = beat the majority class by a margin."""
    h = scored.filter(pl.col("game_key").is_in(holdout_games) & pl.col(truth_col).is_not_null())
    if mask is not None:
        h = h.filter(mask)
    if h.height == 0:
        return {"name": f"G2_heldout_{pred_col}", "value": None, "bar": None, "pass": None, "n": 0, "note": "empty"}
    acc = float((h.get_column(pred_col) == h.get_column(truth_col)).mean())
    maj = float(h.get_column(truth_col).value_counts().get_column("count").max() / h.height)
    return {"name": f"G2_heldout_{pred_col}", "value": acc, "bar": maj + bar_over_majority, "pass": bool(acc >= maj + bar_over_majority),
            "n": h.height, "note": f"majority-class baseline {maj:.3f}; games {sorted(holdout_games)}"}


def split_half_stability(scored: pl.DataFrame, min_snaps: int = 100, bar: float = 0.70, season_col: str = "season") -> dict:
    """G3 · does a player's role mix REPEAT? Even games vs odd games, same season, per share column.
    Value = median correlation across role shares (weighted toward roles that vary)."""
    if season_col not in scored.columns:
        scored = scored.with_columns(pl.lit(0).alias(season_col))
    even = player_role_mix(scored.filter(pl.col("game_key") % 2 == 0), season_col, min_snaps=min_snaps // 2)
    odd = player_role_mix(scored.filter(pl.col("game_key") % 2 == 1), season_col, min_snaps=min_snaps // 2)
    j = even.join(odd, on=["nfl_id", season_col], suffix="_odd")
    if j.height < 5:
        return {"name": "G3_split_half", "value": None, "bar": bar, "pass": None, "n": j.height, "note": "too few players"}
    cors = {}
    for c in SHARE_COLS:
        if c in j.columns and j.get_column(c).std() and j.get_column(c).std() > 0.01:
            cors[c] = _corr(j.get_column(c).to_numpy(), j.get_column(f"{c}_odd").to_numpy())
    v = float(np.nanmedian(list(cors.values()))) if cors else float("nan")
    return {"name": "G3_split_half", "value": v, "bar": bar, "pass": bool(v >= bar), "n": j.height,
            "note": "median even/odd-game correlation of alignment shares; per-role: " + ", ".join(f"{k[6:]} {v_:.2f}" for k, v_ in cors.items())}


def destruction_control(scored: pl.DataFrame, seed: int = 0, min_snaps: int = 100, season_col: str = "season") -> dict:
    """G4 · the control that must FAIL. Shuffle which defender on the play got which probability
    vector (play structure kept, identity broken). Split-half stability must collapse toward 0.
    If it does not, the stability was carried by team/formation, not the man."""
    rng = np.random.default_rng(seed)
    pcols = [c for c in scored.columns if c.startswith("p_align_")]
    parts = []
    for _, g in scored.group_by(["game_key", "gsis_play_id"], maintain_order=True):
        perm = rng.permutation(g.height)
        parts.append(g.with_columns([pl.Series(c, g.get_column(c).to_numpy()[perm]) for c in pcols + ["align_role"]]))
    shuffled = pl.concat(parts)
    real = split_half_stability(scored, min_snaps=min_snaps, season_col=season_col)
    null = split_half_stability(shuffled, min_snaps=min_snaps, season_col=season_col)
    v = null["value"]
    computable = v is not None and not np.isnan(v) and real["value"] is not None and not np.isnan(real["value"])
    collapsed = bool(computable and v < 0.5 * real["value"]) if computable else None
    rv = f"{real['value']:.3f}" if real["value"] is not None else "—"
    return {"name": "G4_destruction", "value": v, "bar": f"< 0.5 × real ({rv})", "pass": collapsed, "n": null["n"],
            "note": "within-play shuffle of role vectors; stability must collapse"}


def run_gates(scored: pl.DataFrame, holdout_games: list[int] | None = None, min_snaps: int = 100) -> list[dict]:
    out = [agreement_with_pff(scored)]
    if holdout_games:
        if "true_align_role" in scored.columns:      # synthetic truth (tests only)
            out.append(heldout_accuracy(scored, holdout_games, "true_align_role", "align_role"))
        elif "label_align" in scored.columns:           # real data: the consensus label on held-out games
            g = heldout_accuracy(scored, holdout_games, "label_align", "align_role")
            g["name"] = "G2a_heldout_alignment"
            out.append(g)
        if "responsibility" in scored.columns:
            # registered construction: coverage_defense assignments on held-out pass snaps. The model is scored on
            # its RAW prediction (resp_model_role) — resp_role is overwritten by the charted label where one exists.
            pred = "resp_model_role" if "resp_model_role" in scored.columns else "resp_role"
            m = pl.col("has_throw")
            if "responsibility_source" in scored.columns:
                m = m & (pl.col("responsibility_source") == "coverage_defense")
            g = heldout_accuracy(scored, holdout_games, "responsibility", pred, mask=m)
            g["name"] = "G2b_heldout_responsibility"
            out.append(g)
    out.append(split_half_stability(scored, min_snaps=min_snaps))
    out.append(destruction_control(scored, min_snaps=min_snaps))
    return out


def format_gates(gates: list[dict]) -> str:
    lines = ["| gate | value | bar | n | verdict |", "|---|---|---|---|---|"]
    for g in gates:
        v = "—" if g["value"] is None else (f"{g['value']:.3f}" if isinstance(g["value"], float) else str(g["value"]))
        b = "—" if g["bar"] is None else (f"{g['bar']:.3f}" if isinstance(g["bar"], float) else str(g["bar"]))
        verdict = "—" if g["pass"] is None else ("GO" if g["pass"] else "NO-GO")
        lines.append(f"| {g['name']} | {v} | {b} | {g['n']} | {verdict} |")
    return "\n".join(lines)
