"""Phase 3 extensions — each registered in docs/REGISTERED_phase3_extensions.md BEFORE it was run on the population.

    E1  GCOE / BDUE (Eager & Seth 2023) rebuilt on 2022–2025 — per-play descriptors, never a leaderboard
    E2  disguise: shown vs played middle-of-field from the safeties' movement
    E3  zone-match detector: MAN_MATCH vs spot-drop on charted zone calls
    E4  offensive alignment roles vs PFF's offensive slot
    E5  team shell mix and each safety's mix conditional on the call

Every function returns (gate dicts, markdown lines). Rows never leave this module except as aggregates.
"""
from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from ..roles.model import ALIGN_FEATURES, RESP_FEATURES, _matrix

PAPER_BOX_SLOTS = ["MLB", "LILB", "RILB", "LLB", "RLB", "SS", "SSL", "SSR"]
TRACKING_BOX_ROLES = ["OFF_BALL_LB", "BOX_SAFETY", "OVERHANG"]


def _gate(name, value, bar, passed, n, note=""):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        passed = None                    # not computable is not a NO-GO; the table says "—" and the note says why
    return {"name": name, "value": value, "bar": bar, "pass": passed, "n": n, "note": note}


def _corr(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < 5 or a[m].std() == 0 or b[m].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1])


def _cat_codes(df: pl.DataFrame, cols: list[str]) -> np.ndarray:
    out = np.full((df.height, len(cols)), np.nan)
    for j, c in enumerate(cols):
        if c in df.columns:
            s = df.get_column(c).cast(pl.Utf8).fill_null("")
            codes = s.cast(pl.Categorical).to_physical().cast(pl.Float64).to_numpy()
            out[:, j] = codes
    return out


def _oof(df: pl.DataFrame, num: list[str], cat: list[str], y: np.ndarray, groups: np.ndarray, classifier: bool = False,
         n_splits: int = 10, seed: int = 0) -> np.ndarray:
    """Out-of-fold predictions, folds by GROUP (week or game), never by row."""
    X = np.hstack([_matrix(df, num), _cat_codes(df, cat)]) if cat else _matrix(df, num)
    catmask = [False] * len(num) + [True] * len(cat)
    pred = np.full(len(y), np.nan)
    k = min(n_splits, len(np.unique(groups)))
    if k < 2:
        return pred
    for tr, te in GroupKFold(n_splits=k).split(X, y, groups):
        if classifier:
            m = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                               categorical_features=catmask if cat else None, random_state=seed)
            m.fit(X[tr], y[tr])
            pred[te] = m.predict_proba(X[te])[:, list(m.classes_).index(1)] if 1 in m.classes_ else 0.0
        else:
            m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                              categorical_features=catmask if cat else None, random_state=seed)
            m.fit(X[tr], y[tr])
            pred[te] = m.predict(X[te])
    return pred


def _null_oof(y: np.ndarray, groups: np.ndarray, n_splits: int = 10) -> np.ndarray:
    pred = np.full(len(y), np.nan)
    k = min(n_splits, len(np.unique(groups)))
    if k < 2:
        return pred
    for tr, te in GroupKFold(n_splits=k).split(y, y, groups):
        pred[te] = y[tr].mean()
    return pred


# ── E1 · GCOE / BDUE ─────────────────────────────────────────────────────────────────────────────────────────
E1_NUM = ["depth", "lateral", "carrier_x_snap", "carrier_y_snap", "pff_BOXPLAYERS_n", "pff_DOWN", "pff_DISTANCE_n", "is_blitz",
          "is_rpo", "n_deep", "n_box", "tackle_half_width"]
E1_CAT = ["pff_alignment", "pff_RUNCONCEPTPRIMARY", "pff_RBDIRECTION", "pff_DROPBACKTYPE", "pff_DEFPERSONNEL", "pff_SHOTGUN"]


