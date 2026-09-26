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


def _heat_off(out: Path, bins_y: int = 32, bins_x: int = 52) -> dict:
    from ..roles.offense import PEER
    o = pl.read_parquet(out / "offense" / "scored.parquet", columns=["ngs_position", "season", "x_snap", "y_snap"])
    o = o.with_columns(pl.col("ngs_position").replace_strict(PEER, default=None).alias("g")).filter(pl.col("g").is_not_null())
    grids = {}
    for (g, season), d in o.group_by("g", "season"):
        H, _, _ = np.histogram2d(d["x_snap"].to_numpy(), d["y_snap"].to_numpy(), bins=[bins_y, bins_x], range=[(-10.0, 22.0), HEAT_X])
        grids[f"{g}_{season}"] = np.round(H / max(H.sum(), 1), 5).tolist()
    return {"y": (-10.0, 22.0), "x": HEAT_X, "bins": [bins_y, bins_x], "grids": grids}


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
    for p in index:
        p["side"] = "D"
    from ..roles.offense import OFF_ROLES
    off = export_offense(out, web_public, heads) if (out / "offense" / "scored.parquet").exists() else []
    meta = {"roles": V2_ROLES, "resp": RESPONSIBILITIES, "off_roles": OFF_ROLES, "labels": ROLE_LABEL, "generated_from": str(v2)}
    (ph / "index.json").write_text(json.dumps(_clean({"meta": meta, "players": index + off}), separators=(",", ":"), allow_nan=False))
    (ph / "heat_off.json").write_text(json.dumps(_clean(_heat_off(out)), separators=(",", ":"), allow_nan=False)) if off else None
    (ph / "heat.json").write_text(json.dumps(_clean(_heat(s)), separators=(",", ":"), allow_nan=False))
    if (out / "shell_by_situation.parquet").exists():
        (ph / "teams.json").write_text(json.dumps(_clean(pl.read_parquet(out / "shell_by_situation.parquet").to_dicts()), separators=(",", ":"), allow_nan=False))
    gates = {}
    for d in run_dirs:
        for f in sorted(d.glob("*gates*.json")):
            gates[f"{d.name}/{f.stem}"] = json.loads(f.read_text())
    (ph / "gates.json").write_text(json.dumps(_clean(gates), indent=1, allow_nan=False))
    return {"players": len(index), "offense_players": len(off), "files": n_files, "headshots": sum(1 for p in index + off if p["head"])}


