"""Databricks Unity Catalog access — three doors, one interface.

1. **REST / Unity Catalog API** (`/api/2.1/unity-catalog/*`): list catalogs, schemas, tables,
   columns. Pure `requests`, no extra dependency. Used by `poshub discover` to write the inventory.
2. **SQL** — the Statement Execution API (`/api/2.0/sql/statements`) against a SQL warehouse, again
   pure `requests`; results come back as Arrow via `EXTERNAL_LINKS` or inline JSON for small
   results. `databricks-sql-connector` is used instead when it is installed (faster, streams Arrow).
3. **Local parquet** — `PANTHERS_DATA_DIR/data/pff_export/<table>/*.parquet`, the same layout the
   Mac export uses. `get_source()` picks this automatically when Databricks is not configured or
   the host is unreachable, so every pipeline step runs identically in both places.

Auth: `DATABRICKS_TOKEN` (PAT) → `Authorization: Bearer`. If empty, the `databricks-sdk` credential
chain (OAuth U2M via `databricks auth login`, Azure CLI, profiles in ~/.databrickscfg) is tried.
⛔ The network policy of a Claude cloud container may deny the workspace host outright (measured
2026-09-25: CONNECT tunnel 403). `reachable()` reports that as a distinct fact from "bad token".
"""
from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import polars as pl
import requests

from ..config import DatabricksConfig, LocalDataConfig, table_name


class DatabricksError(RuntimeError):
    pass


class DatabricksUnreachable(DatabricksError):
    """Network-level failure: proxy 403, DNS, timeout. Not a credential problem."""


class DatabricksAuthError(DatabricksError):
    pass


# ── auth ─────────────────────────────────────────────────────────────────────────────────────────
def _bearer(cfg: DatabricksConfig) -> dict[str, str]:
    if cfg.token:
        return {"Authorization": f"Bearer {cfg.token}"}
    # Fall back to the SDK credential chain (OAuth U2M, Azure CLI, profile). Optional dependency.
    try:
        from databricks.sdk.core import Config  # type: ignore

        kw: dict[str, Any] = {"host": cfg.host}
        if cfg.profile:
            kw["profile"] = cfg.profile
        c = Config(**kw)
        return dict(c.authenticate())
    except ImportError as e:  # pragma: no cover - depends on environment
        raise DatabricksAuthError(
            "no DATABRICKS_TOKEN and databricks-sdk is not installed; "
            "set a PAT or `pip install databricks-sdk` and `databricks auth login --host <host>`"
        ) from e
    except Exception as e:  # pragma: no cover
        raise DatabricksAuthError(f"databricks-sdk could not authenticate: {e}") from e


