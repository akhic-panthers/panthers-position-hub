"""Per-defender features for one play: where he lined up, what he did in the first two seconds.

Every number is in the standardized frame (see standardize.py): for a defender, `depth` is yards
off the ball toward his own end zone, `lateral` is yards from the ball (+ = defense's right).
Feature names ending in `_2s` are measured 20 frames (2.0 s) after the snap — the paper's window
(Eager & Seth 2023: bite distance and ground covered at 2 s). `_thr` = at the throw when there is one.

Nothing here is a role. Roles are decided in `roles/` from these columns, so a threshold change is a
one-file edit and the feature table can be re-scored without re-reading 36 GB of tracking.
"""
from __future__ import annotations

import math

import numpy as np
import polars as pl

from ..config import FRAMES_AT_2S
from .standardize import FIELD_WIDTH, PlayFrame, standardize_play

SKILL = {"WR", "TE", "RB", "FB", "HB"}
DEEP_DEPTH = 10.0          # a defender at ≥10 yd at the snap is a deep defender (shell count)
BOX_DEPTH = 7.0            # PFF's box: first/second level, inside the tackles' width
BOX_PAD = 1.5              # yards outside the tackle that still count as the box edge


def _nearest(px: float, py: float, xs: np.ndarray, ys: np.ndarray) -> tuple[int, float]:
    if len(xs) == 0:
        return -1, float("nan")
    d = np.hypot(xs - px, ys - py)
    i = int(np.argmin(d))
    return i, float(d[i])


def _receivers(off: pl.DataFrame) -> pl.DataFrame:
    """Eligible skill players at the snap, numbered from the outside in per side (#1 = widest)."""
    r = off.filter(pl.col("position").is_in(list(SKILL)) | pl.col("position_group").is_in(list(SKILL)))
    if not r.height:
        return r.with_columns(pl.lit(None, pl.Int8).alias("rec_num"), pl.lit(None, pl.Utf8).alias("rec_side"))
    r = r.with_columns(pl.when(pl.col("y") >= 0).then(pl.lit("R")).otherwise(pl.lit("L")).alias("rec_side"))
    # backfield players (deep and near the middle) do not take a receiver number
    r = r.with_columns(((pl.col("x") < -2.5) & (pl.col("y").abs() < 4.0)).alias("in_backfield"))
    r = r.with_columns(
        pl.when(pl.col("in_backfield")).then(None)
        .otherwise(pl.col("y").abs().rank("ordinal", descending=True).over("rec_side")).cast(pl.Int8).alias("rec_num"))
    return r


