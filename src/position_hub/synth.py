"""Synthetic NGS-shaped tracking with KNOWN roles — the test bed.

The real frames live in Databricks / on the Mac; this module makes plays in the exact NGS column
layout (game_key, nfl_id, time, team_id, position, x, y, s, o, dir, event, gsis_play_id ...) so every
loader, standardizer, feature and model runs end to end here. Each defender carries a hidden
`true_align_role` / `true_responsibility` used only by tests; production never sees them.

⛔ Nothing generated here ever enters a real donor pool, price, index or leaderboard (house rule).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np
import polars as pl

from .roles.taxonomy import ALIGN_ROLES

RNG = random.Random(7)

# offensive template in the standardized frame (offense moves +x; ball at origin; y+ = offense left)
OFFENSE_TEMPLATES = {
    "11_2x2": [("QB", -4.5, 0.0), ("C", -0.5, 0.0), ("G", -0.6, 1.2), ("G", -0.6, -1.2), ("T", -0.7, 2.5), ("T", -0.7, -2.5),
               ("TE", -0.8, 4.0), ("WR", -0.8, 20.0), ("WR", -1.2, 10.5), ("WR", -0.8, -19.0), ("RB", -6.0, -1.0)],
    "11_3x1": [("QB", -4.5, 0.0), ("C", -0.5, 0.0), ("G", -0.6, 1.2), ("G", -0.6, -1.2), ("T", -0.7, 2.5), ("T", -0.7, -2.5),
               ("TE", -0.8, 4.0), ("WR", -0.8, 21.0), ("WR", -1.2, 12.0), ("WR", -0.8, -20.0), ("RB", -6.0, 1.0)],
    "12_pro": [("QB", -1.2, 0.0), ("C", -0.5, 0.0), ("G", -0.6, 1.2), ("G", -0.6, -1.2), ("T", -0.7, 2.5), ("T", -0.7, -2.5),
               ("TE", -0.8, 4.0), ("TE", -0.8, -4.0), ("WR", -0.8, 19.0), ("WR", -0.8, -18.0), ("RB", -7.0, 0.0)],
}

# defensive templates: (ngs_position, depth, lateral, true_align_role)
DEFENSE_TEMPLATES = {
    "nickel_1high": [("DE", 1.0, 5.0, "EDGE"), ("DE", 1.0, -5.0, "EDGE"), ("DT", 1.0, 1.5, "INTERIOR_DL"),
                     ("DT", 1.0, -2.0, "INTERIOR_DL"), ("LB", 4.5, 1.5, "OFF_BALL_LB"), ("LB", 4.5, -2.0, "OFF_BALL_LB"),
                     ("CB", 7.0, 20.5, "BOUNDARY_CB"), ("CB", 1.5, -19.5, "BOUNDARY_CB"), ("CB", 5.5, 11.5, "SLOT_CB"),
                     ("SS", 8.5, 6.0, "BOX_SAFETY"), ("FS", 14.0, 0.5, "DEEP_MIDDLE")],
    "nickel_2high": [("DE", 1.0, 5.0, "EDGE"), ("DE", 1.0, -5.0, "EDGE"), ("DT", 1.0, 1.5, "INTERIOR_DL"),
                     ("DT", 1.0, -2.0, "INTERIOR_DL"), ("LB", 4.5, 1.0, "OFF_BALL_LB"), ("LB", 5.0, -2.5, "OFF_BALL_LB"),
                     ("CB", 6.5, 20.0, "BOUNDARY_CB"), ("CB", 6.5, -19.5, "BOUNDARY_CB"), ("CB", 5.0, 11.0, "SLOT_CB"),
                     ("SS", 12.5, 8.0, "DEEP_HALF"), ("FS", 12.5, -8.0, "DEEP_HALF")],
    "base_1high": [("DE", 1.0, 5.0, "EDGE"), ("DE", 1.0, -5.0, "EDGE"), ("DT", 1.0, 1.5, "INTERIOR_DL"),
                   ("DT", 1.0, -2.0, "INTERIOR_DL"), ("LB", 4.5, 0.5, "OFF_BALL_LB"), ("LB", 4.5, -3.0, "OFF_BALL_LB"),
                   ("LB", 4.0, 6.5, "OVERHANG"), ("CB", 7.0, 19.5, "BOUNDARY_CB"), ("CB", 7.0, -18.5, "BOUNDARY_CB"),
                   ("SS", 9.0, 9.0, "BOX_SAFETY"), ("FS", 14.5, -0.5, "DEEP_MIDDLE")],
}

# what each align role does after the snap on pass / run, as (bite_2s, lateral_2s, responsibility)
BEHAVIOUR = {
    "EDGE": {"pass": (-3.5, 0.5, "RUSH"), "run": (-1.0, 0.0, "RUN_FIT")},
    "INTERIOR_DL": {"pass": (-2.5, 0.0, "RUSH"), "run": (-0.5, 0.0, "RUN_FIT")},
    "OFF_BALL_LB": {"pass": (+3.0, 1.0, "UNDER_ZONE"), "run": (-2.5, 1.5, "RUN_FIT")},
    "OVERHANG": {"pass": (+2.0, 2.0, "UNDER_ZONE"), "run": (-2.0, 1.0, "RUN_FIT")},
    "SLOT_CB": {"pass": (+2.0, 0.0, "MAN"), "run": (-1.0, 0.0, "RUN_FIT")},
    "BOUNDARY_CB": {"pass": (+3.0, 0.0, "MAN"), "run": (-0.5, 0.0, "RUN_FIT")},
    "BOX_SAFETY": {"pass": (+2.5, 1.5, "UNDER_ZONE"), "run": (-3.0, 1.0, "RUN_FIT")},
    "DEEP_HALF": {"pass": (+4.0, 0.0, "DEEP_ZONE"), "run": (-2.0, 0.0, "RUN_FIT")},
    "DEEP_MIDDLE": {"pass": (+4.0, 0.0, "DEEP_ZONE"), "run": (-3.0, 0.0, "RUN_FIT")},
}


@dataclass
class SynthPlayer:
    nfl_id: int
    name: str
    position: str
    team: str
    align_pref: dict[str, float] = field(default_factory=dict)   # role mix this player is drawn from


# stable ids per team so a player persists across games (a season needs a role MIX per man)
TEAM_BASE_ID = {"CAR": 10000, "ATL": 20000, "TB": 30000, "NO": 40000}


def _roster(team: str, base_id: int) -> list[SynthPlayer]:
    names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet", "Kilo",
             "Lima", "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor"]
    pos = ["QB", "C", "G", "G", "T", "T", "TE", "TE", "WR", "WR", "WR", "RB",
           "DE", "DE", "DT", "DT", "LB", "LB", "LB", "CB", "CB", "CB", "SS", "FS"]
    return [SynthPlayer(base_id + i, f"{team} {names[i % len(names)]} {i}", p, team) for i, p in enumerate(pos)]


def _pick(players: list[SynthPlayer], position: str, used: set[int]) -> SynthPlayer:
    for p in players:
        if p.position == position and p.nfl_id not in used:
            used.add(p.nfl_id)
            return p
    for p in players:  # position group fallback
        if p.nfl_id not in used and p.position in ("SS", "FS", "CB", "LB"):
            used.add(p.nfl_id)
            return p
    raise RuntimeError("roster exhausted")


def make_game(game_key: int, n_plays: int = 40, seed: int = 0, home: str = "CAR", away: str = "ATL",
              safety_swap_rate: float = 0.35) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Returns (frames, truth). `truth` has one row per defender-play with the hidden roles.
    `safety_swap_rate` makes the two safeties trade box/deep jobs on a share of snaps so a real role
    MIX exists to recover (e.g. the FS is 65% deep middle, 35% box)."""
    rng = np.random.default_rng(seed)
    frames, truth = [], []
    rosters = {home: _roster(home, TEAM_BASE_ID[home]), away: _roster(away, TEAM_BASE_ID[away])}
    t0_ms = 1_757_869_200_000  # 2025-09-14T17:00:00Z in epoch ms
    for k in range(n_plays):
        pid = 40 + k * 25
        off_team = home if k % 2 == 0 else away
        def_team = away if off_team == home else home
        moves_right = bool(rng.random() < 0.5)
        ball_x = float(rng.uniform(25, 95))
        ball_y = float(rng.choice([23.6, 26.65, 29.7]))          # left hash, middle, right hash
        is_pass = bool(rng.random() < 0.58)
        play_action = bool(is_pass and rng.random() < 0.25)
        off_tpl = OFFENSE_TEMPLATES[rng.choice(list(OFFENSE_TEMPLATES))]
        def_tpl = list(DEFENSE_TEMPLATES[rng.choice(list(DEFENSE_TEMPLATES))])
        # the safeties swap jobs on a share of snaps → recoverable role mix
        if rng.random() < safety_swap_rate:
            ss = [i for i, d in enumerate(def_tpl) if d[0] == "SS"]
            fs = [i for i, d in enumerate(def_tpl) if d[0] == "FS"]
            if ss and fs:
                a, b = def_tpl[ss[0]], def_tpl[fs[0]]
                def_tpl[ss[0]] = ("SS",) + b[1:]
                def_tpl[fs[0]] = ("FS",) + a[1:]
        used: set[int] = set()
        sgn = 1.0 if moves_right else -1.0
        n_frames = 55
        snap_f, ls_f, thr_f, ho_f = 12, 3, 12 + int(rng.integers(20, 30)), 12 + 8
        events = {ls_f: "line_set", snap_f: "ball_snap"}
        if is_pass:
            events[thr_f] = "pass_forward"
            events[min(thr_f + 10, n_frames - 1)] = "pass_outcome_incomplete"
        else:
            events[ho_f] = "handoff"
            events[n_frames - 3] = "tackle"
        if play_action:
            events[snap_f + 6] = "play_action"

        def emit(p: SynthPlayer, path: np.ndarray, extra_truth: dict | None = None):
            for fi in range(n_frames):
                sx, sy = path[fi]
                rx, ry = ball_x + sgn * sx, ball_y + sgn * sy
                spd = float(np.hypot(*(path[fi] - path[fi - 1]))) * 10 if fi else 0.0
                frames.append({"game_key": game_key, "nfl_id": p.nfl_id, "time": t0_ms + k * 40000 + fi * 100,
                               "team_id": p.team, "gsis_id": f"00-00{p.nfl_id}", "esb_id": None, "player_name": p.name,
                               "jersey_number": p.nfl_id % 99, "position": p.position,
                               "position_group": {"QB": "QB", "C": "OL", "G": "OL", "T": "OL", "TE": "TE", "WR": "WR", "RB": "RB",
                                                  "DE": "DL", "DT": "DL", "LB": "LB", "CB": "DB", "SS": "DB", "FS": "DB"}[p.position],
                               "is_on_field": True, "x": rx, "y": ry, "z": None, "s": spd, "a": 0.0, "dis": spd / 10,
                               "o": 90.0 if moves_right else 270.0, "dir": 90.0 if moves_right else 270.0,
                               "gsis_play_id": float(pid), "event": events.get(fi, ""), "sa": 0.0})
            if extra_truth is not None:
                truth.append(extra_truth)

        # offense paths: hold, then move downfield / run
        off_paths: list[tuple[str, np.ndarray]] = []
        for pos, x0, y0 in off_tpl:
            p = _pick(rosters[off_team], pos, used)
            path = np.zeros((n_frames, 2)) + [x0 + rng.normal(0, 0.15), y0 + rng.normal(0, 0.15)]
            for fi in range(snap_f, n_frames):
                t = (fi - snap_f) / 10
                if pos in ("WR", "TE"):
                    path[fi] = path[snap_f] + [min(6.5 * t, 15), 0.3 * t]
                elif pos == "RB":
                    path[fi] = path[snap_f] + ([1.2 * t, 0.0] if is_pass else [4.5 * t, 1.5 * t])
                elif pos == "QB":
                    path[fi] = path[snap_f] + ([-1.5 * min(t, 1.2), 0.0] if is_pass else [-0.5 * min(t, 0.8), 0.0])
                else:
                    path[fi] = path[snap_f] + [-0.3 * min(t, 1.0), 0.0]
            off_paths.append((pos, path))
            emit(p, path)
        # defense paths
        used_d: set[int] = set()
        for pos, depth, lat, role in def_tpl:
            p = _pick(rosters[def_team], pos, used_d)
            bite, latm, resp = BEHAVIOUR[role]["pass" if is_pass else "run"]
            if play_action and role in ("OFF_BALL_LB", "BOX_SAFETY"):
                bite = bite - 2.0 + rng.normal(0, 0.8)           # they bite on play action, individually
            x0, y0 = depth + rng.normal(0, 0.4), lat + rng.normal(0, 0.5)
            path = np.zeros((n_frames, 2)) + [x0, y0]
            # pre-snap disguise: deep safety creeps down late on 20% of snaps (still deep at the snap)
            if role in ("DEEP_MIDDLE", "DEEP_HALF") and rng.random() < 0.2:
                for fi in range(ls_f, snap_f):
                    path[fi] = [x0 + 1.5 - 1.5 * (fi - ls_f) / (snap_f - ls_f), y0]
            if resp == "MAN":
                # mirror the receiver he aligned over: his cushion, a 0.3 s reaction lag
                cand = [(abs(pp[snap_f][1] - y0), pp) for pos_, pp in off_paths if pos_ in ("WR", "TE")]
                _, rp = min(cand, key=lambda c: c[0])
                cushion = np.array([x0 - rp[snap_f][0], y0 - rp[snap_f][1]])
                for fi in range(snap_f, n_frames):
                    src = rp[max(snap_f, fi - 3)]
                    path[fi] = src + cushion * max(0.35, 1 - 0.2 * ((fi - snap_f) / 10)) + rng.normal(0, 0.05, 2)
            else:
                for fi in range(snap_f, n_frames):
                    t = min((fi - snap_f) / 10, 2.0)
                    path[fi] = [x0 + bite * t / 2.0 + rng.normal(0, 0.05), y0 + latm * t / 2.0 + rng.normal(0, 0.05)]
                    if fi - snap_f > 20:
                        path[fi] = path[snap_f + 20] + [(bite / 2.0) * ((fi - snap_f - 20) / 10) * 0.5, 0]
            emit(p, path, {"game_key": game_key, "gsis_play_id": pid, "nfl_id": p.nfl_id, "is_pass": is_pass,
                           "play_action": play_action, "true_align_role": role, "true_responsibility": resp,
                           "pff_alignment": _pff_code(role, lat, pos), "defense_team": def_team})
    fr = pl.DataFrame(frames).with_columns(pl.from_epoch(pl.col("time"), time_unit="ms").cast(pl.Datetime("ns")).alias("time"))
    return fr, pl.DataFrame(truth)


