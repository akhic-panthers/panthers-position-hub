"""Player-season role mix and peer percentiles — the numbers the viewer shows.

Role mix = mean of the per-snap probability vectors (soft share). `hard_share_<ROLE>` is the share of
snaps where the role was the argmax; the two disagree exactly where the geometry is ambiguous, and
both are kept so nobody has to guess which one they are looking at.

Percentiles are empirical CDFs within a peer group (roster position group × season), the same
construction the sister app uses: pct = 100 · mean(values ≤ x). Peers below the snap floor are not
in the denominator. A percentile answers "how much more of this job than his peers", not "how good".
"""
from __future__ import annotations

import numpy as np
import polars as pl

from ..config import MIN_SNAPS_FOR_MIX, MIN_SNAPS_FOR_PERCENTILE
from .taxonomy import ALIGN_ROLES, RESPONSIBILITIES, ROSTER_GROUP_OF


def _share_cols(df: pl.DataFrame, prefix: str, classes: list[str], out_prefix: str) -> list[pl.Expr]:
    return [pl.col(f"{prefix}{c}").mean().alias(f"{out_prefix}{c}") for c in classes if f"{prefix}{c}" in df.columns]


def player_role_mix(scored: pl.DataFrame, season_col: str = "season", min_snaps: int = MIN_SNAPS_FOR_MIX) -> pl.DataFrame:
    if season_col not in scored.columns:
        scored = scored.with_columns(pl.lit(0).alias(season_col))
    keys = ["nfl_id", season_col]
    aggs = [
        pl.len().alias("snaps"),
        pl.col("player_name").drop_nulls().first().alias("player_name") if "player_name" in scored.columns else pl.lit(None).alias("player_name"),
        pl.col("ngs_position").drop_nulls().mode().first().alias("roster_pos") if "ngs_position" in scored.columns else pl.lit(None).alias("roster_pos"),
        pl.col("defense_team").drop_nulls().mode().first().alias("team") if "defense_team" in scored.columns else pl.lit(None).alias("team"),
        pl.col("has_throw").cast(pl.Float64).mean().alias("pass_snap_share") if "has_throw" in scored.columns else pl.lit(None).alias("pass_snap_share"),
        pl.col("depth").mean().alias("mean_depth"),
        pl.col("depth").quantile(0.5).alias("median_depth"),
        pl.col("abs_lateral").mean().alias("mean_abs_lateral"),
        pl.col("in_box").cast(pl.Float64).mean().alias("box_rate"),
        pl.col("bite_2s").mean().alias("mean_bite_2s"),
        pl.col("ground_covered_2s").mean().alias("mean_ground_covered_2s"),
    ]
    aggs += _share_cols(scored, "p_align_", ALIGN_ROLES, "share_")
    aggs += _share_cols(scored, "p_resp_", RESPONSIBILITIES, "resp_")
    aggs += [((pl.col("align_role") == r).cast(pl.Float64).mean()).alias(f"hard_share_{r}") for r in ALIGN_ROLES]
    # entropy of the alignment mix: 0 = one job every snap; ln(9) = spread over everything
    mix = scored.group_by(keys).agg(aggs)
    P = np.stack([mix.get_column(f"share_{r}").fill_null(0).to_numpy() for r in ALIGN_ROLES if f"share_{r}" in mix.columns], 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        H = -(np.where(P > 0, P * np.log(P), 0)).sum(1)
    mix = mix.with_columns(pl.Series("align_entropy", H))
    top = [ALIGN_ROLES[i] for i in P.argmax(1)] if P.size else []
    mix = mix.with_columns(pl.Series("primary_role", top, dtype=pl.Utf8) if top else pl.lit(None).alias("primary_role"))
    mix = mix.with_columns(pl.col("roster_pos").map_elements(lambda p: ROSTER_GROUP_OF.get(p or "", "DB"), return_dtype=pl.Utf8).alias("peer_group"))
    return mix.filter(pl.col("snaps") >= min_snaps).sort(["peer_group", "snaps"], descending=[False, True])


def add_peer_percentiles(mix: pl.DataFrame, cols: list[str] | None = None, season_col: str = "season",
                         min_snaps: int = MIN_SNAPS_FOR_PERCENTILE) -> pl.DataFrame:
    """pct_<col> within (peer_group, season) among players with ≥ min_snaps. Others get null."""
    if cols is None:
        cols = [c for c in mix.columns if c.startswith(("share_", "resp_"))] + ["mean_depth", "box_rate", "align_entropy"]
    elig = pl.col("snaps") >= min_snaps
    exprs = []
    for c in cols:
        if c not in mix.columns:
            continue
        # empirical CDF among eligible peers: share of eligible peers with value <= mine
        ranked = (pl.col(c).rank("max").over(["peer_group", season_col], mapping_strategy="group_to_rows"))
        exprs.append(
            pl.when(elig)
            .then((pl.col(c).filter(elig).rank("max") / pl.col(c).filter(elig).count() * 100.0)
                  .over(["peer_group", season_col], mapping_strategy="group_to_rows"))
            .otherwise(None).alias(f"pct_{c}"))
        del ranked
    # polars cannot align a filtered window back to rows directly; do it in numpy per group instead
    out = mix.clone()
    for c in cols:
        if c not in mix.columns:
            continue
        vals = np.full(mix.height, np.nan)
        arr = mix.get_column(c).cast(pl.Float64).fill_null(np.nan).to_numpy()
        snaps = mix.get_column("snaps").to_numpy()
        groups = list(zip(mix.get_column("peer_group").to_list(), mix.get_column(season_col).to_list()))
        for g in set(groups):
            idx = np.array([i for i, gg in enumerate(groups) if gg == g])
            el = idx[snaps[idx] >= min_snaps]
            if len(el) == 0:
                continue
            ref = arr[el]
            ref = ref[~np.isnan(ref)]
            if len(ref) == 0:
                continue
            for i in el:
                if not np.isnan(arr[i]):
                    vals[i] = 100.0 * np.mean(ref <= arr[i])
        out = out.with_columns(pl.Series(f"pct_{c}", vals))
    return out


def team_role_mix(scored: pl.DataFrame, season_col: str = "season") -> pl.DataFrame:
    """How a defense distributes jobs: mean probability per role per (team, season) and the
    shell mix (share of snaps at 0/1/2/3 deep)."""
    if season_col not in scored.columns:
        scored = scored.with_columns(pl.lit(0).alias(season_col))
    per_play = scored.group_by(["defense_team", season_col, "game_key", "gsis_play_id"]).agg(pl.col("n_deep").first())
    shell = per_play.group_by(["defense_team", season_col]).agg(
        [(pl.col("n_deep") == k).cast(pl.Float64).mean().alias(f"shell_{k}_high") for k in (0, 1, 2)]
        + [(pl.col("n_deep") >= 3).cast(pl.Float64).mean().alias("shell_3plus_high"), pl.len().alias("plays")])
    roles = scored.group_by(["defense_team", season_col]).agg(_share_cols(scored, "p_align_", ALIGN_ROLES, "share_")
                                                              + _share_cols(scored, "p_resp_", RESPONSIBILITIES, "resp_"))
    return shell.join(roles, on=["defense_team", season_col], how="left").sort(["defense_team", season_col])