# ── REST: Unity Catalog metadata ─────────────────────────────────────────────────────────────────
class UnityCatalogClient:
    def __init__(self, cfg: DatabricksConfig | None = None, session: requests.Session | None = None):
        self.cfg = cfg or DatabricksConfig()
        self.s = session or requests.Session()

    # -- plumbing
    def _url(self, path: str) -> str:
        return f"{self.cfg.host}/api/2.1/unity-catalog/{path.lstrip('/')}"

    def _get(self, path: str, **params: Any) -> dict:
        if not self.cfg.host:
            raise DatabricksError("DATABRICKS_HOST is not set")
        try:
            r = self.s.get(self._url(path), headers=_bearer(self.cfg), params=params, timeout=self.cfg.timeout_s)
        except requests.RequestException as e:
            raise DatabricksUnreachable(f"cannot reach {self.cfg.host}: {e}") from e
        if r.status_code in (401, 403):
            raise DatabricksAuthError(f"HTTP {r.status_code} from {path}: {r.text[:200]}")
        if r.status_code >= 400:
            raise DatabricksError(f"HTTP {r.status_code} from {path}: {r.text[:300]}")
        return r.json()

    def _paged(self, path: str, key: str, **params: Any) -> Iterable[dict]:
        token = None
        while True:
            if token:
                params["page_token"] = token
            j = self._get(path, **params)
            yield from j.get(key, [])
            token = j.get("next_page_token")
            if not token:
                break

    # -- reachability, separated from auth on purpose
    def reachable(self) -> tuple[bool, str]:
        """(True, detail) when the host answers at all — even 401 counts as reachable."""
        if not self.cfg.host:
            return False, "DATABRICKS_HOST not set"
        try:
            r = self.s.get(self._url("catalogs"), timeout=15)
            return True, f"HTTP {r.status_code}"
        except requests.RequestException as e:
            return False, f"{type(e).__name__}: {e}"

    # -- metadata
    def catalogs(self) -> list[dict]:
        return list(self._paged("catalogs", "catalogs"))

    def schemas(self, catalog: str) -> list[dict]:
        return list(self._paged("schemas", "schemas", catalog_name=catalog))

    def tables(self, catalog: str, schema: str) -> list[dict]:
        return list(self._paged("tables", "tables", catalog_name=catalog, schema_name=schema))

    def table(self, full_name: str) -> dict:
        return self._get(f"tables/{full_name}")

    def columns(self, full_name: str) -> list[dict]:
        return [
            {"name": c["name"], "type": c.get("type_text") or c.get("type_name"), "position": c.get("position")}
            for c in self.table(full_name).get("columns", [])
        ]

    def volumes(self, catalog: str, schema: str) -> list[dict]:
        return list(self._paged("volumes", "volumes", catalog_name=catalog, schema_name=schema))


# ── SQL: Statement Execution API (pure requests) or databricks-sql-connector ────────────────────
class DatabricksSQL:
    def __init__(self, cfg: DatabricksConfig | None = None, session: requests.Session | None = None):
        self.cfg = cfg or DatabricksConfig()
        self.s = session or requests.Session()
        if not self.cfg.http_path:
            raise DatabricksError("DATABRICKS_HTTP_PATH (SQL warehouse) is required for SQL reads")
        self.warehouse_id = self.cfg.http_path.rstrip("/").split("/")[-1]

    def query(self, sql: str, *, wait_s: int = 600) -> pl.DataFrame:
        try:
            return self._query_connector(sql)
        except ImportError:
            return self._query_rest(sql, wait_s=wait_s)

    # connector path
    def _query_connector(self, sql: str) -> pl.DataFrame:
        from databricks import sql as dbsql  # type: ignore  # optional dependency

        auth = _bearer(self.cfg)
        token = auth.get("Authorization", "").removeprefix("Bearer ").strip()
        with dbsql.connect(server_hostname=self.cfg.host.removeprefix("https://"), http_path=self.cfg.http_path,
                           access_token=token) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return pl.from_arrow(cur.fetchall_arrow())

    # REST path
    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self.s.post(f"{self.cfg.host}{path}", headers=_bearer(self.cfg), json=body, timeout=self.cfg.timeout_s)
        except requests.RequestException as e:
            raise DatabricksUnreachable(str(e)) from e
        if r.status_code in (401, 403):
            raise DatabricksAuthError(r.text[:200])
        if r.status_code >= 400:
            raise DatabricksError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _get(self, path: str) -> dict:
        r = self.s.get(f"{self.cfg.host}{path}", headers=_bearer(self.cfg), timeout=self.cfg.timeout_s)
        if r.status_code >= 400:
            raise DatabricksError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _query_rest(self, sql: str, *, wait_s: int) -> pl.DataFrame:
        body = {"warehouse_id": self.warehouse_id, "statement": sql, "wait_timeout": "50s",
                "format": "ARROW_STREAM", "disposition": "EXTERNAL_LINKS"}
        j = self._post("/api/2.0/sql/statements", body)
        sid = j["statement_id"]
        t0 = time.time()
        while j["status"]["state"] in ("PENDING", "RUNNING"):
            if time.time() - t0 > wait_s:
                raise DatabricksError(f"statement {sid} still {j['status']['state']} after {wait_s}s")
            time.sleep(2)
            j = self._get(f"/api/2.0/sql/statements/{sid}")
        if j["status"]["state"] != "SUCCEEDED":
            raise DatabricksError(f"statement failed: {json.dumps(j['status'])[:400]}")
        return self._collect_external_links(j)

    def _collect_external_links(self, j: dict) -> pl.DataFrame:
        import pyarrow as pa
        import pyarrow.ipc as ipc

        manifest = j["manifest"]
        chunks = list(j.get("result", {}).get("external_links", []))
        # Additional chunks are fetched by index.
        for ch in manifest.get("chunks", [])[1:]:
            r = self._get(f"/api/2.0/sql/statements/{j['statement_id']}/result/chunks/{ch['chunk_index']}")
            chunks.extend(r.get("external_links", []))
        tables = []
        for link in chunks:
            # presigned URL: NO auth header (sending the bearer token to cloud storage is rejected)
            raw = requests.get(link["external_link"], timeout=self.cfg.timeout_s).content
            tables.append(ipc.open_stream(io.BytesIO(raw)).read_all())
        if not tables:
            cols = [c["name"] for c in manifest["schema"]["columns"]]
            return pl.DataFrame({c: [] for c in cols})
        return pl.from_arrow(pa.concat_tables(tables))