def _prep_e1(s: pl.DataFrame) -> pl.DataFrame:
    return s.with_columns(pl.col("pff_BOXPLAYERS").cast(pl.Utf8).str.extract(r"(\d+)").cast(pl.Float64, strict=False).alias("pff_BOXPLAYERS_n")
                          if "pff_BOXPLAYERS" in s.columns else pl.lit(None, pl.Float64).alias("pff_BOXPLAYERS_n"),
                          pl.col("pff_DISTANCE").cast(pl.Float64, strict=False).alias("pff_DISTANCE_n")
                          if "pff_DISTANCE" in s.columns else pl.lit(None, pl.Float64).alias("pff_DISTANCE_n"),
                          (pl.col("season") * 100 + pl.col("week")).alias("_wk"))


def _one_response(pop: pl.DataFrame, response: str, label: str) -> tuple[pl.DataFrame, dict]:
    pop = pop.filter(pl.col(response).is_not_null() & pl.col(response).is_finite())
    y = pop.get_column(response).to_numpy().astype(float)
    g = pop.get_column("_wk").to_numpy()
    if len(np.unique(g)) < 2:          # one week only (smoke runs): fold by game instead; the full run folds by week
        g = pop.get_column("game_key").to_numpy()
    pred = _oof(pop, E1_NUM, E1_CAT, y, g)
    null = _null_oof(y, g)
    rmse = float(np.sqrt(np.nanmean((y - pred) ** 2)))
    rmse0 = float(np.sqrt(np.nanmean((y - null) ** 2)))
    return pop.with_columns(pl.Series(f"exp_{label}", pred), pl.Series(f"oe_{label}", y - pred)), {"rmse": rmse, "null_rmse": rmse0, "n": len(y)}


def _yoy(per: pl.DataFrame, col: str, min_n: int) -> tuple[float, int]:
    p = per.filter(pl.col("n") >= min_n)
    nxt = p.with_columns((pl.col("season") - 1).alias("season"))
    j = p.join(nxt, on=["nfl_id", "season"], suffix="_next")
    return _corr(j[col].to_numpy(), j[f"{col}_next"].to_numpy()), j.height


