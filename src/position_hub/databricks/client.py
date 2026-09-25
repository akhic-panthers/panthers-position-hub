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
import re
import shutil
import subprocess
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
AZURE_DATABRICKS_RESOURCE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"   # fixed AAD app id of Azure Databricks
_AAD_CACHE: dict[str, tuple[float, str]] = {}


def _azure_sp_token(tenant: str, client_id: str, client_secret: str, session: requests.Session | None = None) -> str:
    """Azure AD client-credentials token for the Azure Databricks resource. Pure requests, so a
    headless container with ARM_TENANT_ID / ARM_CLIENT_ID / ARM_CLIENT_SECRET needs no CLI or SDK.
    The service principal must be added to the workspace (Admin settings → Identity → Service principals)."""
    key = f"{tenant}:{client_id}"
    exp, tok = _AAD_CACHE.get(key, (0.0, ""))
    if tok and time.time() < exp - 60:
        return tok
    r = (session or requests).post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                                    data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret,
                                          "scope": f"{AZURE_DATABRICKS_RESOURCE}/.default"}, timeout=30)
    if r.status_code >= 400:
        raise DatabricksAuthError(f"Azure AD token request failed: HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    _AAD_CACHE[key] = (time.time() + float(j.get("expires_in", 3600)), j["access_token"])
    return j["access_token"]


def _azure_cli_token() -> str | None:
    """`az login` once, then every call here is `az account get-access-token` for the Azure Databricks
    resource. No Databricks-specific setup at all — the PanthersScout way. Returns None when the CLI
    is absent or not logged in, so the chain can continue."""
    az = shutil.which("az")
    if not az:
        return None
    exp, tok = _AAD_CACHE.get("az-cli", (0.0, ""))
    if tok and time.time() < exp - 60:
        return tok
    try:
        out = subprocess.run([az, "account", "get-access-token", "--resource", AZURE_DATABRICKS_RESOURCE, "--output", "json"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    j = json.loads(out.stdout)
    tok = j.get("accessToken")
    if not tok:
        return None
    ttl = float(j.get("expires_in") or 3000)
    _AAD_CACHE["az-cli"] = (time.time() + ttl, tok)
    return tok


def _databricks_cli_token(host: str, profile: str = "") -> str | None:
    """`databricks auth login --host <host>` once (browser OAuth; the CLI caches the token in
    ~/.databricks/token-cache.json). Every call here is `databricks auth token`, which refreshes it.
    Returns None when the CLI is absent or has no login for this host."""
    dbx = shutil.which("databricks")
    if not dbx or not (host or profile):
        return None
    key = f"dbx-cli:{profile or host}"
    exp, tok = _AAD_CACHE.get(key, (0.0, ""))
    if tok and time.time() < exp - 60:
        return tok
    cmd = [dbx, "auth", "token", "--output", "json"] + (["--profile", profile] if profile else ["--host", host])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        j = json.loads(out.stdout)
    except ValueError:
        return None
    tok = j.get("access_token")
    if not tok:
        return None
    _AAD_CACHE[key] = (time.time() + 600.0, tok)   # the CLI refreshes; keep ours short
    return tok


def _bearer(cfg: DatabricksConfig, session: requests.Session | None = None) -> dict[str, str]:
    """Credential chain, first hit wins:
       1. DATABRICKS_TOKEN (PAT)
       2. Azure service principal: ARM_TENANT_ID / ARM_CLIENT_ID / ARM_CLIENT_SECRET
       3. Databricks CLI: `databricks auth login --host <host>` once, then `databricks auth token`
       4. Azure CLI: `az login` then a token for the Databricks resource
       5. databricks-sdk chain: OAuth U2M profile, env, Azure identities"""
    if cfg.token:
        return {"Authorization": f"Bearer {cfg.token}"}
    if cfg.azure_tenant_id and cfg.azure_client_id and cfg.azure_client_secret:
        return {"Authorization": f"Bearer {_azure_sp_token(cfg.azure_tenant_id, cfg.azure_client_id, cfg.azure_client_secret, session)}"}
    cli = _databricks_cli_token(cfg.host, cfg.profile) or _azure_cli_token()
    if cli:
        return {"Authorization": f"Bearer {cli}"}
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
            "no credential: `databricks auth login --host <host>` (Databricks CLI) or `az login` (Azure CLI), "
            "or set DATABRICKS_TOKEN (PAT), or ARM_TENANT_ID/ARM_CLIENT_ID/ARM_CLIENT_SECRET (service principal)"
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
            r = self.s.get(self._url(path), headers=_bearer(self.cfg, self.s), params=params, timeout=self.cfg.timeout_s)
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

    def whoami(self) -> dict:
        """The identity the token resolves to (SCIM Me). Auth check that needs no catalog grants."""
        try:
            r = self.s.get(f"{self.cfg.host}/api/2.0/preview/scim/v2/Me", headers=_bearer(self.cfg, self.s), timeout=self.cfg.timeout_s)
        except requests.RequestException as e:
            raise DatabricksUnreachable(str(e)) from e
        if r.status_code in (401, 403):
            raise DatabricksAuthError(f"HTTP {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        j = r.json()
        return {"user": j.get("userName"), "display": j.get("displayName"), "active": j.get("active")}

    def warehouses(self) -> list[dict]:
        """SQL warehouses visible to this identity: id, name, state, http_path."""
        try:
            r = self.s.get(f"{self.cfg.host}/api/2.0/sql/warehouses", headers=_bearer(self.cfg, self.s), timeout=self.cfg.timeout_s)
        except requests.RequestException as e:
            raise DatabricksUnreachable(str(e)) from e
        if r.status_code in (401, 403):
            raise DatabricksAuthError(f"HTTP {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        return [{"id": w["id"], "name": w.get("name"), "state": w.get("state"),
                 "http_path": (w.get("odbc_params") or {}).get("path") or f"/sql/1.0/warehouses/{w['id']}"}
                for w in r.json().get("warehouses", [])]

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
INLINE_ROW_LIMIT = 50_000     # below this, ask for INLINE JSON (one round trip, no cloud-storage host needed)


class DatabricksSQL:
    def __init__(self, cfg: DatabricksConfig | None = None, session: requests.Session | None = None):
        self.cfg = cfg or DatabricksConfig()
        self.s = session or requests.Session()
        if not self.cfg.http_path:
            # no warehouse named: take the one that is running (or the only one) and say which
            ws = UnityCatalogClient(self.cfg, self.s).warehouses()
            running = [w for w in ws if w["state"] == "RUNNING"] or ws
            if not running:
                raise DatabricksError("DATABRICKS_HTTP_PATH is unset and this identity sees no SQL warehouse")
            self.cfg.http_path = running[0]["http_path"]
            self.picked_warehouse = running[0]
        self.warehouse_id = self.cfg.http_path.rstrip("/").split("/")[-1]

    def query(self, sql: str, *, wait_s: int = 600, inline: bool | None = None) -> pl.DataFrame:
        """`inline=None` picks INLINE for statements with a small LIMIT, EXTERNAL_LINKS otherwise.
        External links are presigned cloud-storage URLs (Azure blob/dfs hosts), which a locked-down
        network must also allow; inline needs only the workspace host."""
        try:
            return self._query_connector(sql)
        except ImportError:
            pass
        if inline is None:
            m = re.search(r"\bLIMIT\s+(\d+)\s*$", sql.strip(), re.I)
            inline = bool(m and int(m.group(1)) <= INLINE_ROW_LIMIT)
        return self._query_rest(sql, wait_s=wait_s, inline=inline)

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
            r = self.s.post(f"{self.cfg.host}{path}", headers=_bearer(self.cfg, self.s), json=body, timeout=self.cfg.timeout_s)
        except requests.RequestException as e:
            raise DatabricksUnreachable(str(e)) from e
        if r.status_code in (401, 403):
            raise DatabricksAuthError(r.text[:200])
        if r.status_code >= 400:
            raise DatabricksError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _get(self, path: str) -> dict:
        r = self.s.get(f"{self.cfg.host}{path}", headers=_bearer(self.cfg, self.s), timeout=self.cfg.timeout_s)
        if r.status_code >= 400:
            raise DatabricksError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _query_rest(self, sql: str, *, wait_s: int, inline: bool = False) -> pl.DataFrame:
        body = {"warehouse_id": self.warehouse_id, "statement": sql, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"}
        body.update({"format": "JSON_ARRAY", "disposition": "INLINE"} if inline else {"format": "ARROW_STREAM", "disposition": "EXTERNAL_LINKS"})
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
        return self._collect_inline(j) if inline else self._collect_external_links(j)

    def _collect_inline(self, j: dict) -> pl.DataFrame:
        """INLINE JSON_ARRAY: every value is a string (or null); cast from the manifest types."""
        manifest = j["manifest"]
        cols = manifest["schema"]["columns"]
        rows = list(j.get("result", {}).get("data_array", []) or [])
        for ch in manifest.get("chunks", [])[1:]:
            r = self._get(f"/api/2.0/sql/statements/{j['statement_id']}/result/chunks/{ch['chunk_index']}")
            rows.extend(r.get("data_array", []) or [])
        data = {c["name"]: [row[i] for row in rows] for i, c in enumerate(cols)}
        df = pl.DataFrame(data, schema={c["name"]: pl.Utf8 for c in cols})
        casts = []
        for c in cols:
            t = (c.get("type_name") or "").upper()
            if t in ("INT", "SMALLINT", "TINYINT", "BIGINT", "LONG"):
                casts.append(pl.col(c["name"]).cast(pl.Int64, strict=False))
            elif t in ("FLOAT", "DOUBLE", "DECIMAL"):
                casts.append(pl.col(c["name"]).cast(pl.Float64, strict=False))
            elif t == "BOOLEAN":
                casts.append(pl.col(c["name"]).str.to_lowercase().eq("true").alias(c["name"]))
        return df.with_columns(casts) if casts else df

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
    # DATABRICKS_HTTP_PATH is optional: DatabricksSQL auto-picks the running warehouse when it is unset
    # (the probe does the same). Requiring it here sent a configured Mac to the local export silently.
    if prefer in ("auto", "databricks") and cfg.configured:
        ok, detail = UnityCatalogClient(cfg).reachable()
        if ok:
            try:
                return DataSource(mode="databricks", dbx=DatabricksSQL(cfg))
            except DatabricksError as e:
                if prefer == "databricks":
                    raise
                detail = f"reachable but no usable warehouse/credential: {e}"
        if prefer == "databricks":
            raise DatabricksUnreachable(f"{cfg.host} unreachable: {detail}")
    return DataSource(mode="local", local=LocalDataConfig())
