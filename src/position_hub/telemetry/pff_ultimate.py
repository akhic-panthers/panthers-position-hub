"""PFF Ultimate — film links only. PFF exposes NO API in this stack; everything PFF arrives as the
bronze tables in Unity Catalog. What Ultimate gives us is a play page per PFF play id, which is the
"pro film" a scout opens from a role snap.

A role snap is keyed by (game_key, gsis_play_id, nfl_id). pffplays carries both key spaces
(pff_GAMEID/pff_PLAYID and pff_GSISGAMEKEY/pff_GSISPLAYID), so the crosswalk is a join, not a table.
"""
from __future__ import annotations

import polars as pl

from ..config import PFFUltimateConfig


def pff_ultimate_play_url(pff_play_id: int | str, cfg: PFFUltimateConfig | None = None) -> str:
    cfg = cfg or PFFUltimateConfig()
    return f"{cfg.base_url}/play/{pff_play_id}"


def film_links_for_snaps(snaps: pl.DataFrame, plays: pl.DataFrame, thunder_token: str | None = None,
                         thunder_vendor: str | None = None) -> pl.DataFrame:
    """Attach `pff_ultimate_url` (always) and `thunder_url` (when an SSO token + vendor GUID exist)
    to scored snaps. `plays` is load_play_context() output (needs pff_PLAYID, game_key, gsis_play_id)."""
    from .thunder import launch_by_gsis

    key = plays.select("game_key", "gsis_play_id", "pff_PLAYID").unique()
    out = snaps.join(key, on=["game_key", "gsis_play_id"], how="left")
    out = out.with_columns(pl.col("pff_PLAYID").map_elements(lambda p: pff_ultimate_play_url(int(p)) if p is not None else None,
                                                             return_dtype=pl.Utf8).alias("pff_ultimate_url"))
    if thunder_token and thunder_vendor:
        out = out.with_columns(pl.struct(["game_key", "gsis_play_id"]).map_elements(
            lambda s: launch_by_gsis([(s["game_key"], s["gsis_play_id"])], thunder_token, thunder_vendor),
            return_dtype=pl.Utf8).alias("thunder_url"))
    else:
        out = out.with_columns(pl.lit(None, pl.Utf8).alias("thunder_url"))
    return out