def e1_over_expected(scored: pl.DataFrame, seed: int = 0) -> tuple[list[dict], list[str], pl.DataFrame]:
    s = _prep_e1(scored)
    gates, L, per_play = [], ["## E1 · ground covered over expected (GCOE) and bite distance under expected (BDUE)", ""], []
    arms = {"paper slots (PFF MLB/ILB/LB/SS on the snap)": pl.col("pff_alignment").is_in(PAPER_BOX_SLOTS),
            "tracking roles (off-ball backer / box safety / overhang)": pl.col("align_role").is_in(TRACKING_BOX_ROLES)}
    rows = []
    for arm, mask in arms.items():
        runs = s.filter(mask & (pl.col("is_run") == True) & pl.col("has_handoff"))  # noqa: E712
        pa = s.filter(mask & (pl.col("is_pass") == True) & (pl.col("is_play_action") == True))  # noqa: E712
        gr, gstat = _one_response(runs, "closed_on_carrier_2s", "gc")
        br, bstat = _one_response(pa, "bite_2s", "bite")
        per_g = gr.group_by("nfl_id", "season").agg(pl.len().alias("n"), pl.col("oe_gc").mean().alias("gcoe"),
                                                   pl.col("player_name").drop_nulls().first(), pl.col("defense_team").mode().first().alias("team"))
        per_b = br.group_by("nfl_id", "season").agg(pl.len().alias("n"), pl.col("oe_bite").mean().alias("bdue"))
        r_g, n_g = _yoy(per_g, "gcoe", 200)
        r_b, n_b = _yoy(per_b, "bdue", 75)
        both = per_g.filter(pl.col("n") >= 200).join(per_b.filter(pl.col("n") >= 75), on=["nfl_id", "season"], suffix="_b")
        r_gb = _corr(both["gcoe"].to_numpy(), both["bdue"].to_numpy())
        # destruction: shuffle per-play residuals across players within (season, team), recompute year-to-year
        rng = np.random.default_rng(seed)
        parts = []
        for _, grp in gr.group_by("season", "defense_team"):
            parts.append(grp.with_columns(pl.Series("oe_gc", rng.permutation(grp["oe_gc"].to_numpy()))))
        sh = pl.concat(parts).group_by("nfl_id", "season").agg(pl.len().alias("n"), pl.col("oe_gc").mean().alias("gcoe"))
        r_null, _ = _yoy(sh, "gcoe", 200)
        tag = "paper" if arm.startswith("paper") else "tracking"
        gates += [
            _gate(f"E1a_GCOE_rmse_{tag}", gstat["rmse"], 0.90 * gstat["null_rmse"], gstat["rmse"] <= 0.90 * gstat["null_rmse"], gstat["n"],
                  f"null {gstat['null_rmse']:.2f}; paper 2.47 vs 3.76"),
            _gate(f"E1a_BDUE_rmse_{tag}", bstat["rmse"], 0.90 * bstat["null_rmse"], bstat["rmse"] <= 0.90 * bstat["null_rmse"], bstat["n"],
                  f"null {bstat['null_rmse']:.2f}; paper 2.23 vs 2.96"),
            _gate(f"E1b_GCOE_yoy_{tag}", r_g, 0.30, bool(r_g >= 0.30), n_g, "paper 0.66 (≥ 200 run snaps)"),
            _gate(f"E1b_BDUE_yoy_{tag}", r_b, 0.30, bool(r_b >= 0.30), n_b, "paper 0.57 (≥ 75 play-action snaps)"),
            _gate(f"E1_destruction_{tag}", r_null, f"< 0.5 × {r_g:.2f}", bool(r_null < 0.5 * r_g) if not np.isnan(r_g) else None, n_g,
                  "GCOE residuals shuffled across players within team-season"),
        ]
        rows.append([arm, f"{gstat['n']:,}", f"{gstat['rmse']:.2f} / {gstat['null_rmse']:.2f}", f"{r_g:.2f} (n={n_g})",
                     f"{bstat['n']:,}", f"{bstat['rmse']:.2f} / {bstat['null_rmse']:.2f}", f"{r_b:.2f} (n={n_b})", f"{r_gb:.2f} (n={both.height})",
                     f"{r_null:.2f}"])
        per_play.append(gr.select("game_key", "gsis_play_id", "nfl_id", "season", "exp_gc", "oe_gc").with_columns(pl.lit(tag).alias("arm")))
        per_play.append(br.select("game_key", "gsis_play_id", "nfl_id", "season", "exp_bite", "oe_bite").with_columns(pl.lit(tag).alias("arm")))
    L += ["| population | run snaps | GCOE RMSE / null | GCOE year-to-year | PA snaps | bite RMSE / null | BDUE year-to-year | GCOE × BDUE within season | GCOE year-to-year, shuffled |",
          "|---|---|---|---|---|---|---|---|---|"]
    L += ["| " + " | ".join(r) + " |" for r in rows]
    L += ["", "Paper (2017–2021): GCOE RMSE 2.47 vs null 3.76, year-to-year 0.66; BDUE RMSE 2.23 vs null 2.96, year-to-year 0.57; "
          "GCOE × BDUE −0.40. Residuals ship as per-play descriptors. No season ranking is produced."]
    return gates, L, pl.concat(per_play, how="diagonal_relaxed") if per_play else pl.DataFrame()


