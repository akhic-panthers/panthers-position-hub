"""NGS Player Play tracking — one parquet per game, frame-level (~10 Hz), no ball track.

Layout (measured, audit/output/data_audit/NGS_DATA_STRUCTURE.md in panthers_projects):
    <season>_NGS_Player_Play/<week>/<game_key>.parquet        weeks 1–18, 19–21, 23 = postseason
    <season>_NGS_Player_Play/preseason/*.parquet              ⛔ DIFFERENT SCHEMA (play-level, 108 cols) — skipped
Columns: game_key, nfl_id, time, team_id, gsis_id, esb_id, player_name, jersey_number, position,
position_group, is_on_field, x, y, z(null), s, a, dis, o, dir, gsis_play_id, event, sa
Keys: game_key == pff_GSISGAMEKEY == coverage_defense.gsis_game_id; gsis_play_id shared;
      nfl_id == coverage_defense.gsis_player_id == pffdefense.pff_GSISPLAYERID.
Known gaps: 2024 week 2 and 2024 postseason are absent at source.

If the frames are ever registered in Unity Catalog (`POSHUB_TABLE_NGS_TRACKING`), `load_game`
reads that table filtered on game_key with the same output columns.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import polars as pl

from ..config import LocalDataConfig, _env

KEEP = ["game_key", "nfl_id", "gsis_id", "time", "team_id", "player_name", "jersey_number", "position",
        "position_group", "is_on_field", "x", "y", "s", "a", "dis", "o", "dir", "gsis_play_id", "event"]


def iter_game_files(season: int, root: Path | None = None, include_postseason: bool = True) -> Iterator[tuple[int, Path]]:
    """(week, path) for every regular/post-season game file. Preseason is skipped by design."""
    base = (root or LocalDataConfig().root) / f"{season}_NGS_Player_Play"
    if not base.exists():
        return
    for wk in sorted(os.listdir(base), key=lambda w: (not w.isdigit(), int(w) if w.isdigit() else 0)):
        if not wk.isdigit():
            continue  # 'preseason'
        w = int(wk)
        if w > 18 and not include_postseason:
            continue
        for f in sorted((base / wk).glob("*.parquet")):
            yield w, f


def load_game(path_or_key: Path | int, *, source=None) -> pl.DataFrame:
    """All frames of one game with `frame_id` (dense rank of time within play) attached.
    Rows with a null gsis_play_id (between plays, 57% of frames) are dropped."""
    uc_table = _env("POSHUB_TABLE_NGS_TRACKING")
    if isinstance(path_or_key, int) and uc_table and source is not None:
        df = source.dbx.query(f"SELECT {', '.join(KEEP)} FROM {uc_table} WHERE game_key = {int(path_or_key)}")
    else:
        lf = pl.scan_parquet(str(path_or_key))
        have = lf.collect_schema().names()
        df = lf.select([c for c in KEEP if c in have]).collect()
    df = df.filter(pl.col("gsis_play_id").is_not_null() & pl.col("is_on_field"))
    df = df.with_columns(pl.col("gsis_play_id").cast(pl.Int64), pl.col("game_key").cast(pl.Int64),
                         pl.col("nfl_id").cast(pl.Int64))
    df = df.with_columns(pl.col("time").rank("dense").over("gsis_play_id").cast(pl.Int32).alias("frame_id"))
    return df.sort(["gsis_play_id", "frame_id", "nfl_id"])


def plays_in_game(df: pl.DataFrame) -> list[int]:
    return df.get_column("gsis_play_id").unique().sort().to_list()
