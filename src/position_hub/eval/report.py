"""`poshub report` — the aggregate tables REPORT.md is written from. Aggregates only; names, never ids, in anything
a person reads. The prose is written by a person (or Claude) on top of these tables, not generated here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from ..roles.taxonomy import ALIGN_ROLES, RESPONSIBILITIES, ROLE_LABEL

SHORT = {"EDGE": "edge", "INTERIOR_DL": "interior", "OFF_BALL_LB": "off-ball LB", "OVERHANG": "overhang", "SLOT_CB": "slot",
         "BOUNDARY_CB": "boundary CB", "BOX_SAFETY": "box S", "DEEP_HALF": "deep half", "DEEP_MIDDLE": "deep middle"}


def _mix_str(r: dict, floor: float = 0.05) -> str:
    parts = sorted(((r.get(f"share_{k}") or 0.0, k) for k in ALIGN_ROLES), reverse=True)
    return " · ".join(f"{v:.0%} {SHORT[k]}" for v, k in parts if v >= floor)


def _resp_str(r: dict, floor: float = 0.05) -> str:
    parts = sorted(((r.get(f"resp_{k}") or 0.0, k) for k in RESPONSIBILITIES), reverse=True)
    return " · ".join(f"{v:.0%} {ROLE_LABEL[k].lower()}" for v, k in parts if v >= floor)


def population(f: pl.DataFrame) -> list[str]:
    g = f.group_by("season").agg(
        pl.col("game_key").n_unique().alias("games"), pl.struct("game_key", "gsis_play_id").n_unique().alias("plays"),
        pl.len().alias("snaps"), pl.col("nfl_id").n_unique().alias("defenders"),
        pl.col("pff_alignment").is_not_null().mean().alias("pff"),
        pl.col("responsibility").filter(pl.col("is_pass") == True).is_not_null().mean().alias("cov_pass"),  # noqa: E712
        (pl.col("responsibility_source") == "coverage_defense").filter(pl.col("is_pass") == True).mean().alias("cov_src"),  # noqa: E712
        pl.col("ngs_role").is_not_null().mean().alias("ngs"), (pl.col("is_pass") == True).mean().alias("pass_share"),  # noqa: E712
        (pl.col("ball_proxy") == "center").mean().alias("ctr")).sort("season")
    L = ["| season | games | plays | defender-snaps | defenders | → pffdefense | pass snaps with charted responsibility | of which coverage_defense | → NGS play-level | pass share | tagged center |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in g.iter_rows(named=True):
        L.append(f"| {r['season']} | {r['games']} | {r['plays']:,} | {r['snaps']:,} | {r['defenders']:,} | {r['pff']:.1%} | {r['cov_pass']:.1%} | "
                 f"{r['cov_src']:.1%} | {r['ngs']:.1%} | {r['pass_share']:.1%} | {r['ctr']:.1%} |")
    return L


def soft_hard_gap(mix: pl.DataFrame) -> list[str]:
    S = np.stack([mix[f"share_{k}"].fill_null(0).to_numpy() for k in ALIGN_ROLES], 1)
    H = np.stack([mix[f"hard_share_{k}"].fill_null(0).to_numpy() for k in ALIGN_ROLES], 1)
    tv = 0.5 * np.abs(S - H).sum(1)
    out = ["| peer group | player-seasons | soft vs hard gap, median | p90 |", "|---|---|---|---|"]
    for grp in sorted(mix["peer_group"].unique().to_list()):
        m = (mix["peer_group"] == grp).to_numpy()
        out.append(f"| {grp} | {m.sum()} | {np.median(tv[m]):.1%} | {np.quantile(tv[m], .9):.1%} |")
    out.append(f"| all | {len(tv)} | {np.median(tv):.1%} | {np.quantile(tv, .9):.1%} |")
    return out


def team_table(mix: pl.DataFrame, team: str, seasons: list[int], groups=("S", "CB", "LB", "DB", "EDGE", "IDL"), min_snaps: int = 150) -> list[str]:
    t = mix.filter((pl.col("team") == team) & pl.col("season").is_in(seasons) & pl.col("peer_group").is_in(list(groups)) & (pl.col("snaps") >= min_snaps))
    L = ["| player | season | listed | snaps | where he lined up | what he did after the snap | depth pct | box pct | jobs (entropy) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in t.sort(["season", "peer_group", "snaps"], descending=[False, False, True]).iter_rows(named=True):
        pdp, pbx = r.get("pct_mean_depth"), r.get("pct_box_rate")
        L.append(f"| {r['player_name']} | {r['season']} | {r['roster_pos']} | {r['snaps']} | {_mix_str(r)} | {_resp_str(r)} | "
                 f"{'' if pdp is None or np.isnan(pdp) else f'{pdp:.0f}'} | {'' if pbx is None or np.isnan(pbx) else f'{pbx:.0f}'} | {r['align_entropy']:.2f} |")
    return L


def named(mix: pl.DataFrame, names: list[str], seasons: list[int]) -> list[str]:
    t = mix.filter(pl.col("player_name").is_in(names) & pl.col("season").is_in(seasons))
    L = ["| player | team | season | listed | snaps | where he lined up | what he did after the snap | jobs |", "|---|---|---|---|---|---|---|---|"]
    for r in t.sort(["player_name", "season"]).iter_rows(named=True):
        L.append(f"| {r['player_name']} | {r['team']} | {r['season']} | {r['roster_pos']} | {r['snaps']} | {_mix_str(r)} | {_resp_str(r)} | {r['align_entropy']:.2f} |")
    return L


def leaders(mix: pl.DataFrame, col: str, group: str, season: int, n: int = 8, min_snaps: int = 400) -> list[str]:
    t = mix.filter((pl.col("peer_group") == group) & (pl.col("season") == season) & (pl.col("snaps") >= min_snaps)).sort(col, descending=True).head(n)
    return [f"{r['player_name']} ({r['team']}) {r[col]:.0%}" for r in t.iter_rows(named=True)]


def call_split(call: pl.DataFrame, names: list[str] | None = None, n: int = 12) -> list[str]:
    if call.height == 0:
        return ["(no call table)"]
    t = call.filter(pl.col("player_name").is_in(names)) if names else call.sort("snaps", descending=True).head(n)
    L = ["| safety | team | season | snaps | deep share, one-high call | deep share, two-high call | deep middle, one-high | box, one-high | call explains |",
         "|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: "—" if v is None else f"{v:.0%}"
    for r in t.sort(["season", "snaps"], descending=[False, True]).iter_rows(named=True):
        L.append(f"| {r['player_name']} | {r['team']} | {r['season']} | {r['snaps']} | {f(r['deep_share_one_high'])} | {f(r['deep_share_two_high'])} | "
                 f"{f(r['middle_share_one_high'])} | {f(r['box_share_one_high'])} | {f(r['call_explains'])} |")
    return L


def build(out: Path, run: Path, team: str = "CAR", named_players: list[str] | None = None) -> str:
    f = pl.read_parquet(out / "scored.parquet")
    mix = pl.read_parquet(out / "role_mix.parquet")
    seasons = sorted(mix["season"].unique().to_list())
    L = ["# report tables", "", "## population and joins", ""] + population(f)
    L += ["", "## soft vs hard share gap (total variation between mean probability and argmax share)", ""] + soft_hard_gap(mix)
    L += ["", f"## {team} defenders, {seasons[-2:][0]}–{seasons[-1]} (≥ 150 snaps)", ""] + team_table(mix, team, seasons[-2:], min_snaps=min(150, int(mix["snaps"].min())))
    if named_players:
        L += ["", "## named players league-wide", ""] + named(mix, named_players, seasons[-2:])
    L += ["", "## who leads each job (≥ 400 snaps, latest season)", ""]
    for col, grp, lab in (("share_DEEP_MIDDLE", "S", "deep middle, safeties"), ("share_BOX_SAFETY", "S", "box, safeties"),
                          ("share_SLOT_CB", "S", "slot, safeties"), ("share_SLOT_CB", "CB", "slot, corners"),
                          ("share_OVERHANG", "LB", "overhang, linebackers"), ("share_EDGE", "LB", "edge, linebackers")):
        L.append(f"- {lab}: " + ", ".join(leaders(mix, col, grp, seasons[-1])))
    call = pl.read_parquet(out / "safety_mix_by_call.parquet") if (out / "safety_mix_by_call.parquet").exists() else pl.DataFrame()
    if call.height:
        L += ["", "## safeties by the call (pff_MOFOCPLAYED), most snaps", ""] + call_split(call.filter(pl.col("season") == seasons[-1]))
        L += ["", f"## {team} safeties by the call", ""] + call_split(call.filter(pl.col("team") == team))
    md = "\n".join(L) + "\n"
    run.mkdir(parents=True, exist_ok=True)
    (run / "report_tables.md").write_text(md)
    return md


def gate_json(out: Path) -> list[dict]:
    p = out / "gates.json"
    return json.loads(p.read_text()) if p.exists() else []