# ── E2 · disguise ────────────────────────────────────────────────────────────────────────────────────────────
def e2_disguise(scored: pl.DataFrame, seed: int = 0) -> tuple[list[dict], list[str]]:
    L = ["", "## E2 · disguise — the shell shown vs the shell played", ""]
    s = scored.filter(pl.col("pff_MOFOCSHOWN").is_in(["O", "C"]) & pl.col("pff_MOFOCPLAYED").is_in(["O", "C"]))
    s = s.with_columns((pl.col("depth_2s") >= 10.0).alias("_deep2"), (pl.col("depth_line_set") >= 10.0).alias("_deep_ls"),
                       (pl.col("depth_2s") - pl.col("depth")).alias("_d_post"), (pl.col("depth") - pl.col("depth_line_set")).alias("_d_pre"))
    play = s.group_by("game_key", "gsis_play_id").agg(
        pl.col("pff_MOFOCSHOWN").first(), pl.col("pff_MOFOCPLAYED").first(), pl.col("season").first(),
        pl.col("n_deep").first(), pl.col("n_deep_line_set").first().cast(pl.Float64), pl.col("_deep2").sum().alias("n_deep_2s"),
        pl.col("_d_pre").filter(pl.col("depth") >= 7).abs().max().alias("max_pre_move_safety"),
        pl.col("_d_post").filter(pl.col("depth") >= 7).min().alias("most_down_post_safety"),
        pl.col("_d_post").filter(pl.col("depth") >= 7).max().alias("most_up_post_safety"),
        pl.col("depth").filter(pl.col("depth_rank") <= 2).min().alias("second_deepest"))
    play = play.with_columns((pl.col("pff_MOFOCSHOWN") != pl.col("pff_MOFOCPLAYED")).cast(pl.Int8).alias("y"))
    y = play["y"].to_numpy()
    g = play["game_key"].to_numpy()
    base = ["n_deep", "second_deepest"]
    treat = base + ["n_deep_line_set", "n_deep_2s", "max_pre_move_safety", "most_down_post_safety", "most_up_post_safety"]
    pb = _oof(play, base, [], y, g, classifier=True, seed=seed)
    pt = _oof(play, treat, [], y, g, classifier=True, seed=seed)
    ok = ~(np.isnan(pb) | np.isnan(pt))
    auc_b = float(roc_auc_score(y[ok], pb[ok])) if len(np.unique(y[ok])) == 2 else float("nan")
    auc_t = float(roc_auc_score(y[ok], pt[ok])) if len(np.unique(y[ok])) == 2 else float("nan")
    def permuted_auc(cols: list[str], rs: int) -> float:
        r = np.random.default_rng(rs)
        parts = []
        for _, grp in play.group_by("game_key"):
            perm = r.permutation(grp.height)
            parts.append(grp.with_columns([pl.Series(c, grp[c].to_numpy()[perm]) for c in cols]))
        sh = pl.concat(parts)
        pn = _oof(sh, treat, [], sh["y"].to_numpy(), sh["game_key"].to_numpy(), classifier=True, seed=seed)
        okn = ~np.isnan(pn)
        return float(roc_auc_score(sh["y"].to_numpy()[okn], pn[okn]))

    # amended 2026-09-25 before the population run: permuting only the movement features leaves the snap shell in, so
    # the null can never fall below the baseline. The gated control permutes EVERY feature within game; the
    # movement-only arm is reported beside it and should land on the baseline.
    auc_n = permuted_auc(treat, seed)
    auc_mv = permuted_auc([c for c in treat if c not in base], seed + 1)
    gates = [_gate("E2_disguise_auc", auc_t, f"≥ 0.70 and ≥ {auc_b:.3f} + 0.05", bool(auc_t >= 0.70 and auc_t >= auc_b + 0.05), play.height,
                   f"snap-only baseline {auc_b:.3f}; shown ≠ played on {y.mean():.1%} of plays"),
             _gate("E2_destruction", auc_n, "≤ 0.55 (all features permuted within game)", bool(auc_n <= 0.55), play.height,
                   f"movement-only permuted {auc_mv:.3f} (should return to the {auc_b:.3f} baseline)")]
    ct = play.group_by("pff_MOFOCSHOWN", "pff_MOFOCPLAYED").len().sort("pff_MOFOCSHOWN", "pff_MOFOCPLAYED")
    L += [f"- plays with both calls charted: {play.height:,}; shown ≠ played on {y.mean():.1%}",
          "- " + " · ".join(f"shown {r['pff_MOFOCSHOWN']} → played {r['pff_MOFOCPLAYED']}: {r['len']:,}" for r in ct.iter_rows(named=True)),
          f"- held-out-game AUC for 'shown ≠ played': snap shell only {auc_b:.3f} · + line-set shell and safety movement {auc_t:.3f} · "
          f"movement permuted {auc_mv:.3f} · everything permuted {auc_n:.3f}"]
    # safety surface: who rotates, down or up, before or after the snap
    saf = s.filter(pl.col("align_role").is_in(["DEEP_HALF", "DEEP_MIDDLE", "BOX_SAFETY"]) | (pl.col("depth_line_set") >= 8))
    saf = saf.with_columns(((pl.col("depth_2s") - pl.col("depth_line_set")) <= -3).alias("rot_down"),
                           ((pl.col("depth_2s") - pl.col("depth_line_set")) >= 3).alias("rot_up"),
                           (pl.col("_d_pre").abs() >= 3).alias("rot_presnap"))
    per = saf.group_by("nfl_id", "season").agg(pl.len().alias("snaps"), pl.col("player_name").drop_nulls().first(),
                                               pl.col("defense_team").mode().first().alias("team"),
                                               pl.col("rot_down").mean().alias("rotated_down"), pl.col("rot_up").mean().alias("rotated_up"),
                                               (pl.col("rot_presnap") & (pl.col("rot_down") | pl.col("rot_up"))).sum().alias("_pre"),
                                               (pl.col("rot_down") | pl.col("rot_up")).sum().alias("_rot"))
    per = per.with_columns((pl.col("_pre") / pl.col("_rot")).alias("share_before_snap")).drop("_pre", "_rot")
    return gates, L, per


