"""`poshub export-web` — the static data the Next.js app in web/ reads, under web/public/ph/ (gitignored).

    index.json            every player-season on the board: role mix (v2), responsibility, percentiles, by-call split
    p/<nfl_id>_<season>.json   one player-season: every snap (where he stood, where he was at 2 s, the v2 role and its
                          probability, the charted responsibility, down/distance, the film keys) + his block map
    heat.json             league density of alignment spots per peer group × season (the heatmap backdrop)
    teams.json            shell mix by team-season × down × distance
    gates.json            v1, v2 and extension gates, for the Method page

Per-snap rows stay on this machine: web/public/ph is gitignored, like out/. Nothing here is pushed.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from ..roles.v2 import V2_ROLES
from ..roles.taxonomy import RESPONSIBILITIES, ROLE_LABEL
from .export import _clean

# ── PFF's own code dictionaries (PFF Data Reference Guide.xlsx, sheet "All Blocking Codes"). Never paraphrase a code
#    from memory: the first draft of this file guessed PH = "pass pro, help" (it is a PUSH block) and CL = "chip" (it is
#    a CLEAN-UP). PFF left/right are the DEFENSE's; the map folds them (the mirror image of a gap is the same gap).
GAP_FOLD = {"LA": "A gap", "RA": "A gap", "LB": "B gap", "RB": "B gap", "LC": "C gap", "RC": "C gap",
            "LD": "D gap", "RD": "D gap", "LY": "E gap", "RY": "E gap", "LE": "Outside the widest TE", "RE": "Outside the widest TE"}
GAP_JOB = {"FC": "Force", "1S": "Primary run support", "2S": "Secondary run support", "MF": "Middle of the field safety",
           "CV": "Play coverage", "CO": "Contain", "RP": "Crack replace", "PT": "Tracking the peel blocker"}
BLOCKER_FOLD = {"LT": "Tackle", "RT": "Tackle", "LG": "Guard", "RG": "Guard", "C": "Center",
                **{k: "Tight end" for k in ("TE-L", "TE-R", "TE-oL", "TE-oR", "TE-iL", "TE-iR", "TE-FL", "TE-FR")},
                **{k: "Back" for k in ("HB", "HB-L", "HB-R", "FB", "FB-L", "FB-R", "FB-iL", "FB-iR")},
                **{k: "Receiver" for k in ("LWR", "RWR", "SLWR", "SRWR", "SLoWR", "SLiWR", "SRoWR", "SRiWR")}, "QB": "Quarterback"}
BLOCK_TYPE = {
    # run plays
    "BF": "Backfield full", "BH": "Backfield help", "BK": "Back block", "CK": "Crack block", "CM": "Combo block", "CS": "Crash block",
    "CU": "Cutoff block", "DF": "Downfield block", "DN": "Down block", "DW": "Draw block", "HG": "Hinge block", "HL": "Help block",
    "HP": "Pull block, help", "MN": "Man block", "NB": "No block", "PB": "Pull block", "PH": "Push block", "PL": "Peel block",
    "RH": "Reach block", "RO": "Ran him off / ran a route", "SB": "Slingshot block", "SF": "Sift block", "ST": "Stalk block",
    "TW": "Trap / wham block",
    # pass plays
    "CH": "Chip block", "CL": "Clean-up", "PA": "Play-action protection", "PP": "Pass protection", "PR": "Pocket roll block",
    "PT": "Post block", "PU": "Backfield pickup", "RP": "RPO block", "SR": "Set and release", "SW": "Switch block",
    "UP": "Pull pass protection",
}
MOVE = {"I": "Inside move", "O": "Outside move", "B": "Bull rush", "CL": "Center left", "CR": "Center right",
        "PA": "Play-action run fit", "NM": "No move"}
HEAT_Y = (0.0, 22.0)      # depth, yards
HEAT_X = (-26.0, 26.0)    # lateral, yards (+ = the defense's right)


def _headshots(sister_public: Path) -> dict[str, str]:
    p = sister_public / "phase11_players.json"
    if not p.exists():
        return {}
    return {k: v.get("h") for k, v in json.loads(p.read_text()).items() if v.get("h")}


def _block_maps(out: Path) -> pl.DataFrame:
    """Per defender-season: who blocked him, how, how often two men did, the gap he hit, his first move."""
    bp = out / "cache" / "pffplayerblockings_2022_2023_2024_2025.parquet"
    if not bp.exists():
        return pl.DataFrame()
    b = pl.read_parquet(bp).with_columns(pl.col("GsisGameId").cast(pl.Int64).alias("game_key"), pl.col("GsisPlayId").cast(pl.Int64).alias("gsis_play_id"))
    seasons = pl.read_parquet(out / "features.parquet", columns=["game_key", "season"]).unique()
    b = b.join(seasons, on="game_key", how="inner")
    off = pl.read_parquet(sorted((out / "cache").glob("pffoffense_*.parquet"))[0]) if list((out / "cache").glob("pffoffense_*.parquet")) else None
    on_him = b.filter(pl.col("BlockedPlayerGsisId").is_not_null()).with_columns(pl.col("BlockedPlayerGsisId").cast(pl.Int64).alias("nfl_id"),
                                                                                pl.col("GsisPlayerId").cast(pl.Int64).alias("blocker_id"))
    if off is not None:
        on_him = on_him.join(off.rename({"nfl_id": "blocker_id"}), on=["game_key", "gsis_play_id", "blocker_id"], how="left")
        on_him = on_him.with_columns(pl.col("pff_off_position").replace_strict(BLOCKER_FOLD, default="Other").alias("blocker"))
    else:
        on_him = on_him.with_columns(pl.lit("Other").alias("blocker"))
    per_snap = on_him.group_by("nfl_id", "season", "game_key", "gsis_play_id").agg(pl.len().alias("n_blockers"))
    blockers = on_him.group_by("nfl_id", "season", "blocker").len()
    btype = on_him.group_by("nfl_id", "season", "BlockType").len()
    own = b.with_columns(pl.col("GsisPlayerId").cast(pl.Int64).alias("nfl_id")).filter(pl.col("BlockedPlayerGsisId").is_null())
    own = own.with_columns(pl.col("Gap1").replace_strict(GAP_FOLD, default=None).alias("gap"),
                           pl.col("Gap1").replace_strict(GAP_JOB, default=None).alias("job"))
    gaps = own.filter(pl.col("gap").is_not_null()).group_by("nfl_id", "season", "gap").len()
    jobs = own.filter(pl.col("job").is_not_null()).group_by("nfl_id", "season", "job").len()
    # PFF records the rusher's move on the BLOCKER's line ("the move attempted by the pass rusher recorded in the
    # blocked_player field on this line"), so moves are counted on the rows where he is the blocked man, once per snap
    moves = (on_him.filter(pl.col("Move1").is_not_null()).unique(["nfl_id", "game_key", "gsis_play_id", "Move1"])
             .group_by("nfl_id", "season", "Move1").len())
    base = own.group_by("nfl_id", "season").agg(pl.len().alias("charted_snaps"), pl.col("Unblocked").cast(pl.Float64).mean().alias("unblocked_rate"),
                                                pl.col("Looper").cast(pl.Float64).mean().alias("looper_rate"))
    dt = per_snap.group_by("nfl_id", "season").agg(pl.len().alias("blocked_snaps"), (pl.col("n_blockers") >= 2).mean().alias("double_team_rate"))
    rows = {}
    for r in base.join(dt, on=["nfl_id", "season"], how="left").iter_rows(named=True):
        rows[(r["nfl_id"], r["season"])] = {**{k: r[k] for k in ("charted_snaps", "blocked_snaps", "unblocked_rate", "looper_rate", "double_team_rate")},
                                            "blockers": {}, "types": {}, "gaps": {}, "jobs": {}, "moves": {}}
    for df, key, col in ((blockers, "blockers", "blocker"), (btype, "types", "BlockType"), (gaps, "gaps", "gap"), (jobs, "jobs", "job"),
                         (moves, "moves", "Move1")):
        for r in df.iter_rows(named=True):
            k = (r["nfl_id"], r["season"])
            if k in rows and r[col] is not None:
                label = BLOCK_TYPE.get(r[col], r[col]) if key == "types" else MOVE.get(r[col], r[col]) if key == "moves" else r[col]
                rows[k][key][label] = rows[k][key].get(label, 0) + r["len"]
    return rows


def _heat(scored: pl.DataFrame, bins_y: int = 22, bins_x: int = 52) -> dict:
    out = {}
    for (grp, season), g in scored.group_by("peer_group", "season"):
        H, _, _ = np.histogram2d(g["depth"].to_numpy(), g["lateral"].to_numpy(), bins=[bins_y, bins_x], range=[HEAT_Y, HEAT_X])
        H = H / max(H.sum(), 1)
        out[f"{grp}_{season}"] = np.round(H, 5).tolist()
    return {"y": HEAT_Y, "x": HEAT_X, "bins": [bins_y, bins_x], "grids": out}


def export_web(out: Path, web_public: Path, run_dirs: list[Path], sister_public: Path | None = None) -> dict:
    v2 = out / "v2"
    mix = pl.read_parquet(v2 / "role_mix.parquet")
    s = pl.read_parquet(v2 / "scored.parquet")
    keep = mix.select("nfl_id", "season", "peer_group")
    s = s.join(keep, on=["nfl_id", "season"], how="inner")
    heads = _headshots(sister_public) if sister_public else {}
    call = pl.read_parquet(out / "safety_mix_by_call.parquet") if (out / "safety_mix_by_call.parquet").exists() else pl.DataFrame()
    calls = {(r["nfl_id"], r["season"]): r for r in call.iter_rows(named=True)} if call.height else {}
    blocks = _block_maps(out)

    ph = web_public / "ph"
    (ph / "p").mkdir(parents=True, exist_ok=True)
    role_ix = {r: i for i, r in enumerate(V2_ROLES)}
    resp_ix = {r: i for i, r in enumerate(RESPONSIBILITIES)}

    index = []
    for r in mix.iter_rows(named=True):
        key = (r["nfl_id"], r["season"])
        c = calls.get(key)
        index.append({
            "id": r["nfl_id"], "name": r.get("player_name"), "team": r.get("team"), "season": r["season"], "pos": r.get("roster_pos"),
            "group": r.get("peer_group"), "snaps": r["snaps"], "primary": r.get("primary_role"), "entropy": r.get("align_entropy"),
            "depth": r.get("mean_depth"), "box": r.get("box_rate"), "head": heads.get(str(r["nfl_id"])),
            "align": {k: r.get(f"share_{k}") for k in V2_ROLES},
            "resp": {k: r.get(f"resp_{k}") for k in RESPONSIBILITIES},
            "pct": {k[4:]: v for k, v in r.items() if k.startswith("pct_") and v is not None},
            "call": {k: c[k] for k in ("deep_share_one_high", "deep_share_two_high", "middle_share_one_high", "box_share_one_high", "call_explains")} if c else None,
            "blocks": blocks.get(key) if isinstance(blocks, dict) else None,
        })
    cols = ["game_key", "gsis_play_id", "week", "depth", "lateral", "depth_2s", "lateral_2s", "align_role", "align_top_p", "resp_role",
            "pff_DOWN", "pff_DISTANCE", "is_pass", "is_play_action", "offense_team", "pff_MOFOCPLAYED"]
    n_files = 0
    for (nid, season), g in s.select(["nfl_id", "season"] + [c for c in cols if c in s.columns]).group_by("nfl_id", "season"):
        g = g.sort("week", "gsis_play_id")
        snaps = [[r["game_key"], r["gsis_play_id"], r["week"], round(r["depth"], 1), round(r["lateral"], 1),
                  None if r["depth_2s"] is None else round(r["depth_2s"], 1), None if r["lateral_2s"] is None else round(r["lateral_2s"], 1),
                  role_ix.get(r["align_role"], -1), round(r["align_top_p"], 2), resp_ix.get(r["resp_role"], -1), r["pff_DOWN"],
                  r["pff_DISTANCE"], 1 if r["is_pass"] else 0, 1 if r["is_play_action"] else 0, r["offense_team"], r["pff_MOFOCPLAYED"]]
                 for r in g.iter_rows(named=True)]
        (ph / "p" / f"{nid}_{season}.json").write_text(json.dumps(_clean({
            "cols": ["game_key", "play_id", "week", "depth", "lateral", "depth_2s", "lateral_2s", "role", "p", "resp", "down", "distance",
                     "pass", "pa", "opp", "shell"], "snaps": snaps}), separators=(",", ":"), allow_nan=False))
        n_files += 1
    meta = {"roles": V2_ROLES, "resp": RESPONSIBILITIES, "labels": ROLE_LABEL, "generated_from": str(v2)}
    (ph / "index.json").write_text(json.dumps(_clean({"meta": meta, "players": index}), separators=(",", ":"), allow_nan=False))
    (ph / "heat.json").write_text(json.dumps(_clean(_heat(s)), separators=(",", ":"), allow_nan=False))
    if (out / "shell_by_situation.parquet").exists():
        (ph / "teams.json").write_text(json.dumps(_clean(pl.read_parquet(out / "shell_by_situation.parquet").to_dicts()), separators=(",", ":"), allow_nan=False))
    gates = {}
    for d in run_dirs:
        for f in sorted(d.glob("*gates*.json")):
            gates[f"{d.name}/{f.stem}"] = json.loads(f.read_text())
    (ph / "gates.json").write_text(json.dumps(_clean(gates), indent=1, allow_nan=False))
    return {"players": len(index), "files": n_files, "headshots": sum(1 for p in index if p["head"])}
