"""Coordinate standardization — one play at a time, pure functions.

The standardized frame (same convention as panthers_projects/simulator/transforms.py so numbers are
comparable across the two repos):
  * origin = ball at the snap. ⛔ NGS has NO ball track; the snapper (C) is the proxy, offensive-line
    median as fallback (flag `ball_proxy`).
  * offense ALWAYS moves +x. So for a DEFENDER, x = depth off the line of scrimmage (positive),
    y = lateral offset from the ball; +y is the OFFENSE's left = the DEFENSE's right.
  * angles keep the NGS convention (0 = +y axis, clockwise); a flipped play rotates them by 180°.

Direction rule (measured 100% correct with and without a tagged center): the quarterback lines up
BEHIND his own offensive line — offense moves right iff qb_x < median OL x at the snap.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

SNAP_EVENTS = (["ball_snap", "snap_direct"], ["autoevent_ballsnap"])
LINE_SET_EVENTS = ["line_set"]
THROW_EVENTS = (["pass_forward"], ["autoevent_passforward"])
HANDOFF_EVENTS = (["handoff"], ["autoevent_handoff"])
END_EVENTS = ["tackle", "out_of_bounds", "touchdown", "qb_sack", "qb_slide", "qb_kneel", "safety",
              "pass_outcome_caught", "pass_outcome_incomplete", "pass_outcome_interception",
              "pass_outcome_touchdown", "dropped_pass", "fumble"]
OL_POS = {"C", "G", "T", "OL", "LG", "RG", "LT", "RT", "OG", "OT"}
FIELD_WIDTH = 53.3


def _first_event_frame(play: pl.DataFrame, tiers: tuple[list[str], list[str]] | list[str], after: int | None = None) -> int | None:
    manual, auto = tiers if isinstance(tiers, tuple) else (tiers, [])
    for names in (manual, auto):
        if not names:
            continue
        e = play.filter(pl.col("event").is_in(names))
        if after is not None:
            e = e.filter(pl.col("frame_id") > after)
        if e.height:
            return int(e.get_column("frame_id").min())
    return None


@dataclass
class PlayFrame:
    """One standardized play: frames + the anchors every feature reads."""
    frames: pl.DataFrame            # standardized x, y (+ raw_x, raw_y), dir, o, s, frame_id, nfl_id, ...
    game_key: int
    gsis_play_id: int
    snap_frame: int
    line_set_frame: int | None
    throw_frame: int | None
    handoff_frame: int | None
    end_frame: int | None
    offense_team: str
    defense_team: str
    offense_moves_right: bool
    ball_x: float
    ball_y: float
    ball_proxy: str                 # "center" | "ol_middle" | "ol_median"
    qb_id: int | None
    ball_carrier_id: int | None     # at handoff: nearest non-QB offensive player to the QB

    @property
    def is_flipped(self) -> bool:
        return not self.offense_moves_right

    def at(self, frame: int) -> pl.DataFrame:
        return self.frames.filter(pl.col("frame_id") == frame)

    def defenders_at(self, frame: int) -> pl.DataFrame:
        return self.at(frame).filter(~pl.col("is_offense"))

    def offense_at(self, frame: int) -> pl.DataFrame:
        return self.at(frame).filter(pl.col("is_offense"))


def standardize_play(play: pl.DataFrame) -> PlayFrame | None:
    """Returns None when the play has no snap or no two teams (kickoffs, aborted, spikes are kept
    only if they have a snap; special teams are filtered upstream by the PFF join)."""
    if play.height == 0:
        return None
    game_key = int(play.get_column("game_key")[0])
    pid = int(play.get_column("gsis_play_id")[0])
    snap = _first_event_frame(play, SNAP_EVENTS)
    if snap is None:
        return None
    at_snap = play.filter(pl.col("frame_id") == snap)
    teams = at_snap.get_column("team_id").unique().to_list()
    if len(teams) != 2:
        return None

    # offense = the QB's team; fallback = the team with a center
    qb = at_snap.filter(pl.col("position") == "QB")
    if qb.height:
        off_team = qb.get_column("team_id")[0]
        qb_id = int(qb.get_column("nfl_id")[0])
        qb_x = float(qb.get_column("x").mean())
    else:
        c = at_snap.filter(pl.col("position") == "C")
        if not c.height:
            return None
        off_team, qb_id, qb_x = c.get_column("team_id")[0], None, float("nan")
    def_team = [t for t in teams if t != off_team][0]
    off = at_snap.filter(pl.col("team_id") == off_team)

    # ball proxy: the tagged center; else the MIDDLE lineman (the man with the median lateral position among five
    # linemen IS the snapper — a guard or tackle carrying his roster label at center); else the OL median.
    # Measured 2026-09-25 vs NGS x_ball_at_snap: tagged center 0.00 yd off; the coordinate median sat 0.43 yd behind.
    center = off.filter(pl.col("position") == "C")
    ol = off.filter(pl.col("position").is_in(list(OL_POS)))
    if center.height:
        ball_x, ball_y, proxy = float(center["x"][0]), float(center["y"][0]), "center"
    elif ol.height >= 5:
        mid = ol.sort("y")[ol.height // 2]
        ball_x, ball_y, proxy = float(mid["x"][0]), float(mid["y"][0]), "ol_middle"
    elif ol.height >= 3:
        ball_x, ball_y, proxy = float(ol["x"].median()), float(ol["y"].median()), "ol_median"
    else:
        return None
    ol_x = float(ol["x"].median()) if ol.height else ball_x
    if not np.isnan(qb_x):
        moves_right = qb_x < ol_x if abs(qb_x - ol_x) > 0.25 else qb_x < ball_x
    else:
        # no QB: the defense is on the far side of the line from the offense's centroid
        moves_right = float(off["x"].mean()) < float(at_snap.filter(pl.col("team_id") == def_team)["x"].mean())
    sgn = 1.0 if moves_right else -1.0

    f = play.with_columns(
        (pl.col("team_id") == off_team).alias("is_offense"),
        pl.col("x").alias("raw_x"), pl.col("y").alias("raw_y"),
        ((pl.col("x") - ball_x) * sgn).alias("x"),
        ((pl.col("y") - ball_y) * sgn).alias("y"),
    )
    if not moves_right:
        f = f.with_columns(((pl.col("dir") + 180.0) % 360.0).alias("dir"), ((pl.col("o") + 180.0) % 360.0).alias("o"))

    end = _first_event_frame(play, END_EVENTS, after=snap)
    throw = _first_event_frame(play, THROW_EVENTS, after=snap)
    handoff = _first_event_frame(play, HANDOFF_EVENTS, after=snap)
    if end is not None and throw is not None and throw > end:
        throw = None
    line_set = _first_event_frame(play, LINE_SET_EVENTS)
    if line_set is not None and line_set >= snap:
        line_set = None

    carrier = None
    if handoff is not None and qb_id is not None:
        h = f.filter((pl.col("frame_id") == handoff) & pl.col("is_offense") & (pl.col("nfl_id") != qb_id))
        q = f.filter((pl.col("frame_id") == handoff) & (pl.col("nfl_id") == qb_id))
        if h.height and q.height:
            d = ((h["x"] - q["x"][0]) ** 2 + (h["y"] - q["y"][0]) ** 2).arg_min()
            carrier = int(h["nfl_id"][d])

    return PlayFrame(frames=f, game_key=game_key, gsis_play_id=pid, snap_frame=snap, line_set_frame=line_set,
                     throw_frame=throw, handoff_frame=handoff, end_frame=end, offense_team=str(off_team),
                     defense_team=str(def_team), offense_moves_right=moves_right, ball_x=ball_x, ball_y=ball_y,
                     ball_proxy=proxy, qb_id=qb_id, ball_carrier_id=carrier)