# ── E3 · zone-match detector ─────────────────────────────────────────────────────────────────────────────────
def e3_zone_match(scored: pl.DataFrame, seed: int = 0) -> tuple[list[dict], list[str]]:
    L = ["", "## E3 · zone-match detector (MAN_MATCH vs spot drop, on charted zone calls)", ""]
    z = scored.filter((pl.col("responsibility_source") == "coverage_defense") & pl.col("responsibility").is_in(["MAN_MATCH", "UNDER_ZONE", "DEEP_ZONE"])
                      & pl.col("bite_2s").is_not_null())
    y = (z["responsibility"] == "MAN_MATCH").cast(pl.Int8).to_numpy()
    g = z["game_key"].to_numpy()
    pb = _oof(z, ALIGN_FEATURES, [], y, g, classifier=True, seed=seed)
    pt = _oof(z, RESP_FEATURES, [], y, g, classifier=True, seed=seed)
    auc_b, auc_t = float(roc_auc_score(y, pb)), float(roc_auc_score(y, pt))
    rng = np.random.default_rng(seed)
    ys = y.copy()
    for gk in np.unique(g):
        idx = np.where(g == gk)[0]
        ys[idx] = rng.permutation(ys[idx])
    pn = _oof(z, RESP_FEATURES, [], ys, g, classifier=True, seed=seed)
    auc_n = float(roc_auc_score(ys, pn))
    gates = [_gate("E3_zone_match_auc", auc_t, f"≥ 0.70 and ≥ {auc_b:.3f} + 0.05", bool(auc_t >= 0.70 and auc_t >= auc_b + 0.05), len(y),
                   f"pre-snap baseline {auc_b:.3f}; MAN_MATCH base rate {y.mean():.1%}"),
             _gate("E3_destruction", auc_n, "≤ 0.55 (label shuffled within game)", bool(auc_n <= 0.55), len(y), "")]
    L += [f"- charted zone reps: {len(y):,}; pattern-matched (MAT/SEA/CAR/TAM) {y.mean():.1%}",
          f"- held-out-game AUC: pre-snap alignment only {auc_b:.3f} · + post-snap geometry {auc_t:.3f} · shuffled {auc_n:.3f}"]
    return gates, L


