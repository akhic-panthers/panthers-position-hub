"""Configuration — every external thing this package touches is named here, read lazily from env.

Nothing here opens a connection. A missing secret fails at CALL time with a clear message, never at
import time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v.strip() if v is not None and v.strip() else default


def load_dotenv(path: str | os.PathLike | None = None) -> None:
    """Minimal .env loader (KEY=VALUE, # comments). Never overrides an already-set variable."""
    p = Path(path) if path else Path.cwd() / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


# ── Unity Catalog table registry ────────────────────────────────────────────────────────────────
# Measured in the Panthers workspace (2026-08, handoff/memory/panthers-phaseQ-wider-feed.md):
# every PFF bronze table is `pff.bronze.<table>`. (A Databricks-assistant paste once read as
# "pffplayspff.bronze.pffplays" — that was the name column and the full-name column run together,
# NOT per-table catalogs.) Same layouts exist for other leagues under pff.cff / pff.cfl / pff.ufl,
# and pff.silver / pff.gold hold analytics tables (scheme_data, pass_rush_entropy).
# Any name can be overridden with POSHUB_TABLE_<NAME>; `poshub discover` verifies them live.
PFF_CATALOG = "pff"
PFF_SCHEMA = "bronze"
PFF_TABLE_NAMES = ["pffplays", "pffoffense", "pffdefense", "pffgames", "pffrosters", "pffplayerblockings",
                   "pffspecial", "coverage_defense", "coverage_offense", "coverage",
                   "pffquarterbackchartings", "nfl_player", "season_grade", "game_grade", "pff_teams"]
PFF_TABLES: dict[str, str] = {t: f"{PFF_CATALOG}.{PFF_SCHEMA}.{t}" for t in PFF_TABLE_NAMES}


def table_name(logical: str) -> str:
    """Three-part UC name for a logical table; env override wins."""
    override = _env(f"POSHUB_TABLE_{logical.upper()}")
    if override:
        return override
    if logical in PFF_TABLES:
        return PFF_TABLES[logical]
    raise KeyError(f"unknown logical table {logical!r}; set POSHUB_TABLE_{logical.upper()}")


@dataclass
class DatabricksConfig:
    host: str = field(default_factory=lambda: _env("DATABRICKS_HOST").rstrip("/"))
    token: str = field(default_factory=lambda: _env("DATABRICKS_TOKEN"))
    http_path: str = field(default_factory=lambda: _env("DATABRICKS_HTTP_PATH"))
    profile: str = field(default_factory=lambda: _env("DATABRICKS_CONFIG_PROFILE"))
    volume: str = field(default_factory=lambda: _env("POSHUB_UC_VOLUME", "/Volumes/pff/bronze/exports"))
    timeout_s: int = 60

    @property
    def configured(self) -> bool:
        return bool(self.host)

    def missing(self) -> list[str]:
        m = []
        if not self.host:
            m.append("DATABRICKS_HOST")
        if not self.token and not self.profile:
            m.append("DATABRICKS_TOKEN (or DATABRICKS_CONFIG_PROFILE)")
        return m


@dataclass
class LocalDataConfig:
    """Mirror of panthers_projects layout so the same code runs on the Mac against the export."""
    root: Path = field(default_factory=lambda: Path(_env("PANTHERS_DATA_DIR", str(Path.cwd()))))

    def pff_export_dir(self, table: str) -> Path:
        return self.root / "data" / "pff_export" / table

    def ngs_season_dir(self, season: int) -> Path:
        return self.root / f"{season}_NGS_Player_Play"


@dataclass
class ThunderConfig:
    base_url: str = field(default_factory=lambda: _env("THUNDER_BASE_URL", "https://tclightningservices.xosdigital.com/Api"))
    sso_url: str = field(default_factory=lambda: _env("THUNDER_SSO_URL", "https://tcssoservices.xosdigital.com/sso/RESTSSOServices.svc"))
    username: str = field(default_factory=lambda: _env("THUNDER_USERNAME"))
    password: str = field(default_factory=lambda: _env("THUNDER_PASSWORD"))
    vendor_guid: str = field(default_factory=lambda: _env("THUNDER_VENDOR_GUID"))

    @property
    def has_credential(self) -> bool:
        return bool(self.username and self.password)


@dataclass
class OpenFieldConfig:
    base_url: str = field(default_factory=lambda: _env("OPENFIELD_BASE_URL", "https://connect-us.catapultsports.com/api/v6"))
    token: str = field(default_factory=lambda: _env("OPENFIELD_TOKEN"))


@dataclass
class PFFUltimateConfig:
    base_url: str = field(default_factory=lambda: _env("PFF_ULTIMATE_BASE_URL", "https://ultimate.pff.com"))


# ── modelling constants (registered; change = new registration) ────────────────────────────────
FRAME_HZ = 10
POST_SNAP_SECONDS = 2.0          # Eager & Seth 2023: bite distance / ground covered measured at 2 s
FRAMES_AT_2S = int(POST_SNAP_SECONDS * FRAME_HZ)
MIN_SNAPS_FOR_MIX = 100          # player-season floor before a role mix is shown
MIN_SNAPS_FOR_PERCENTILE = 200   # peer-percentile floor (paper used 200 run-defense snaps)