def _pff_code(role: str, lat: float, pos: str) -> str:
    """A plausible PFF alignment slot for the synthetic snap (left/right are the DEFENSE's; the
    standardized +y is the defense's right)."""
    side = "R" if lat >= 0 else "L"
    return {"EDGE": f"{side}EO" if side == "R" else "LEO", "INTERIOR_DL": f"D{side}T", "OFF_BALL_LB": f"{side}ILB",
            "OVERHANG": f"{side}OLB", "SLOT_CB": f"SCB{side}", "BOUNDARY_CB": f"{side}CB",
            "BOX_SAFETY": f"SS{side}", "DEEP_HALF": f"FS{side}", "DEEP_MIDDLE": "FS"}[role]


def make_season(n_games: int = 6, plays_per_game: int = 40, seed: int = 0) -> tuple[pl.DataFrame, pl.DataFrame]:
    """A round-robin among four teams; every man plays ~half the games, so role mixes are estimable."""
    # ordered so every team appears in both even- and odd-numbered games (the split-half gate splits on game parity)
    matchups = [("CAR", "ATL"), ("CAR", "TB"), ("TB", "NO"), ("ATL", "NO"), ("CAR", "NO"), ("ATL", "TB")]
    fr, tr = [], []
    for g in range(n_games):
        home, away = matchups[g % len(matchups)]
        f, t = make_game(59000 + g, plays_per_game, seed=seed + g, home=home, away=away)
        fr.append(f)
        tr.append(t)
    return pl.concat(fr), pl.concat(tr)


assert set(BEHAVIOUR) == set(ALIGN_ROLES), "synthetic behaviours must cover the taxonomy"
