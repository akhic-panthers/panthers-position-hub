"""Offensive skill players' paths in the first three seconds after the snap, every half second, in the standardized
frame (offense moves +x; x = yards past the line, y = yards from the ball, + = the offense's left). One row per
skill player per snap. This is the route map's input; the route NAME comes from PFF's charting, not from here.
"""
from __future__ import annotations

import polars as pl

from .features import SKILL
from .loader import load_game
from .standardize import standardize_play

OFFSETS = [5, 10, 15, 20, 25, 30]          # frames after the snap at 10 Hz: 0.5 s … 3.0 s


def offense_paths_for_game(path: str) -> pl.DataFrame:
    g = load_game(path)
    out = []
    for _, play in g.group_by("gsis_play_id", maintain_order=True):
        pf = standardize_play(play)
        if pf is None:
            continue
        f = pf.frames.filter(pl.col("is_offense") & (pl.col("position").is_in(list(SKILL)) | pl.col("position_group").is_in(list(SKILL))))
        want = [pf.snap_frame + o for o in OFFSETS]
        f = f.filter(pl.col("frame_id").is_in([pf.snap_frame] + want)).with_columns(((pl.col("frame_id") - pf.snap_frame) // 5).alias("k"))
        if not f.height:
            continue
        wide = f.pivot(on="k", index="nfl_id", values=["x", "y"], aggregate_function="first")
        wide = wide.with_columns(pl.lit(pf.game_key).alias("game_key"), pl.lit(pf.gsis_play_id).alias("gsis_play_id"),
                                 pl.lit(pf.throw_frame - pf.snap_frame if pf.throw_frame is not None else None, pl.Int32).alias("frames_to_throw"))
        out.append(wide)
    return pl.concat(out, how="diagonal_relaxed") if out else pl.DataFrame()