# ── E4 · offensive alignment roles ───────────────────────────────────────────────────────────────────────────
PFF_OFF_FOLD = {"LWR": "WIDE", "RWR": "WIDE", "SLWR": "SLOT", "SRWR": "SLOT", "SLoWR": "SLOT", "SLiWR": "SLOT", "SRoWR": "SLOT",
                "SRiWR": "SLOT", "TE-L": "INLINE_TE", "TE-R": "INLINE_TE", "TE-oL": "WING", "TE-oR": "WING", "TE-iL": "WING",
                "TE-iR": "WING", "HB": "BACKFIELD", "HB-L": "BACKFIELD", "HB-R": "BACKFIELD", "FB": "BACKFIELD", "FB-L": "BACKFIELD",
                "FB-R": "BACKFIELD", "FB-iR": "BACKFIELD", "FB-iL": "BACKFIELD"}
OFF_ROLES = ["X", "Z", "SLOT", "WING", "INLINE_TE", "BACKFIELD"]


def offense_role(r: dict) -> str:
    if r.get("in_backfield"):
        return "BACKFIELD"
    ob = r["outside_tackle_by"]
    on = bool(r.get("on_line"))
    if (on and ob <= 2.0) or (not on and r["x_snap"] < -4.0 and ob <= 3.0):
        return "INLINE_TE" if on else "BACKFIELD"
    if not on and ob <= 3.0:
        return "WING"
    if (r.get("rec_num") or 1) == 1:
        return "X" if on else "Z"
    return "SLOT"


def e4_offense_roles(off: pl.DataFrame, pff_off: pl.DataFrame) -> tuple[list[dict], list[str], pl.DataFrame]:
    L = ["", "## E4 · offensive alignment roles (X / Z / slot / wing / inline TE / backfield)", ""]
    o = off.with_columns(pl.Series("off_role", [offense_role(r) for r in off.iter_rows(named=True)], dtype=pl.Utf8))
    if pff_off.height:
        o = o.join(pff_off, on=["game_key", "gsis_play_id", "nfl_id"], how="left")
        o = o.with_columns(pl.col("pff_off_position").replace_strict(PFF_OFF_FOLD, default=None).alias("pff_off_family"))
        c = o.filter(pl.col("pff_off_family").is_not_null())
        mine = c["off_role"].replace({"X": "WIDE", "Z": "WIDE"})
        agree = float((mine == c["pff_off_family"]).mean())
        gates = [_gate("E4_offense_agreement", agree, 0.85, bool(agree >= 0.85), c.height, "X/Z folded to WIDE; PFF does not chart on/off the line")]
        fams = ["WIDE", "SLOT", "WING", "INLINE_TE", "BACKFIELD"]
        L += ["| rule role | n | " + " | ".join(fams) + " |", "|---|---|" + "---|" * len(fams)]
        for role in OFF_ROLES:
            r = c.filter(pl.col("off_role") == role)
            if r.height:
                vc = dict(r["pff_off_family"].value_counts().iter_rows())
                L.append(f"| {role} | {r.height:,} | " + " | ".join(f"{vc.get(f, 0) / r.height:.0%}" for f in fams) + " |")
        L += ["", f"- top-1 agreement with PFF's offensive slot (X/Z folded): **{agree:.1%}** on {c.height:,} skill-player snaps"]
    else:
        gates = [_gate("E4_offense_agreement", None, 0.85, None, 0, "pffoffense not loaded")]
    return gates, L, o