# ── one interface over "Databricks table" and "local parquet directory" ────────────────────────
@dataclass
class DataSource:
    """`read(table, columns, where)` resolves a *logical* table name either in Unity Catalog or in
    the local export directory. Pipelines never know which one they got."""

    mode: str                       # "databricks" | "local"
    dbx: DatabricksSQL | None = None
    local: LocalDataConfig | None = None

    def read(self, logical: str, columns: list[str] | None = None, where: str | None = None,
             limit: int | None = None) -> pl.DataFrame:
        if self.mode == "databricks":
            assert self.dbx is not None
            cols = ", ".join(f"`{c}`" for c in columns) if columns else "*"
            sql = f"SELECT {cols} FROM {table_name(logical)}"
            if where:
                sql += f" WHERE {where}"
            if limit:
                sql += f" LIMIT {int(limit)}"
            return self.dbx.query(sql)
        assert self.local is not None
        d = self.local.pff_export_dir(logical)
        files = sorted(d.glob("*.parquet")) + sorted(d.glob("**/*.parquet"))
        files = sorted(set(files))
        if not files:
            raise FileNotFoundError(f"no parquet under {d} for logical table {logical!r}")
        lf = pl.scan_parquet([str(f) for f in files])
        if columns:
            lf = lf.select(columns)
        if where:
            # local `where` is a polars expression string is not supported; use duckdb when present
            try:
                import duckdb  # type: ignore

                cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
                q = f"SELECT {cols} FROM read_parquet({[str(f) for f in files]!r}) WHERE {where}"
                if limit:
                    q += f" LIMIT {int(limit)}"
                return pl.from_arrow(duckdb.sql(q).arrow())
            except ImportError as e:
                raise DatabricksError("local `where` filters need duckdb (`pip install duckdb`)") from e
        if limit:
            lf = lf.limit(limit)
        return lf.collect()

    def describe(self) -> str:
        if self.mode == "databricks":
            return f"databricks:{self.dbx.cfg.host}"  # type: ignore[union-attr]
        return f"local:{self.local.root}"  # type: ignore[union-attr]


def get_source(prefer: str = "auto") -> DataSource:
    """Pick Databricks when it is configured *and* answers; otherwise the local export."""
    cfg = DatabricksConfig()
    if prefer in ("auto", "databricks") and cfg.configured and cfg.http_path:
        ok, detail = UnityCatalogClient(cfg).reachable()
        if ok:
            return DataSource(mode="databricks", dbx=DatabricksSQL(cfg))
        if prefer == "databricks":
            raise DatabricksUnreachable(f"{cfg.host} unreachable: {detail}")
    return DataSource(mode="local", local=LocalDataConfig())
