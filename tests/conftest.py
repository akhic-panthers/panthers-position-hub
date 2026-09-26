import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from position_hub.ngs.features import defender_features_for_game  # noqa: E402
from position_hub.pff.vocab import align_family  # noqa: E402
from position_hub.roles.rules import add_rule_roles  # noqa: E402
from position_hub.synth import make_season  # noqa: E402


def frames_to_game(g: pl.DataFrame) -> pl.DataFrame:
    g = g.filter(pl.col("is_on_field")).with_columns(pl.col("gsis_play_id").cast(pl.Int64))
    return g.with_columns(pl.col("time").rank("dense").over("gsis_play_id").cast(pl.Int32).alias("frame_id")).sort(["gsis_play_id", "frame_id", "nfl_id"])


@pytest.fixture(scope="session")
def season():
    """A small synthetic season with hidden truth: (features_with_truth, truth, frames)."""
    fr, truth = make_season(n_games=6, plays_per_game=44, seed=11)
    feats = []
    for gk, g in fr.group_by("game_key"):
        f = defender_features_for_game(frames_to_game(g))
        feats.append(f.with_columns(pl.lit(2025).alias("season"), pl.lit(int(gk[0]) % 100 + 1).alias("week")))
    feats = pl.concat(feats, how="diagonal_relaxed")
    rng = np.random.default_rng(1)
    tr = truth.with_columns(pl.col("pff_alignment").map_elements(align_family, return_dtype=pl.Utf8).alias("pff_align_family"))
    tr = tr.with_columns(pl.Series("responsibility", [r if (rng.random() < 0.6 and p) else None for r, p in zip(tr["true_responsibility"], tr["is_pass"])]))
    feats = feats.join(tr.select("game_key", "gsis_play_id", "nfl_id", "pff_alignment", "pff_align_family", "responsibility",
                                 "true_align_role", "true_responsibility", "is_pass"), on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    return add_rule_roles(feats), truth, fr


@pytest.fixture(autouse=True)
def _no_machine_credentials(monkeypatch):
    """Tests never see this machine's Databricks / Thunder settings. The repo-root .env (gitignored) is real on the
    Mac and `poshub` loads it at start; without this, one CLI test leaks DATABRICKS_CONFIG_PROFILE into the rest."""
    import position_hub.cli as cli

    for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_HTTP_PATH", "DATABRICKS_CONFIG_PROFILE", "ARM_TENANT_ID",
              "ARM_CLIENT_ID", "ARM_CLIENT_SECRET", "THUNDER_USERNAME", "THUNDER_PASSWORD", "THUNDER_VENDOR_GUID", "OPENFIELD_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