def defender_features_for_play(pf: PlayFrame) -> pl.DataFrame:
    snap = pf.at(pf.snap_frame)
    off = snap.filter(pl.col("is_offense"))
    dfd = snap.filter(~pl.col("is_offense"))
    if dfd.height == 0 or off.height == 0:
        return pl.DataFrame()

    # offensive structure at the snap
    ol = off.filter(pl.col("position").is_in(["C", "G", "T", "OL", "LG", "RG", "LT", "RT", "OG", "OT"]))
    tackle_half_width = float(ol["y"].abs().max()) if ol.height >= 3 else 4.0
    rec = _receivers(off)
    rx, ry = rec["x"].to_numpy(), rec["y"].to_numpy()
    rnum = rec["rec_num"].to_numpy() if "rec_num" in rec.columns else np.array([])
    rside = rec["rec_side"].to_numpy() if "rec_side" in rec.columns else np.array([])
    rid = rec["nfl_id"].to_numpy()
    te_mask = (rec["position"] == "TE").to_numpy() if rec.height else np.array([], bool)
    # strength = side with more eligible receivers (ties → side of the tight end, else right)
    n_r = int((ry >= 0).sum()) if rec.height else 0
    n_l = int((ry < 0).sum()) if rec.height else 0
    if n_r != n_l:
        strong_side = "R" if n_r > n_l else "L"
    elif te_mask.any():
        strong_side = "R" if float(np.mean(ry[te_mask])) >= 0 else "L"
    else:
        strong_side = "R"

    # team-level shell at the snap
    depths = dfd["x"].to_numpy()
    n_deep = int((depths >= DEEP_DEPTH).sum())
    n_on_line = int((depths <= 1.5).sum())
    box_mask = (depths <= BOX_DEPTH) & (np.abs(dfd["y"].to_numpy()) <= tackle_half_width + BOX_PAD)
    n_box = int(box_mask.sum())

    # frames we read
    f2 = pf.snap_frame + FRAMES_AT_2S
    at2 = pf.at(f2)
    if at2.height == 0:                       # short play: use the last frame available
        f2 = int(pf.frames["frame_id"].max())
        at2 = pf.at(f2)
    at_thr = pf.at(pf.throw_frame) if pf.throw_frame is not None else None
    at_ls = pf.at(pf.line_set_frame) if pf.line_set_frame is not None else None
    carrier2 = at2.filter(pl.col("nfl_id") == pf.ball_carrier_id) if pf.ball_carrier_id else None
    qb2 = at2.filter(pl.col("nfl_id") == pf.qb_id) if pf.qb_id else None
    rec2 = at2.filter(pl.col("nfl_id").is_in(rid.tolist())) if rec.height else None

    rows = []
    depth_rank = dfd["x"].rank("ordinal", descending=True).to_numpy()  # 1 = deepest
    for i, r in enumerate(dfd.iter_rows(named=True)):
        px, py = float(r["x"]), float(r["y"])
        j, dist_rec = _nearest(px, py, rx, ry)
        over = None
        if j >= 0 and len(rnum):
            v = rnum[j]
            if v is not None:
                fv = float(v)
                if not math.isnan(fv):
                    over = int(fv)
        over_side = str(rside[j]) if j >= 0 else None
        lat_to_rec = float(py - ry[j]) if j >= 0 else float("nan")
        cushion = float(px - rx[j]) if j >= 0 else float("nan")
        raw_y = float(r["raw_y"])
        row = {
            "game_key": pf.game_key, "gsis_play_id": pf.gsis_play_id, "nfl_id": int(r["nfl_id"]),
            "player_name": r.get("player_name"), "ngs_position": r.get("position"), "team_id": r.get("team_id"),
            "defense_team": pf.defense_team, "offense_team": pf.offense_team,
            # pre-snap geometry
            "depth": px, "lateral": py, "abs_lateral": abs(py),
            "sideline_dist": float(min(raw_y, FIELD_WIDTH - raw_y)),
            "on_line": px <= 1.5, "in_box": bool(box_mask[i]),
            "outside_tackle": abs(py) > tackle_half_width + BOX_PAD,
            "tackle_half_width": tackle_half_width,
            "depth_rank": int(depth_rank[i]), "is_deep": px >= DEEP_DEPTH,
            "n_deep": n_deep, "n_box": n_box, "n_on_line": n_on_line,
            "strong_side": strong_side, "on_strong_side": (py >= 0) == (strong_side == "R"),
            "dist_nearest_rec": dist_rec, "over_rec_num": over, "over_rec_side": over_side,
            "lat_to_nearest_rec": lat_to_rec, "cushion_nearest_rec": cushion,
            "nearest_rec_is_te": bool(te_mask[j]) if j >= 0 and len(te_mask) else False,
            "nearest_rec_detached": bool(abs(ry[j]) > tackle_half_width + 1.0) if j >= 0 else False,
            "speed_snap": float(r["s"]) if r["s"] is not None else float("nan"),
            "orient_snap": float(r["o"]) if r["o"] is not None else float("nan"),
        }
        # pre-snap movement (rotation / disguise): line_set → snap
        if at_ls is not None:
            ls = at_ls.filter(pl.col("nfl_id") == r["nfl_id"])
            if ls.height:
                row["depth_line_set"] = float(ls["x"][0])
                row["presnap_depth_change"] = px - float(ls["x"][0])
                row["presnap_lateral_change"] = py - float(ls["y"][0])
        # 2 s after the snap
        p2 = at2.filter(pl.col("nfl_id") == r["nfl_id"])
        if p2.height:
            x2, y2 = float(p2["x"][0]), float(p2["y"][0])
            row.update({
                "depth_2s": x2, "lateral_2s": y2,
                "bite_2s": x2 - px,                       # negative = toward the line (the paper's "bite")
                "lateral_move_2s": y2 - py,
                "ground_covered_2s": math.hypot(x2 - px, y2 - py),
                "speed_2s": float(p2["s"][0]) if p2["s"][0] is not None else float("nan"),
                "crossed_los_2s": x2 < -0.5,
                "min_depth_to_2s": float(pf.frames.filter((pl.col("nfl_id") == r["nfl_id"]) & (pl.col("frame_id") >= pf.snap_frame) & (pl.col("frame_id") <= f2))["x"].min()),
            })
            if carrier2 is not None and carrier2.height:
                d_c2 = math.hypot(x2 - float(carrier2["x"][0]), y2 - float(carrier2["y"][0]))
                c_snap = snap.filter(pl.col("nfl_id") == pf.ball_carrier_id)
                d_c0 = math.hypot(px - float(c_snap["x"][0]), py - float(c_snap["y"][0])) if c_snap.height else float("nan")
                row["dist_carrier_2s"] = d_c2
                row["closed_on_carrier_2s"] = d_c0 - d_c2          # + = closed ground on the ball carrier
            if qb2 is not None and qb2.height:
                row["dist_qb_2s"] = math.hypot(x2 - float(qb2["x"][0]), y2 - float(qb2["y"][0]))
            if rec2 is not None and rec2.height and j >= 0:
                m = rec2.filter(pl.col("nfl_id") == int(rid[j]))
                if m.height:
                    row["dist_aligned_rec_2s"] = math.hypot(x2 - float(m["x"][0]), y2 - float(m["y"][0]))
                # nearest receiver at 2 s, whoever he is
                _, row["dist_nearest_rec_2s"] = _nearest(x2, y2, rec2["x"].to_numpy(), rec2["y"].to_numpy())
        # at the throw
        if at_thr is not None:
            pt = at_thr.filter(pl.col("nfl_id") == r["nfl_id"])
            if pt.height:
                xt, yt = float(pt["x"][0]), float(pt["y"][0])
                row["depth_thr"] = xt
                row["time_to_throw_s"] = (pf.throw_frame - pf.snap_frame) / 10.0
                rt = at_thr.filter(pl.col("nfl_id").is_in(rid.tolist()))
                if rt.height:
                    _, row["dist_nearest_rec_thr"] = _nearest(xt, yt, rt["x"].to_numpy(), rt["y"].to_numpy())
                if pf.qb_id:
                    qt = at_thr.filter(pl.col("nfl_id") == pf.qb_id)
                    if qt.height:
                        row["dist_qb_thr"] = math.hypot(xt - float(qt["x"][0]), yt - float(qt["y"][0]))
        row["ball_proxy"] = pf.ball_proxy
        row["has_throw"] = pf.throw_frame is not None
        row["has_handoff"] = pf.handoff_frame is not None
        rows.append(row)
    return pl.DataFrame(rows)


def defender_features_for_game(game: pl.DataFrame, play_ids: list[int] | None = None) -> pl.DataFrame:
    """Loop over plays of one loaded game (see loader.load_game)."""
    out = []
    for pid, play in game.group_by("gsis_play_id", maintain_order=True):
        pid = pid[0] if isinstance(pid, tuple) else pid
        if play_ids is not None and pid not in play_ids:
            continue
        pf = standardize_play(play)
        if pf is None:
            continue
        feats = defender_features_for_play(pf)
        if feats.height:
            out.append(feats)
    return pl.concat(out, how="diagonal_relaxed") if out else pl.DataFrame()
