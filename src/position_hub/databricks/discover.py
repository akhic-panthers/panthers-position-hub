"""`poshub discover` — write what Unity Catalog actually holds to data_contracts/uc_inventory.json.

Why a file: the PFF feed's one-catalog-per-table layout was learned by asking, and it changed how
every loader was written. The inventory is checked in so the next person reads it instead of
rediscovering it. Column lists here are the truth for the loaders; `docs/01_data_contract.md`
carries the interpretation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import PFF_TABLES, table_name
from .client import DatabricksAuthError, DatabricksUnreachable, UnityCatalogClient

NGS_HINTS = ("ngs", "tracking", "player_play", "frame", "nextgen")


def discover(out: Path = Path("data_contracts/uc_inventory.json"), catalogs_filter: str | None = None) -> dict:
    uc = UnityCatalogClient()
    ok, detail = uc.reachable()
    inv: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "host": uc.cfg.host,
                 "reachable": ok, "detail": detail, "catalogs": [], "pff_tables": {}, "ngs_candidates": []}
    if not ok:
        out.write_text(json.dumps(inv, indent=2))
        return inv
    try:
        cats = uc.catalogs()
    except DatabricksAuthError as e:
        inv["detail"] = f"auth: {e}"
        out.write_text(json.dumps(inv, indent=2))
        return inv
    for c in cats:
        name = c["name"]
        if catalogs_filter and catalogs_filter not in name:
            continue
        entry = {"name": name, "schemas": []}
        try:
            for s in uc.schemas(name):
                sn = s["name"]
                if sn == "information_schema":
                    continue
                tabs = uc.tables(name, sn)
                entry["schemas"].append({"name": sn, "tables": [
                    {"name": t["name"], "full_name": t["full_name"], "type": t.get("table_type"),
                     "columns": [{"name": col["name"], "type": col.get("type_text")} for col in t.get("columns", [])]}
                    for t in tabs]})
                for t in tabs:
                    fn = t["full_name"].lower()
                    if any(h in fn for h in NGS_HINTS):
                        inv["ngs_candidates"].append(t["full_name"])
        except DatabricksUnreachable:
            raise
        except Exception as e:  # a catalog we cannot read is a fact, not a crash
            entry["error"] = str(e)[:200]
        inv["catalogs"].append(entry)
    for logical in PFF_TABLES:
        fn = table_name(logical)
        try:
            inv["pff_tables"][logical] = {"full_name": fn, "columns": uc.columns(fn)}
        except Exception as e:
            inv["pff_tables"][logical] = {"full_name": fn, "error": str(e)[:200]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, indent=2))
    return inv