# ── E5 · team shells and each safety's mix conditional on the call ───────────────────────────────────────────
def e5_team_and_call(scored: pl.DataFrame, min_snaps: int = 200) -> tuple[list[str], pl.DataFrame, pl.DataFrame]:
    L = ["", "## E5 · shell mix, and how much of a safety's mix the call explains", ""]
    plays = scored.unique(["game_key", "gsis_play_id"]).filter(pl.col("pff_DOWN").is_not_null())
    plays = plays.with_columns(pl.when(pl.col("pff_DOWN") == 3).then(pl.lit("3rd down")).when(pl.col("pff_DOWN") == 4).then(pl.lit("4th down"))
                               .otherwise(pl.lit("1st/2nd down")).alias("down_group"),
                               pl.col("pff_DISTANCE").cast(pl.Float64, strict=False).alias("_dist"))
    plays = plays.with_columns(pl.when(pl.col("_dist") <= 3).then(pl.lit("short (1–3)")).when(pl.col("_dist") <= 7).then(pl.lit("medium (4–7)"))
                               .otherwise(pl.lit("long (8+)")).alias("distance_group"))
    shell = (plays.group_by("defense_team", "season", "down_group", "distance_group")
             .agg(pl.len().alias("plays"), (pl.col("n_deep") <= 1).mean().alias("one_high_or_zero"), (pl.col("n_deep") >= 2).mean().alias("two_high"),
                  (pl.col("pff_MOFOCPLAYED") == "O").mean().alias("pff_played_open")).filter(pl.col("plays") >= 100))
    # safeties: per-snap deep probability, split by the charted call
    saf = scored.filter(pl.col("peer_group_hint") == "S") if "peer_group_hint" in scored.columns else scored.filter(pl.col("ngs_position").is_in(["FS", "SS", "S", "SAF"]))
    saf = saf.filter(pl.col("pff_MOFOCPLAYED").is_in(["O", "C"])).with_columns(
        (pl.col("p_align_DEEP_HALF") + pl.col("p_align_DEEP_MIDDLE")).alias("p_deep"))
    rows = []
    for key, g in saf.group_by("nfl_id", "season"):
        if g.height < min_snaps:
            continue
        tot = float(g["p_deep"].var() or 0.0)
        within = sum(float(gg["p_deep"].var() or 0.0) * (gg.height - 1) for _, gg in g.group_by("pff_MOFOCPLAYED")) / max(g.height - 1, 1)
        byc = {k[0]: gg for k, gg in g.group_by("pff_MOFOCPLAYED")}
        rows.append({"nfl_id": key[0], "season": key[1], "player_name": g["player_name"].drop_nulls().first(),
                     "team": g["defense_team"].mode().first(), "snaps": g.height,
                     "deep_share_one_high": float(byc["C"]["p_deep"].mean()) if "C" in byc else None,
                     "deep_share_two_high": float(byc["O"]["p_deep"].mean()) if "O" in byc else None,
                     "middle_share_one_high": float(byc["C"]["p_align_DEEP_MIDDLE"].mean()) if "C" in byc else None,
                     "box_share_one_high": float(byc["C"]["p_align_BOX_SAFETY"].mean()) if "C" in byc else None,
                     "call_explains": 1.0 - within / tot if tot > 0 else None})
    call = pl.DataFrame(rows) if rows else pl.DataFrame()
    if call.height:
        ce = call["call_explains"].drop_nulls()
        L += [f"- safeties with ≥ {min_snaps} charted snaps: {call.height}; share of the variance in their per-snap deep probability that the "
              f"one-high / two-high call explains: median {ce.median():.0%}, IQR {ce.quantile(.25):.0%}–{ce.quantile(.75):.0%}; "
              f"≥ 50% for {(ce >= 0.5).mean():.0%} of them",
              "- where the call explains most of a safety's mix, his mix is a TEAM fact (what the coordinator called), and the viewer says so"]
    return L, shell, call
