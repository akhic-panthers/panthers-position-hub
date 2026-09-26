"""The exact command sequence scripts/first_run.sh runs, against a synthetic Mac layout: tracking under
<root>/<season>_NGS_Player_Play/<week>/ and the PFF export under <root>/data/pff_export/. Local source,
parallel workers, then fit → score → mix → summarize. Needs duckdb for the local WHERE filter."""
import os

import polars as pl
import pytest

pytest.importorskip("duckdb")

from position_hub.cli import main  # noqa: E402
from position_hub.synth import make_season, write_local_export  # noqa: E402


def test_first_run_sequence_on_local_layout(tmp_path, monkeypatch, capsys):
    frames, truth = make_season(n_games=6, plays_per_game=36, seed=5)
    write_local_export(tmp_path, frames, truth, season=2025)
    monkeypatch.setenv("PANTHERS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    out = tmp_path / "out"

    assert main(["--out", str(out), "features", "--seasons", "2025", "--workers", "2", "--source", "local"]) == 0
    f = pl.read_parquet(out / "features.parquet")
    assert f.height > 1500 and f["pff_alignment"].is_not_null().mean() > 0.99, "PFF join through (game_key, gsis_play_id, nfl_id)"
    cov_share = (f["responsibility_source"] == "coverage_defense").mean()
    assert 0.3 < cov_share < 0.8, "coverage_defense charts coverage players on pass snaps only"
    assert set(f.filter(pl.col("responsibility_source") == "pffdefense.pff_ROLE")["responsibility"].unique().to_list()) <= {"RUSH", "RUN_FIT"}
    assert set(f["week"].unique().to_list()) <= {1, 2, 3}
    assert "is_pass" in f.columns and f["is_pass"].is_not_null().all()
    assert not (out / "features_errors.txt").exists()

    assert main(["--out", str(out), "fit", "--holdout-weeks", "3", "--seed", "0"]) == 0
    assert (out / "model.pkl").exists() and (out / "model.json").exists()
    assert main(["--out", str(out), "score"]) == 0
    assert main(["--out", str(out), "mix", "--min-snaps", "40", "--min-snaps-pct", "40", "--viewer-json", str(tmp_path / "v.json")]) == 0
    assert (out / "role_mix.parquet").exists() and (out / "gates.md").exists() and (tmp_path / "v.json").exists()
    run_dir = tmp_path / "runs" / "x"
    assert main(["--out", str(out), "summarize", "--run-dir", str(run_dir)]) == 0
    md = (run_dir / "summary.md").read_text()
    assert "## features" in md and "## gates" in md and "## role mix" in md and "| 2025 |" in md
    # only a markdown summary lands in the run folder: no rows, no parquet
    assert [p.name for p in run_dir.iterdir()] == ["summary.md"]


def test_features_reports_a_broken_game_file_instead_of_dying(tmp_path, monkeypatch):
    frames, truth = make_season(n_games=2, plays_per_game=12, seed=9)
    write_local_export(tmp_path, frames, truth, season=2025)
    bad = tmp_path / "2025_NGS_Player_Play" / "1" / "99999.parquet"
    bad.write_bytes(b"not a parquet file")
    monkeypatch.setenv("PANTHERS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    out = tmp_path / "out"
    assert main(["--out", str(out), "features", "--seasons", "2025", "--workers", "1", "--source", "local"]) == 0
    errs = (out / "features_errors.txt").read_text()
    assert "99999.parquet" in errs
    assert pl.read_parquet(out / "features.parquet").height > 0
