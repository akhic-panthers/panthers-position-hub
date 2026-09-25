"""`poshub` — the pipeline as commands. Every step reads/writes parquet under --out so a step can
be re-run alone (features are the expensive part; roles are cheap to re-score).

    poshub status                         what is reachable: Databricks, local export, Thunder, OpenField
    poshub probe                          the Databricks connection ladder: host → auth → catalog → warehouse → SQL → tables
    poshub sql "SELECT ..."               one statement through the SQL warehouse
    poshub discover                       write data_contracts/uc_inventory.json from Unity Catalog
    poshub features  --seasons 2024 2025  NGS + PFF → out/features.parquet   (one row per defender-snap)
    poshub fit       --holdout-weeks 17 18 fit the two role models → out/model.pkl
    poshub score                          out/scored.parquet (probabilities per snap)
    poshub mix                            out/role_mix.parquet + gates + viewer/data/role_mix.json
    poshub summarize --run-dir runs/X     aggregates + join rates + gates as markdown (what gets pushed)
    poshub demo                           the whole thing on synthetic tracking (no data needed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

from .config import LocalDataConfig, load_dotenv


def cmd_status(a) -> int:
    from .databricks.client import DatabricksConfig, UnityCatalogClient
    from .telemetry.openfield import OpenFieldClient
    from .telemetry.thunder import ThunderClient

    cfg = DatabricksConfig()
    ok, detail = UnityCatalogClient(cfg).reachable()
    print(f"databricks   host={cfg.host or '(unset)'} reachable={ok} detail={detail} missing={cfg.missing()} http_path={'set' if cfg.http_path else 'unset'}")
    loc = LocalDataConfig()
    have = [t for t in ("pffplays", "pffdefense", "coverage_defense") if loc.pff_export_dir(t).exists()]
    ngs = [s for s in range(2022, 2027) if loc.ngs_season_dir(s).exists()]
    print(f"local        root={loc.root} pff_export={have or 'none'} ngs_seasons={ngs or 'none'}")
    if not a.offline:
        print(f"thunder      {ThunderClient().status()}")
        print(f"openfield    {OpenFieldClient().probe()}")
    return 0


def cmd_probe(a) -> int:
    from .databricks.probe import probe

    rep = probe()
    print(rep.format())
    if a.json:
        Path(a.json).write_text(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.ok else 2


def cmd_sql(a) -> int:
    from .databricks.client import DatabricksSQL

    df = DatabricksSQL().query(a.statement)
    print(df)
    if a.out_file:
        df.write_parquet(a.out_file)
    return 0


def cmd_discover(a) -> int:
    from .databricks.discover import discover

    inv = discover(Path(a.out_file), catalogs_filter=a.catalog)
    print(f"reachable={inv['reachable']} detail={inv['detail']} catalogs={len(inv['catalogs'])} ngs_candidates={inv['ngs_candidates']}")
    for k, v in inv["pff_tables"].items():
        print(f"  {k:26s} {v['full_name']:45s} {'cols=' + str(len(v['columns'])) if 'columns' in v else v.get('error')}")
    return 0 if inv["reachable"] else 2


def _process_game(args: tuple) -> "pl.DataFrame | None":
    """Top-level so ProcessPoolExecutor can pickle it. One game file → per-defender features."""
    path, season, week = args
    from .ngs.features import defender_features_for_game
    from .ngs.loader import load_game

    try:
        g = load_game(path)
        f = defender_features_for_game(g)
    except Exception as e:  # a broken game file is a fact to report, not a reason to lose the run
        return pl.DataFrame({"_error": [f"{path}: {type(e).__name__}: {str(e)[:200]}"], "season": [season], "week": [week]})
    if f.height == 0:
        return None
    return f.with_columns(pl.lit(season).alias("season"), pl.lit(week).alias("week"))


def cmd_features(a) -> int:
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from .databricks.client import get_source
    from .ngs.loader import iter_game_files
    from .pff.loaders import load_coverage_assignments, load_defender_snaps, load_play_context
    from .roles.rules import add_rule_roles

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    src = get_source(a.source)
    print(f"source: {src.describe()}")
    plays = load_play_context(src, a.seasons)
    print(f"pffplays: {plays.height:,} plays, seasons {sorted(plays['season'].unique().to_list())}")
    dsnaps = load_defender_snaps(src, plays)
    cov = load_coverage_assignments(src, a.seasons)
    print(f"pffdefense: {dsnaps.height:,} defender-snaps · coverage_defense: {cov.height:,} rows")
    root = LocalDataConfig().root
    jobs = []
    for season in a.seasons:
        n = 0
        for week, f in iter_game_files(season, root):
            if a.weeks and week not in a.weeks:
                continue
            jobs.append((str(f), season, week))
            n += 1
            if a.max_games and n >= a.max_games:
                break
        print(f"  {season}: {n} game files queued")
    if not jobs:
        print("no tracking games found under", root, "— set PANTHERS_DATA_DIR or POSHUB_TABLE_NGS_TRACKING", file=sys.stderr)
        return 2
    workers = a.workers or max(1, min(8, (os.cpu_count() or 2) - 1))
    frames, errors, done = [], [], 0
    print(f"  {len(jobs)} games on {workers} workers")
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_process_game, j): j for j in jobs}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r is None:
                continue
            if "_error" in r.columns:
                errors.append(r["_error"][0])
            else:
                frames.append(r)
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} games · {sum(f.height for f in frames):,} defender-snaps · {len(errors)} errors", flush=True)
    if errors:
        (out / "features_errors.txt").write_text("\n".join(errors) + "\n")
        print(f"  {len(errors)} game files failed → {out / 'features_errors.txt'}", file=sys.stderr)
    if not frames:
        return 2
    feats = pl.concat(frames, how="diagonal_relaxed")
    feats = feats.join(dsnaps.select("game_key", "gsis_play_id", "nfl_id", "pff_alignment", "pff_align_family", "pff_game_position",
                                     "pff_in_box", "pff_ROLE").unique(["game_key", "gsis_play_id", "nfl_id"]),
                       on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    feats = feats.join(cov.select("game_key", "gsis_play_id", "nfl_id", "cov_alignment", "assignment", "responsibility").unique(["game_key", "gsis_play_id", "nfl_id"]),
                       on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    ctx_cols = [c for c in ("game_key", "gsis_play_id", "is_pass", "is_play_action", "pff_PASSCOVERAGE", "pff_BOXPLAYERS", "pff_DOWN", "pff_DISTANCE") if c in plays.columns]
    feats = feats.join(plays.select(ctx_cols).unique(["game_key", "gsis_play_id"]), on=["game_key", "gsis_play_id"], how="left")
    feats = add_rule_roles(feats)
    feats.write_parquet(out / "features.parquet")
    print(f"wrote {out / 'features.parquet'}: {feats.height:,} defender-snaps, PFF join {feats['pff_alignment'].is_not_null().mean():.1%}, "
          f"charted responsibility {feats['responsibility'].is_not_null().mean():.1%}")
    return 0


def cmd_summarize(a) -> int:
    """Population + join-rate summary of a run, as markdown. Aggregates only, never rows."""
    out = Path(a.out)
    lines = [f"# run summary · {out}", ""]
    if (out / "features.parquet").exists():
        f = pl.read_parquet(out / "features.parquet")
        lines += ["## features", "", "| season | games | plays | defender-snaps | defenders | PFF alignment joined | charted coverage | pass share | ball proxy = center |",
                  "|---|---|---|---|---|---|---|---|---|"]
        g = f.group_by("season").agg(pl.col("game_key").n_unique().alias("games"),
                                     pl.struct("game_key", "gsis_play_id").n_unique().alias("plays"), pl.len().alias("snaps"),
                                     pl.col("nfl_id").n_unique().alias("defenders"),
                                     pl.col("pff_alignment").is_not_null().mean().alias("pff") if "pff_alignment" in f.columns else pl.lit(None).alias("pff"),
                                     pl.col("responsibility").is_not_null().mean().alias("cov") if "responsibility" in f.columns else pl.lit(None).alias("cov"),
                                     pl.col("has_throw").mean().alias("pass"),
                                     (pl.col("ball_proxy") == "center").mean().alias("ctr")).sort("season")
        for r in g.iter_rows(named=True):
            pct = lambda v: "—" if v is None else f"{v:.1%}"
            lines.append(f"| {r['season']} | {r['games']} | {r['plays']:,} | {r['snaps']:,} | {r['defenders']:,} | {pct(r['pff'])} | {pct(r['cov'])} | {pct(r['pass'])} | {pct(r['ctr'])} |")
        if "rule_align_role" in f.columns:
            lines += ["", "### rule alignment role × PFF family (row %)", ""]
            if "pff_align_family" in f.columns:
                ct = (f.filter(pl.col("pff_align_family").is_not_null()).group_by("rule_align_role", "pff_align_family").len()
                       .with_columns((pl.col("len") / pl.col("len").sum().over("rule_align_role")).alias("share")).sort("rule_align_role", "share", descending=[False, True]))
                for role, grp in ct.group_by("rule_align_role", maintain_order=True):
                    lines.append(f"- **{role[0]}** → " + ", ".join(f"{r['pff_align_family']} {r['share']:.0%}" for r in grp.head(4).iter_rows(named=True)))
    if (out / "model.json").exists():
        lines += ["", "## fit", "", "```", (out / "model.json").read_text().strip(), "```"]
    if (out / "gates.md").exists():
        lines += ["", "## gates", "", (out / "gates.md").read_text().strip()]
    if (out / "role_mix.parquet").exists():
        m = pl.read_parquet(out / "role_mix.parquet")
        lines += ["", "## role mix", "", f"{m.height} player-seasons above the snap floor; by peer group: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(m.group_by("peer_group").len().iter_rows()))]
        if "share_DEEP_MIDDLE" in m.columns:
            top = m.filter(pl.col("peer_group") == "S").sort("snaps", descending=True).head(12)
            lines += ["", "| safety | team | snaps | deep middle | deep half | box | slot | entropy |", "|---|---|---|---|---|---|---|---|"]
            for r in top.iter_rows(named=True):
                lines.append(f"| {r.get('player_name')} | {r.get('team')} | {r['snaps']} | {r.get('share_DEEP_MIDDLE', 0):.0%} | {r.get('share_DEEP_HALF', 0):.0%} | "
                             f"{r.get('share_BOX_SAFETY', 0):.0%} | {r.get('share_SLOT_CB', 0):.0%} | {r.get('align_entropy', 0):.2f} |")
    if (out / "features_errors.txt").exists():
        errs = (out / "features_errors.txt").read_text().strip().splitlines()
        lines += ["", f"## {len(errs)} game files failed", "", "```", *errs[:20], "```"]
    md = "\n".join(lines) + "\n"
    Path(a.run_dir).mkdir(parents=True, exist_ok=True)
    (Path(a.run_dir) / "summary.md").write_text(md)
    print(md)
    return 0


def _holdout(feats: pl.DataFrame, weeks: list[int] | None) -> list[int]:
    if not weeks or "week" not in feats.columns:
        return []
    return feats.filter(pl.col("week").is_in(weeks)).get_column("game_key").unique().to_list()


def cmd_fit(a) -> int:
    from .roles.model import RoleAttributionModel

    out = Path(a.out)
    feats = pl.read_parquet(out / "features.parquet")
    hold = _holdout(feats, a.holdout_weeks)
    m = RoleAttributionModel(seed=a.seed).fit(feats, holdout_games=hold)
    m.fit_report["holdout_games"] = hold
    m.save(out / "model.pkl")
    print(json.dumps(m.fit_report, indent=1))
    return 0


def cmd_score(a) -> int:
    from .roles.model import RoleAttributionModel

    out = Path(a.out)
    feats = pl.read_parquet(out / "features.parquet")
    m = RoleAttributionModel.load(out / "model.pkl")
    s = m.predict(feats)
    s.write_parquet(out / "scored.parquet")
    print(f"scored {s.height:,} snaps → {out / 'scored.parquet'}")
    return 0


def cmd_mix(a) -> int:
    from .eval.gates import format_gates, run_gates
    from .roles.aggregate import add_peer_percentiles, player_role_mix, team_role_mix
    from .roles.model import RoleAttributionModel
    from .viewer.export import export_viewer_json

    out = Path(a.out)
    s = pl.read_parquet(out / "scored.parquet")
    hold = []
    if (out / "model.json").exists():
        hold = json.loads((out / "model.json").read_text()).get("holdout_games", [])
    mix = add_peer_percentiles(player_role_mix(s, min_snaps=a.min_snaps), min_snaps=a.min_snaps_pct)
    mix.write_parquet(out / "role_mix.parquet")
    tm = team_role_mix(s)
    tm.write_parquet(out / "team_role_mix.parquet")
    gates = run_gates(s, holdout_games=hold, min_snaps=a.min_snaps)
    (out / "gates.md").write_text(format_gates(gates) + "\n")
    print(format_gates(gates))
    export_viewer_json(mix, Path(a.viewer_json), gates=gates, source=str(out), team_mix=tm)
    print(f"{mix.height} player-seasons → {out / 'role_mix.parquet'}; viewer → {a.viewer_json}")
    return 0


def cmd_demo(a) -> int:
    """Synthetic end to end. Proves the plumbing, never the football."""
    import numpy as np

    from .ngs.features import defender_features_for_game
    from .pff.vocab import align_family
    from .roles.rules import add_rule_roles
    from .synth import make_season

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fr, truth = make_season(n_games=a.games, plays_per_game=a.plays, seed=a.seed)
    frames = []
    for gk, g in fr.group_by("game_key"):
        g = g.filter(pl.col("is_on_field")).with_columns(pl.col("gsis_play_id").cast(pl.Int64))
        g = g.with_columns(pl.col("time").rank("dense").over("gsis_play_id").cast(pl.Int32).alias("frame_id")).sort(["gsis_play_id", "frame_id", "nfl_id"])
        f = defender_features_for_game(g)
        frames.append(f.with_columns(pl.lit(2025).alias("season"), pl.lit(int(gk[0]) % 100 + 1).alias("week")))
    feats = pl.concat(frames, how="diagonal_relaxed")
    rng = np.random.default_rng(a.seed)
    tr = truth.with_columns(pl.col("pff_alignment").map_elements(align_family, return_dtype=pl.Utf8).alias("pff_align_family"))
    tr = tr.with_columns(pl.Series("responsibility", [r if (rng.random() < 0.6 and p) else None for r, p in zip(tr["true_responsibility"], tr["is_pass"])]))
    feats = feats.join(tr.select("game_key", "gsis_play_id", "nfl_id", "pff_alignment", "pff_align_family", "responsibility", "true_align_role", "true_responsibility", "is_pass"),
                       on=["game_key", "gsis_play_id", "nfl_id"], how="left")
    add_rule_roles(feats).write_parquet(out / "features.parquet")
    print(f"synthetic: {fr.height:,} frames → {feats.height:,} defender-snaps")
    ns = argparse.Namespace(out=str(out), holdout_weeks=[a.games - 1, a.games], seed=a.seed, min_snaps=60, min_snaps_pct=60,
                            viewer_json=a.viewer_json)
    cmd_fit(ns)
    cmd_score(ns)
    return cmd_mix(ns)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(prog="poshub", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="out")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--offline", action="store_true"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("probe"); s.add_argument("--json"); s.set_defaults(fn=cmd_probe)
    s = sub.add_parser("sql"); s.add_argument("statement"); s.add_argument("--out-file"); s.set_defaults(fn=cmd_sql)
    s = sub.add_parser("discover"); s.add_argument("--out-file", default="data_contracts/uc_inventory.json"); s.add_argument("--catalog"); s.set_defaults(fn=cmd_discover)
    s = sub.add_parser("features"); s.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025]); s.add_argument("--weeks", type=int, nargs="*")
    s.add_argument("--max-games", type=int); s.add_argument("--workers", type=int); s.add_argument("--source", default="auto", choices=["auto", "databricks", "local"]); s.set_defaults(fn=cmd_features)
    s = sub.add_parser("summarize"); s.add_argument("--run-dir", required=True); s.set_defaults(fn=cmd_summarize)
    s = sub.add_parser("fit"); s.add_argument("--holdout-weeks", type=int, nargs="*", default=[17, 18]); s.add_argument("--seed", type=int, default=0); s.set_defaults(fn=cmd_fit)
    s = sub.add_parser("score"); s.set_defaults(fn=cmd_score)
    s = sub.add_parser("mix"); s.add_argument("--min-snaps", type=int, default=100); s.add_argument("--min-snaps-pct", type=int, default=200)
    s.add_argument("--viewer-json", default="viewer/data/role_mix.json"); s.set_defaults(fn=cmd_mix)
    s = sub.add_parser("demo"); s.add_argument("--games", type=int, default=8); s.add_argument("--plays", type=int, default=45); s.add_argument("--seed", type=int, default=0)
    s.add_argument("--viewer-json", default="viewer/data/role_mix.json"); s.set_defaults(fn=cmd_demo)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
