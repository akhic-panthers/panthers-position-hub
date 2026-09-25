"""NGS play-level product from Unity Catalog — `ngsdb.bronze.player_play` — used as an independent CHECK.

Found by `poshub discover` on 2026-09-25 (it answers Eric's open question: the 108-column play-level product
does exist for the regular season, in the workspace, 2016–2025). Per (game_key, gsis_play_id, nfl_id) it carries:

  * the BALL at the snap (`x_ball_at_snap`, `y_ball_at_snap`) — the thing the per-game frames lack and this
    project proxies with the snapper;
  * `Play_Direction` (left/right) — the league's answer to our QB-behind-his-line direction rule;
  * `depth_from_los_at_snap` — the league's depth, to compare with ours;
  * `ngs_position` — NGS's OWN per-snap defender role: CB, SLOT_CB, HIGH_SAFETY, BOX_SAFETY, MLB, OLB, EDGE,
    INTERIOR_LINE. A third label source, produced neither by PFF's charters nor by our geometry;
  * `defender_location_type` (technique: ZERO … NINE, *_ZERO = off the line, LEFT/RIGHT_WIDE, LEFT/RIGHT_SLOT,
    SAFETY), `playing_high_safety`, `lined_up_in_the_box`, `blitzing`, `cushion`, `distance_from_lineset_to_snap`,
    `in_motion_at_ball_snap`, `defenders_in_the_box`.

⛔ It is a check, not a training label and not a tuning target (gate first, tune never). The registered v1
method keeps the snapper proxy; this table lets the first real run MEASURE the proxy error and the direction
rule on every snap instead of on three hand-picked plays. Flags in this table are varchar '1'/'0'.
"""
from __future__ import annotations

import polars as pl

from ..databricks.client import DataSource

NGS_PP_COLS = ["game_key", "gsis_play_id", "nfl_id", "season", "season_type", "week", "team_abbr", "position", "ngs_position",
               "x_at_snap", "y_at_snap", "x_ball_at_snap", "y_ball_at_snap", "depth_from_los_at_snap", "Play_Direction",
               "defender_location_type", "playing_high_safety", "lined_up_in_the_box", "blitzing", "cushion",
               "distance_from_lineset_to_snap", "in_motion_at_ball_snap", "defenders_in_the_box", "play_type"]

# NGS role → this project's alignment role family, for the agreement crosstab only
NGS_ROLE_TO_ALIGN = {"CB": "BOUNDARY_CB", "SLOT_CB": "SLOT_CB", "HIGH_SAFETY": "DEEP_SAFETY", "BOX_SAFETY": "BOX_SAFETY",
                     "MLB": "OFF_BALL_LB", "OLB": "OFF_BALL_LB", "EDGE": "EDGE", "INTERIOR_LINE": "INTERIOR_DL"}


def load_ngs_play_level(src: DataSource, seasons: list[int], season_types: tuple[str, ...] = ("REG", "POST")) -> pl.DataFrame:
    """Defender rows of `ngsdb.bronze.player_play` for the seasons given, prefixed `ngs_`. Databricks only —
    there is no local copy; on a local source this returns an empty frame and the caller says so."""
    if src.mode != "databricks":
        return pl.DataFrame()
    where = (f"season IN ({', '.join(str(int(s)) for s in seasons)}) AND season_type IN ({', '.join(repr(t) for t in season_types)}) "
             f"AND defense_play = '1'")
    frames = []
    for s in seasons:  # one season per statement keeps each result under the external-links chunk limits
        w = where.replace(f"season IN ({', '.join(str(int(x)) for x in seasons)})", f"season = {int(s)}")
        frames.append(src.read("ngs_player_play", NGS_PP_COLS, where=w))
    df = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
    if df.height == 0:
        return df
    df = df.with_columns([pl.col(c).cast(pl.Int64, strict=False) for c in ("game_key", "gsis_play_id", "nfl_id")])
    df = df.with_columns([pl.col(c).cast(pl.Utf8).is_in(["1", "True", "true"]).alias(c)
                          for c in ("playing_high_safety", "lined_up_in_the_box", "blitzing", "in_motion_at_ball_snap") if c in df.columns])
    df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in
                          ("x_at_snap", "y_at_snap", "x_ball_at_snap", "y_ball_at_snap", "depth_from_los_at_snap", "cushion", "distance_from_lineset_to_snap") if c in df.columns])
    df = df.with_columns(pl.col("ngs_position").replace_strict(NGS_ROLE_TO_ALIGN, default=None).alias("ngs_align_family"))
    keep = ["game_key", "gsis_play_id", "nfl_id"]
    # the frames already carry `ngs_position` (the ROSTER position); NGS's per-snap ROLE becomes `ngs_role`
    ren = {"ngs_position": "ngs_role", "position": "ngs_roster_position", "ngs_align_family": "ngs_align_family"}
    ren.update({c: f"ngs_{c.lower()}" for c in df.columns if c not in keep and c not in ren})
    return df.rename(ren).unique(keep)
