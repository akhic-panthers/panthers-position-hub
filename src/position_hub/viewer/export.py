"""Viewer export — the JSON the static viewer (viewer/index.html) and the sister app read.

Shape mirrors web/public/dev/pos_boards.json in panthers_projects: {meta, players:[...]} with every
number documented once in `meta.metrics_doc`. Percentiles are within peer group × season. No
composite score: each column answers one question.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ..config import MIN_SNAPS_FOR_MIX, MIN_SNAPS_FOR_PERCENTILE
from ..roles.taxonomy import ALIGN_ROLES, PRIMARY_ROLES_OF_GROUP, RESPONSIBILITIES, ROLE_LABEL

CAVEATS = [
    "Role shares are DESCRIPTIVE: what the tracking says he did on his snaps this season. They are not a grade and not a projection.",
    "Alignment shares count the role he lined up in on each snap, read from the tracking at the snap. In v1 the per-snap call is effectively certain, so a share is a count, not a blend of probabilities.",
    "Responsibility on pass snaps is PFF's charted assignment where charted; otherwise the tracking model's estimate. Run snaps are geometric (run fit / rush).",
    "Percentiles are within roster position group and season, among players above the snap floor. A high percentile means MORE of that job than peers, not better at it.",
    f"Players under {MIN_SNAPS_FOR_MIX} snaps are not shown; percentiles need {MIN_SNAPS_FOR_PERCENTILE}.",
    "Left and right are folded: the mirror image of a job is the same job.",
    "For safeties, the one-high / two-high split shows how much of the mix is the call. Where the call explains most of it, the mix describes the defense he plays in as much as the player.",
]


def export_viewer_json(mix: pl.DataFrame, out: Path, gates: list[dict] | None = None, source: str = "",
                       team_mix: pl.DataFrame | None = None, call: pl.DataFrame | None = None) -> dict:
    calls = {}
    if call is not None and call.height:
        for c in call.iter_rows(named=True):
            calls[(c["nfl_id"], c["season"])] = {k: c[k] for k in ("deep_share_one_high", "deep_share_two_high", "middle_share_one_high",
                                                                    "box_share_one_high", "call_explains")}
    players = []
    for r in mix.iter_rows(named=True):
        align = {role: r.get(f"share_{role}") for role in ALIGN_ROLES if r.get(f"share_{role}") is not None}
        hard = {role: r.get(f"hard_share_{role}") for role in ALIGN_ROLES if r.get(f"hard_share_{role}") is not None}
        resp = {c: r.get(f"resp_{c}") for c in RESPONSIBILITIES if r.get(f"resp_{c}") is not None}
        pct = {k[4:]: v for k, v in r.items() if k.startswith("pct_") and v is not None}
        players.append({
            "nfl_id": r["nfl_id"], "name": r.get("player_name"), "roster_pos": r.get("roster_pos"), "peer_group": r.get("peer_group"),
            "team": r.get("team"), "season": r.get("season"), "snaps": r["snaps"], "pass_snap_share": r.get("pass_snap_share"),
            "primary_role": r.get("primary_role"), "align_entropy": r.get("align_entropy"),
            "mean_depth": r.get("mean_depth"), "box_rate": r.get("box_rate"),
            "mean_bite_2s": r.get("mean_bite_2s"), "mean_ground_covered_2s": r.get("mean_ground_covered_2s"),
            "align": align, "align_hard": hard, "resp": resp, "pct": pct,
            "by_call": calls.get((r["nfl_id"], r.get("season"))),
        })
    doc = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(), "source": source,
            "attribution": "position-hub v0.1 — positional role attribution from NGS tracking geometry + PFF charting. "
                           "Method after Eager & Seth (2023) for the 2 s post-snap window; role taxonomy registered in docs/.",
            "caveats": CAVEATS,
            "roles": {"align": ALIGN_ROLES, "resp": RESPONSIBILITIES, "labels": ROLE_LABEL, "primary_by_group": PRIMARY_ROLES_OF_GROUP},
            "metrics_doc": {
                "align.<ROLE>": "mean P(alignment role) over his snaps",
                "align_hard.<ROLE>": "share of snaps where ROLE was the most likely alignment",
                "resp.<CLASS>": "share of snaps by responsibility (charted where PFF charted it, else modelled/geometric)",
                "pct.<col>": "percentile within peer_group × season among players ≥ snap floor (100 × share of peers ≤ his value)",
                "align_entropy": "entropy of the alignment mix in nats: 0 = one job every snap",
                "mean_depth": "mean depth off the ball at the snap, yards",
                "box_rate": "share of snaps inside the tackle box (≤ 7 yd, inside the tackles' width + 1.5)",
                "mean_bite_2s": "mean change in depth 2 s after the snap; negative = toward the line (Eager & Seth's bite)",
                "mean_ground_covered_2s": "mean yards moved in the first 2 s",
            },
            "gates": gates or [],
        },
        "players": players,
    }
    if team_mix is not None:
        doc["teams"] = team_mix.to_dicts()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_clean(doc), indent=1, default=_json_default, allow_nan=False))
    return doc


def _json_default(o):
    import math

    if isinstance(o, float) and math.isnan(o):
        return None
    return str(o)


def export_pos_boards(mix: pl.DataFrame, out: Path, gates: list[dict] | None = None) -> dict:
    """The sister app's board shape (web/public/dev/pos_boards.json: {meta, boards: {GROUP: {players: [...]}}}),
    keyed by `gsis` = nfl_id like the existing boards. One row per player, seasons nested. No composite score."""
    boards: dict[str, dict] = {}
    for (grp,), g in mix.group_by("peer_group"):
        players = []
        for (nid,), pg in g.group_by("nfl_id"):
            pg = pg.sort("season")
            last = pg.row(-1, named=True)
            seasons = [{"season": r["season"], "team": r.get("team"), "snaps": r["snaps"], "primary_role": r.get("primary_role"),
                        "align": {k: round(r[f"share_{k}"], 4) for k in ALIGN_ROLES if r.get(f"share_{k}") is not None},
                        "resp": {k: round(r[f"resp_{k}"], 4) for k in RESPONSIBILITIES if r.get(f"resp_{k}") is not None},
                        "pct": {k[4:]: round(v, 1) for k, v in r.items() if k.startswith("pct_") and v is not None and v == v},
                        "align_entropy": r.get("align_entropy"), "mean_depth": r.get("mean_depth"), "box_rate": r.get("box_rate")}
                       for r in pg.iter_rows(named=True)]
            players.append({"gsis": nid, "name": last.get("player_name"), "team": last.get("team"), "last": last["season"],
                            "n": int(pg["snaps"].sum()), "n_seasons": pg.height, "primary_role": last.get("primary_role"), "seasons": seasons})
        boards[f"ROLE_{grp}"] = {"headline": "primary_role", "players": sorted(players, key=lambda p: -p["n"])}
    doc = {"meta": {"attribution": "Position hub — per-snap alignment role and responsibility from NGS tracking geometry with PFF charting as the check; "
                                   "player-season role mix = mean over snaps. Method after Eager & Seth (2023) for the 2 s window.",
                    "caveats": CAVEATS, "roles": {"align": ALIGN_ROLES, "resp": RESPONSIBILITIES, "labels": ROLE_LABEL}, "gates": gates or []},
           "boards": boards}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_clean(doc), default=_json_default, allow_nan=False))
    return doc


def _clean(o):
    """NaN / inf → null, recursively. A bare NaN breaks JSON.parse in every browser (sister-project landmine; hit again
    here on the first real export, 2026-09-25). `allow_nan=False` on the dump makes a miss loud instead of silent."""
    import math

    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o