# ── offense ────────────────────────────────────────────────────────────────────────────────────────────────────
def export_offense(out: Path, web_public: Path, heads: dict[str, str]) -> list[dict]:
    """Offensive player-seasons for the Player Room: role mix (docs/REGISTERED_offense_roles_v1.md), usage, route tree,
    who covered him (the v2 role of his charted coverage_defense matchup), whom he blocked, and every snap with its
    first three seconds. Per-snap files land beside the defense's under ph/p/ (gitignored)."""
    from ..roles.offense import OFF_ROLES, PEER, motion_kind
    from ..roles.aggregate import add_peer_percentiles

    o = pl.read_parquet(out / "offense" / "scored.parquet")
    o = o.with_columns(pl.col("ngs_position").replace_strict(PEER, default=None).alias("peer_group")).filter(pl.col("peer_group").is_not_null())
    # team codes people read (the tracking carries NGS team ids), and PFF's charted on-the-line flag for X vs Z and wing:
    # a geometric cut called 98% of wide receivers X (the ball is ~0.5 yd ahead of the snapper; Z is only ~1 yd off)
    codes = pl.read_parquet(out / "v2" / "scored.parquet", columns=["game_key", "gsis_play_id", "offense_team", "defense_team"]).unique(["game_key", "gsis_play_id"])
    o = o.drop([c for c in ("offense_team", "defense_team") if c in o.columns]).join(codes, on=["game_key", "gsis_play_id"], how="left")
    onlos = pl.read_parquet(out / "cache" / "pffoffense_full_2022_2025.parquet").select(
        pl.col("pff_GSISGAMEKEY").cast(pl.Int64).alias("game_key"), pl.col("pff_GSISPLAYID").cast(pl.Int64).alias("gsis_play_id"),
        pl.col("pff_GSISPLAYERID").cast(pl.Int64, strict=False).alias("nfl_id"), (pl.col("pff_ONLOS") == "Y").alias("pff_on_line")).unique(["game_key", "gsis_play_id", "nfl_id"])
    o = o.join(onlos, on=["game_key", "gsis_play_id", "nfl_id"], how="left").with_columns(pl.coalesce(["pff_on_line", "on_line"]).alias("on_line"))
    o = o.with_columns(pl.when(pl.col("route").str.starts_with("Pass Block")).then(pl.lit("Stayed in to block")).otherwise(pl.col("route")).alias("route"))
    paths = pl.read_parquet(out / "offense_paths.parquet").drop([c for c in ("season", "week", "x_0", "y_0") if c in pl.read_parquet_schema(out / "offense_paths.parquet")])
    o = o.join(paths, on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    v2 = pl.read_parquet(out / "v2" / "scored.parquet", columns=["game_key", "gsis_play_id", "nfl_id", "align_role", "player_name", "resp_role"])

    # who covered him: coverage_defense's primary matchup, with that defender's v2 role on the snap
    cov = pl.read_parquet(next((out / "cache").glob("coverage_defense_*.parquet")))
    cov = cov.filter(pl.col("primary_matchup_player_gsis_id").is_not_null()).select(
        "game_key", "gsis_play_id", pl.col("nfl_id").alias("def_id"), pl.col("primary_matchup_player_gsis_id").cast(pl.Int64).alias("nfl_id"), "responsibility")
    cov = cov.join(v2.rename({"nfl_id": "def_id", "align_role": "def_role", "player_name": "def_name"}).drop("resp_role"),
                   on=["game_key", "gsis_play_id", "def_id"], how="left").unique(["game_key", "gsis_play_id", "nfl_id"])
    o = o.join(cov.select("game_key", "gsis_play_id", "nfl_id", "def_role", "def_name", pl.col("responsibility").alias("def_resp")),
               on=["game_key", "gsis_play_id", "nfl_id"], how="left")

    # his blocks: PFF's blocking chart, the defender he blocked and that defender's v2 role
    b = pl.read_parquet(out / "cache" / "pffplayerblockings_2022_2023_2024_2025.parquet").filter(pl.col("BlockedPlayerGsisId").is_not_null())
    b = b.select(pl.col("GsisGameId").cast(pl.Int64).alias("game_key"), pl.col("GsisPlayId").cast(pl.Int64).alias("gsis_play_id"),
                 pl.col("GsisPlayerId").cast(pl.Int64).alias("nfl_id"), pl.col("BlockedPlayerGsisId").cast(pl.Int64).alias("def_id"), "BlockType", "BlockLevel")
    b = b.join(v2.select("game_key", "gsis_play_id", pl.col("nfl_id").alias("def_id"), pl.col("align_role").alias("blocked_role")),
               on=["game_key", "gsis_play_id", "def_id"], how="left")
    seasons = o.select("game_key", "season").unique()
    b = b.join(seasons, on="game_key", how="inner")

    mix = o.group_by("nfl_id", "season").agg(
        pl.len().alias("snaps"), pl.col("player_name").drop_nulls().first(), pl.col("offense_team").mode().first().alias("team"),
        pl.col("ngs_position").mode().first().alias("roster_pos"), pl.col("peer_group").mode().first(),
        *[pl.col(f"p_off_{r}").mean().alias(f"share_{r}") for r in OFF_ROLES],
        (pl.col("off_role") == "WIDE").sum().alias("_wide"), ((pl.col("off_role") == "WIDE") & pl.col("on_line")).sum().alias("_x"),
        (pl.col("off_role") == "INLINE_TE").sum().alias("_te"), ((pl.col("off_role") == "INLINE_TE") & ~pl.col("on_line")).sum().alias("_wing"),
        pl.col("motion_code").is_not_null().mean().alias("motion_rate"), pl.col("motion_code").str.starts_with("*").fill_null(False).mean().alias("motion_at_snap_rate"),
        (pl.col("pff_off_role") == "Pass Route").sum().alias("routes"), pl.col("targeted").fill_null(False).sum().alias("targets"),
        pl.col("carrier").fill_null(False).sum().alias("carries"), pl.col("route_depth").mean().alias("mean_route_depth"),
    ).filter(pl.col("snaps") >= 100)
    P = np.stack([mix[f"share_{r}"].fill_null(0).to_numpy() for r in OFF_ROLES], 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        H = -(np.where(P > 0, P * np.log(P), 0)).sum(1)
    mix = mix.with_columns(pl.Series("align_entropy", H), pl.Series("primary_role", [OFF_ROLES[i] for i in P.argmax(1)]),
                           (pl.col("targets") / pl.col("routes")).alias("target_rate"),
                           (pl.col("_x") / pl.col("_wide")).alias("x_share_of_wide"), (pl.col("_wing") / pl.col("_te")).alias("wing_share_of_te"))
    mix = add_peer_percentiles(mix, cols=[f"share_{r}" for r in OFF_ROLES] + ["align_entropy", "target_rate", "motion_rate", "mean_route_depth"])

    def counts(df: pl.DataFrame, key: str, label=None) -> dict:
        res: dict = {}
        for r in df.filter(pl.col(key).is_not_null()).group_by("nfl_id", "season", key).len().iter_rows(named=True):
            d = res.setdefault((r["nfl_id"], r["season"]), {})
            k = label(r[key]) if label else r[key]
            d[k] = d.get(k, 0) + r["len"]
        return res
    role_mix = counts(o, "pff_off_role")
    routes = counts(o.filter(pl.col("route") != "Run Play"), "route")
    motions = counts(o.with_columns(pl.col("motion_code").map_elements(motion_kind, return_dtype=pl.Utf8).alias("motion_kind")), "motion_kind")
    covered_role = counts(o, "def_role")
    covered_resp = counts(o.with_columns(pl.col("def_resp").replace({"UNDER_ZONE": "Zone", "DEEP_ZONE": "Zone", "MAN": "Man", "MAN_MATCH": "Match (zone played as man)"})), "def_resp")
    covered_by = counts(o, "def_name")
    blk_type = counts(b.with_columns(pl.col("BlockType").replace_strict(BLOCK_TYPE, default=pl.col("BlockType"))), "BlockType")
    blk_role = counts(b, "blocked_role")

    ph = web_public / "ph"
    role_ix = {r: i for i, r in enumerate(OFF_ROLES)}
    players = []
    keys = set(zip(mix["nfl_id"].to_list(), mix["season"].to_list()))
    for r in mix.iter_rows(named=True):
        k = (r["nfl_id"], r["season"])
        top_def = dict(sorted(covered_by.get(k, {}).items(), key=lambda kv: -kv[1])[:8])
        players.append({
            "side": "O", "id": r["nfl_id"], "name": r["player_name"], "team": r["team"], "season": r["season"], "pos": r["roster_pos"],
            "group": r["peer_group"], "snaps": r["snaps"], "primary": r["primary_role"], "entropy": r["align_entropy"], "head": heads.get(str(r["nfl_id"])),
            "align": {x: r[f"share_{x}"] for x in OFF_ROLES}, "pct": {kk[4:]: v for kk, v in r.items() if kk.startswith("pct_") and v is not None},
            "usage": {"routes": r["routes"], "targets": r["targets"], "carries": r["carries"], "target_rate": r["target_rate"],
                      "mean_route_depth": r["mean_route_depth"], "motion_rate": r["motion_rate"], "motion_at_snap_rate": r["motion_at_snap_rate"],
                      "x_share_of_wide": r["x_share_of_wide"], "wing_share_of_te": r["wing_share_of_te"]},
            "roles_charted": role_mix.get(k, {}), "routes": routes.get(k, {}), "motions": motions.get(k, {}),
            "covered": {"by_role": covered_role.get(k, {}), "by_call": covered_resp.get(k, {}), "by_player": top_def},
            "blocking": {"types": blk_type.get(k, {}), "blocked_roles": blk_role.get(k, {})},
        })
    cols = ["game_key", "gsis_play_id", "week", "x_snap", "y_snap"] + [f"{a}_{i}" for i in range(1, 7) for a in ("x", "y")] + \
           ["off_role", "off_top_p", "route", "targeted", "carrier", "pff_off_role", "pff_DOWN", "pff_DISTANCE", "is_pass", "is_play_action",
            "defense_team", "def_role", "on_line"]
    have = [c for c in cols if c in o.columns]
    for (nid, season), g in o.select(["nfl_id", "season"] + have).group_by("nfl_id", "season"):
        if (nid, season) not in keys:
            continue
        g = g.sort("week", "gsis_play_id")
        snaps = []
        for r in g.iter_rows(named=True):
            path = [[None if r.get(f"x_{i}") is None else round(r[f"x_{i}"], 1), None if r.get(f"y_{i}") is None else round(r[f"y_{i}"], 1)] for i in range(1, 7)]
            snaps.append([r["game_key"], r["gsis_play_id"], r["week"], round(r["x_snap"], 1), round(r["y_snap"], 1), path,
                          role_ix.get(r["off_role"], -1), round(r["off_top_p"], 2), r["route"], 1 if r["targeted"] else 0, 1 if r["carrier"] else 0,
                          r["pff_off_role"], r["pff_DOWN"], r["pff_DISTANCE"], 1 if r["is_pass"] else 0, 1 if r["is_play_action"] else 0,
                          r["defense_team"], r["def_role"], 1 if r["on_line"] else 0])
        (ph / "p" / f"o{nid}_{season}.json").write_text(json.dumps(_clean({"snaps": snaps}), separators=(",", ":"), allow_nan=False))
    return players
