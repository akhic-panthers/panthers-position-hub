"""`poshub probe` — the connection ladder. Each rung is a separate fact with its own remedy, because
"Databricks doesn't work" has at least five different causes and they look alike from a traceback.

    1 host      TCP/TLS to the workspace host          → network policy / DNS / proxy
    2 auth      /scim/v2/Me answers with an identity    → token, service principal, OAuth
    3 catalog   pff.bronze is listable                  → Unity Catalog grants (USE CATALOG / USE SCHEMA)
    4 warehouse a SQL warehouse is visible and RUNNING  → DATABRICKS_HTTP_PATH, CAN USE on the warehouse
    5 sql       SELECT 1 through the Statement API      → warehouse actually executes
    6 tables    row count + column check on the contract tables → SELECT grants, names right
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..config import DatabricksConfig, PFF_TABLES, table_name
from .client import DatabricksAuthError, DatabricksError, DatabricksSQL, DatabricksUnreachable, UnityCatalogClient

CONTRACT_COLUMNS = {
    "pffplays": ["pff_GAMEID", "pff_PLAYID", "pff_GSISGAMEKEY", "pff_GSISPLAYID", "pff_GAMESEASON", "pff_RUNPASS", "pff_PASSCOVERAGE"],
    "pffdefense": ["pff_GAMEID", "pff_PLAYID", "pff_GSISPLAYERID", "pff_POSITION", "pff_GAMEPOSITION", "pff_ROLE", "pff_BOXPLAYER"],
    "coverage_defense": ["gsis_game_id", "gsis_play_id", "gsis_player_id", "season", "position", "assignment", "modifier1"],
}


@dataclass
class Rung:
    name: str
    ok: bool | None = None
    detail: str = ""
    remedy: str = ""


@dataclass
class ProbeReport:
    host: str
    rungs: list[Rung] = field(default_factory=list)

    def add(self, r: Rung) -> Rung:
        self.rungs.append(r)
        return r

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.rungs)

    def to_dict(self) -> dict:
        return {"host": self.host, "ok": self.ok, "rungs": [asdict(r) for r in self.rungs]}

    def format(self) -> str:
        out = [f"databricks probe · {self.host or '(DATABRICKS_HOST unset)'}"]
        for r in self.rungs:
            mark = "—" if r.ok is None else ("OK " if r.ok else "FAIL")
            out.append(f"  [{mark}] {r.name:9s} {r.detail}")
            if r.ok is False and r.remedy:
                out.append(f"           → {r.remedy}")
        return "\n".join(out)


def probe(cfg: DatabricksConfig | None = None, session=None, tables: list[str] | None = None) -> ProbeReport:
    cfg = cfg or DatabricksConfig()
    rep = ProbeReport(host=cfg.host)
    uc = UnityCatalogClient(cfg, session) if session is not None else UnityCatalogClient(cfg)

    # 1 host
    if not cfg.host:
        rep.add(Rung("host", False, "DATABRICKS_HOST not set", "set DATABRICKS_HOST=https://adb-7405617646104787.7.azuredatabricks.net"))
        return rep
    ok, detail = uc.reachable()
    r1 = rep.add(Rung("host", ok, detail, "the environment's network policy denies this host: add it to the allowed domains "
                                          "(Claude cloud env → Edit → Network access), or run from a laptop / the workspace notebook"))
    if not ok:
        return rep

    # 2 auth
    missing = cfg.missing()
    if missing:
        rep.add(Rung("auth", False, "no credential", f"{' or '.join(missing)}"))
        return rep
    if not (cfg.token or cfg.profile or (cfg.azure_tenant_id and cfg.azure_client_id)) and cfg.has_azure_cli:
        from .client import _azure_cli_token

        if not _azure_cli_token():
            rep.add(Rung("auth", False, "Azure CLI present but not logged in", "run `az login` (then it is a token for resource 2ff814a6-… on every call)"))
            return rep
    try:
        me = uc.whoami()
        rep.add(Rung("auth", True, f"{me.get('user')} ({me.get('display') or 'no display name'})"))
    except DatabricksAuthError as e:
        rep.add(Rung("auth", False, str(e)[:160], "token rejected: `az login` again (Azure CLI), or regenerate the PAT, "
                                                 "or add the service principal to the workspace"))
        return rep
    except DatabricksUnreachable as e:
        rep.add(Rung("auth", False, str(e)[:160], "host answered the first time and not the second: proxy instability, retry"))
        return rep

    # 3 catalog
    try:
        schemas = [s["name"] for s in uc.schemas("pff")]
        has_bronze = "bronze" in schemas
        rep.add(Rung("catalog", has_bronze, f"pff schemas: {', '.join(schemas) or 'none visible'}",
                     "ask the workspace admin for USE CATALOG on pff and USE SCHEMA on pff.bronze"))
    except DatabricksError as e:
        rep.add(Rung("catalog", False, str(e)[:160], "catalog `pff` not visible to this identity: USE CATALOG grant, or the name differs — run `poshub discover`"))

    # 4 warehouse
    try:
        ws = uc.warehouses()
        running = [w for w in ws if w["state"] == "RUNNING"]
        chosen = None
        if cfg.http_path:
            chosen = next((w for w in ws if w["http_path"] == cfg.http_path or w["id"] == cfg.http_path.rstrip("/").split("/")[-1]), None)
            det = f"DATABRICKS_HTTP_PATH → {chosen['name']} [{chosen['state']}]" if chosen else f"DATABRICKS_HTTP_PATH {cfg.http_path} not among {len(ws)} visible warehouses"
            rep.add(Rung("warehouse", chosen is not None, det, "set DATABRICKS_HTTP_PATH to one of: " + "; ".join(f"{w['name']} {w['http_path']}" for w in ws)))
        else:
            chosen = (running or ws or [None])[0]
            det = f"auto-picked {chosen['name']} [{chosen['state']}] {chosen['http_path']}" if chosen else "no SQL warehouse visible"
            rep.add(Rung("warehouse", chosen is not None, det, "create or get CAN USE on a SQL warehouse, then set DATABRICKS_HTTP_PATH"))
        if chosen and chosen["state"] not in ("RUNNING", "STARTING"):
            rep.rungs[-1].detail += " (stopped: the first statement will auto-start it, expect ~1–3 min)"
    except DatabricksError as e:
        rep.add(Rung("warehouse", False, str(e)[:160], "no permission to list warehouses; set DATABRICKS_HTTP_PATH explicitly"))
        chosen = None
    if not chosen and not cfg.http_path:
        return rep

    # 5 sql
    try:
        sql = DatabricksSQL(cfg, session) if session is not None else DatabricksSQL(cfg)
        one = sql.query("SELECT 1 AS one LIMIT 1")
        rep.add(Rung("sql", int(one["one"][0]) == 1, f"SELECT 1 via Statement Execution API on warehouse {sql.warehouse_id}"))
    except DatabricksError as e:
        rep.add(Rung("sql", False, str(e)[:200], "warehouse did not execute: check its state, CAN USE, and the Statement API is enabled"))
        return rep

    # 6 tables
    for t in tables or list(CONTRACT_COLUMNS):
        fn = table_name(t)
        try:
            n = sql.query(f"SELECT COUNT(*) AS n FROM {fn} LIMIT 1")["n"][0]
            head = sql.query(f"SELECT * FROM {fn} LIMIT 1")
            missing_cols = [c for c in CONTRACT_COLUMNS.get(t, []) if c not in head.columns]
            rep.add(Rung(f"table:{t}", not missing_cols, f"{fn}: {int(n):,} rows, {len(head.columns)} cols" + (f", missing {missing_cols}" if missing_cols else ""),
                         "column names differ from data_contracts/uc_tables.json: run `poshub discover` and update pff/loaders.py"))
        except DatabricksError as e:
            rep.add(Rung(f"table:{t}", False, f"{fn}: {str(e)[:140]}", f"SELECT grant on {fn}, or override POSHUB_TABLE_{t.upper()}"))
    return rep


__all__ = ["probe", "ProbeReport", "Rung", "CONTRACT_COLUMNS", "PFF_TABLES"]
