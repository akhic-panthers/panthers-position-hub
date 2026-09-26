"""`poshub verify` — Phase 1 checks on REAL frames, the ones synthetic tracking could not make.

Everything here is a plumbing check, not a result. Each block answers one question and says what a failure
would mean. Output is markdown (aggregates only) for runs/<stamp>/verify.md.

  1. frame        direction rule vs NGS Play_Direction; snapper proxy vs NGS ball at the snap; our depth vs NGS depth
  2. events       share of plays with snap / line_set / throw / handoff / end event; frames after the snap
  3. spine        join rates to pffdefense and coverage_defense, by season and by side
  4. crosstab     rule alignment role × PFF alignment family, and × NGS ngs_position (a third, independent label)
  5. bite         bite_2s by rule role on pass vs run (edges negative, deep safeties positive)
  6. sanity       depth by rule role; offense behind the line / defense in front at the snap
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from ..roles.taxonomy import ALIGN_ROLES


def _pct(v) -> str:
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.1%}"


def _q(s: pl.Series, q: float) -> float:
    v = s.drop_nulls()
    return float(v.quantile(q)) if v.len() else float("nan")


def _table(rows: list[list], header: list[str]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def frame_checks(f: pl.DataFrame) -> list[str]:
    L = ["## 1 · the standardized frame, checked against the league's own numbers", ""]
    has_ngs = "ngs_play_direction" in f.columns and f["ngs_play_direction"].is_not_null().any()
    per_play = f.unique(["game_key", "gsis_play_id"])
    L.append(f"- plays: {per_play.height:,}; ball proxy = tagged center on {_pct((per_play['ball_proxy'] == 'center').mean())}, "
             f"offensive-line median on {_pct((per_play['ball_proxy'] == 'ol_median').mean())} (no player tagged C at the snap)")
    if not has_ngs:
        L.append("- ⚠ no NGS play-level columns (run features with the Databricks source) — direction and ball checks skipped")
        return L
    p = per_play.filter(pl.col("ngs_play_direction").is_not_null())
    ours_right = p["offense_moves_right"]
    theirs_right = p["ngs_play_direction"].str.to_lowercase() == "right"
    agree = (ours_right == theirs_right)
    L.append(f"- **direction rule vs NGS Play_Direction: {_pct(agree.mean())} agree** on {p.height:,} plays"
             + ("" if agree.mean() > 0.995 else "  ⚠ below 99.5%: inspect the disagreements before anything else"))
    if (~agree).sum():
        bad = p.filter(~agree).group_by("ball_proxy").len().sort("len", descending=True)
        L.append("  - disagreements by ball proxy: " + ", ".join(f"{r['ball_proxy']} {r['len']}" for r in bad.iter_rows(named=True)))
    # snapper proxy vs the ball: offset along the play direction (positive = ball is in FRONT of the snapper, toward the defense)
    p = p.filter(pl.col("ngs_x_ball_at_snap").is_not_null())
    sgn = pl.when(pl.col("offense_moves_right")).then(1.0).otherwise(-1.0)
    p = p.with_columns(((pl.col("ngs_x_ball_at_snap") - pl.col("proxy_raw_x")) * sgn).alias("ball_ahead_of_proxy"),
                       ((pl.col("ngs_y_ball_at_snap") - pl.col("proxy_raw_y")) * sgn).alias("ball_lateral_of_proxy"))
    for proxy, g in p.group_by("ball_proxy", maintain_order=True):
        a, b = g["ball_ahead_of_proxy"], g["ball_lateral_of_proxy"]
        L.append(f"- ball vs {proxy[0]} proxy (n={g.height:,}): along-field offset median {_q(a, .5):+.2f} yd (IQR {_q(a, .25):+.2f}…{_q(a, .75):+.2f}), "
                 f"lateral median {_q(b, .5):+.2f} yd (IQR {_q(b, .25):+.2f}…{_q(b, .75):+.2f}); |along| > 1.5 yd on {_pct((a.abs() > 1.5).mean())}")
    # our depth vs NGS depth_from_los_at_snap, per defender-snap
    d = f.filter(pl.col("ngs_depth_from_los_at_snap").is_not_null()).with_columns((pl.col("depth") - pl.col("ngs_depth_from_los_at_snap")).alias("dd"))
    L.append(f"- our depth (from the snapper) minus NGS depth_from_los_at_snap: median {_q(d['dd'], .5):+.2f} yd, IQR {_q(d['dd'], .25):+.2f}…{_q(d['dd'], .75):+.2f}, "
             f"|diff| > 2 yd on {_pct((d['dd'].abs() > 2).mean())} of {d.height:,} defender-snaps (expected: a constant ≈ +0.5–0.8, the snapper's body behind the ball)")
    # raw coordinate identity: same player, same play → NGS x_at_snap should equal our raw x at the snap frame
    r = f.filter(pl.col("ngs_x_at_snap").is_not_null()).with_columns(
        ((pl.col("raw_x_snap") - pl.col("ngs_x_at_snap")) ** 2 + (pl.col("raw_y_snap") - pl.col("ngs_y_at_snap")) ** 2).sqrt().alias("dxy"))
    L.append(f"- join identity: distance between our raw snap position and NGS x_at_snap/y_at_snap — median {_q(r['dxy'], .5):.2f} yd, "
             f"> 1 yd on {_pct((r['dxy'] > 1).mean())} (a snap-frame disagreement of one or two frames, not a wrong player, if small)")
    return L


def event_checks(f: pl.DataFrame) -> list[str]:
    L = ["", "## 2 · events", ""]
    p = f.unique(["game_key", "gsis_play_id"])
    cols = [("has_line_set", "line_set before the snap"), ("has_throw", "pass_forward"), ("has_handoff", "handoff"), ("has_end_event", "an end event")]
    L.append(f"- plays with a snap event that reached this table: {p.height:,} (plays without `ball_snap`/`snap_direct` never get a row; see the features log for the play spine)")
    for c, lab in cols:
        if c in p.columns:
            L.append(f"- {lab}: {_pct(p[c].mean())} of plays")
    if "is_pass" in p.columns:
        pp = p.filter(pl.col("is_pass") == True)  # noqa: E712
        L.append(f"- PFF pass plays with a pass_forward event: {_pct(pp['has_throw'].mean())} of {pp.height:,} (sacks, scrambles and throwaways legitimately lack one)")
        rr = p.filter(pl.col("is_run") == True) if "is_run" in p.columns else pl.DataFrame()  # noqa: E712
        if rr.height:
            L.append(f"- PFF run plays with a handoff event: {_pct(rr['has_handoff'].mean())} of {rr.height:,} (QB keepers and direct snaps lack one)")
    if "frames_after_snap" in p.columns:
        L.append(f"- frames after the snap: median {_q(p['frames_after_snap'].cast(pl.Float64), .5):.0f}, < 20 (no 2 s window) on {_pct((p['frames_after_snap'] < 20).mean())}")
    return L


def spine_checks(f: pl.DataFrame) -> list[str]:
    L = ["", "## 3 · the join spine (game_key, gsis_play_id, nfl_id)", ""]
    rows = []
    for s, g in f.group_by("season", maintain_order=True):
        pas = g.filter(pl.col("is_pass") == True) if "is_pass" in g.columns else g  # noqa: E712
        rows.append([s[0], f"{g.height:,}", _pct(g["pff_alignment"].is_not_null().mean()), _pct(pas["responsibility"].is_not_null().mean()),
                     _pct(g["ngs_role"].is_not_null().mean()) if "ngs_role" in g.columns else "—"])
    L += _table(rows, ["season", "defender-snaps", "→ pffdefense", "pass snaps → coverage_defense", "→ NGS player_play"])
    miss = f.filter(pl.col("pff_alignment").is_null())
    if miss.height:
        by_pos = miss.group_by("ngs_position").len().sort("len", descending=True).head(6)
        L.append(f"- defender-snaps without a pffdefense row: {miss.height:,}; by NGS position: " + ", ".join(f"{r['ngs_position']} {r['len']}" for r in by_pos.iter_rows(named=True)))
        per_play_miss = miss.group_by("game_key", "gsis_play_id").len()
        L.append(f"  - on {per_play_miss.height:,} plays; plays where ALL our defenders miss (PFF has no defense rows for the play, e.g. a penalty no-play): "
                 f"{per_play_miss.filter(pl.col('len') >= 11).height:,}")
    if "ngs_role" in f.columns:
        n11 = f.group_by("game_key", "gsis_play_id").len()
        L.append(f"- defenders per play in tracking: 11 on {_pct((n11['len'] == 11).mean())}, 10 or fewer on {_pct((n11['len'] < 11).mean())}, 12+ on {_pct((n11['len'] > 11).mean())}")
    return L


def crosstab_checks(f: pl.DataFrame) -> list[str]:
    L = ["", "## 4 · rule alignment role × charted labels (row %, n)", ""]
    fold = {"DEEP_HALF": "DEEP_SAFETY", "DEEP_MIDDLE": "DEEP_SAFETY"}
    for label_col, title in (("pff_align_family", "PFF alignment family (`pff_POSITION` → family)"), ("ngs_align_family", "NGS ngs_position → family")):
        if label_col not in f.columns or not f[label_col].is_not_null().any():
            continue
        g = f.filter(pl.col(label_col).is_not_null())
        fams = sorted(g[label_col].unique().to_list())
        rows = []
        for role in ALIGN_ROLES:
            r = g.filter(pl.col("rule_align_role") == role)
            if not r.height:
                continue
            vc = dict(r[label_col].value_counts().iter_rows())
            rows.append([role, f"{r.height:,}"] + [f"{vc.get(fm, 0) / r.height:.0%}" if vc.get(fm, 0) / r.height >= 0.005 else "·" for fm in fams])
        L += [f"**{title}**", ""] + _table(rows, ["rule role", "n"] + fams)
        mine = g["rule_align_role"].replace_strict(fold, default=None).fill_null(g["rule_align_role"])
        agree = (mine == g[label_col]) | ((mine == "OVERHANG") & g[label_col].is_in(["OFF_BALL_LB", "EDGE", "BOX_SAFETY"]))
        L += ["", f"- top-1 agreement (safety depth classes folded, OVERHANG accepted as LB/EDGE/BOX_SAFETY): **{_pct(agree.mean())}** on {g.height:,}", ""]
    return L


def bite_checks(f: pl.DataFrame) -> list[str]:
    L = ["", "## 5 · bite at 2 s by rule role (yards; negative = toward the line)", ""]
    if "bite_2s" not in f.columns:
        return L + ["- no bite_2s column"]
    rows = []
    for role in ALIGN_ROLES:
        r = f.filter((pl.col("rule_align_role") == role) & pl.col("bite_2s").is_not_null())
        if not r.height:
            continue
        pas = r.filter(pl.col("is_pass") == True) if "is_pass" in r.columns else r  # noqa: E712
        run = r.filter(pl.col("is_run") == True) if "is_run" in r.columns else r.clear()  # noqa: E712
        rows.append([role, f"{r.height:,}", f"{_q(pas['bite_2s'], .5):+.1f}", f"{_q(pas['bite_2s'], .25):+.1f}…{_q(pas['bite_2s'], .75):+.1f}",
                     f"{_q(run['bite_2s'], .5):+.1f}" if run.height else "—", f"{_q(r['ground_covered_2s'], .5):.1f}"])
    L += _table(rows, ["rule role", "n", "pass: median bite", "pass: IQR", "run: median bite", "ground covered 2 s (median)"])
    return L


def sanity_checks(f: pl.DataFrame) -> list[str]:
    L = ["", "## 6 · depth by rule role (yards from the snapper)", ""]
    rows = []
    for role in ALIGN_ROLES:
        r = f.filter(pl.col("rule_align_role") == role)
        if r.height:
            rows.append([role, f"{r.height:,}", f"{_q(r['depth'], .05):.1f}", f"{_q(r['depth'], .5):.1f}", f"{_q(r['depth'], .95):.1f}", f"{_q(r['abs_lateral'], .5):.1f}"])
    L += _table(rows, ["rule role", "n", "depth p5", "median", "p95", "|lateral| median"])
    neg = f.filter(pl.col("depth") < -0.5)
    L.append(f"- defenders standardised BEHIND the line at the snap (depth < −0.5): {neg.height:,} ({_pct(neg.height / max(f.height, 1))}) — a few are real (a corner over a stacked release), many would mean a flipped play")
    return L


def verify(features_path: Path, out_md: Path, title: str = "") -> str:
    f = pl.read_parquet(features_path)
    L = [f"# verify · {title or features_path}", "", f"{f.height:,} defender-snaps · {f.unique(['game_key', 'gsis_play_id']).height:,} plays · "
         f"{f['game_key'].n_unique()} games · seasons {sorted(f['season'].unique().to_list()) if 'season' in f.columns else '?'}", ""]
    L += frame_checks(f) + event_checks(f) + spine_checks(f) + crosstab_checks(f) + bite_checks(f) + sanity_checks(f)
    md = "\n".join(L) + "\n"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md)
    return md
