"""Statement Execution API paths, warehouse auto-pick, Azure SP auth, and the probe ladder — all
against a fake session, so they run without the workspace. The real host is exercised by `poshub probe`."""
import io
import json

import polars as pl
import pyarrow as pa
import pyarrow.ipc as ipc
import pytest
import requests

from position_hub.config import DatabricksConfig
from position_hub.databricks import client as C
from position_hub.databricks.client import DatabricksSQL, DatabricksUnreachable
from position_hub.databricks.probe import probe
from test_connectors import FakeResp, FakeSession

HOST = "https://adb-7405617646104787.7.azuredatabricks.net"
WH = {"warehouses": [{"id": "abc123", "name": "Serverless Starter", "state": "RUNNING", "odbc_params": {"path": "/sql/1.0/warehouses/abc123"}},
                     {"id": "old9", "name": "Classic", "state": "STOPPED"}]}


def _inline_statement(rows, cols):
    return FakeResp(200, {"statement_id": "s1", "status": {"state": "SUCCEEDED"},
                          "manifest": {"schema": {"columns": cols}, "chunks": [{"chunk_index": 0}]},
                          "result": {"data_array": rows}})


def test_inline_json_path_casts_from_manifest_types():
    cfg = DatabricksConfig(host=HOST, token="t", http_path="/sql/1.0/warehouses/abc123")
    posted = {}

    def on_post(kw):
        posted.update(kw["json"])
        return _inline_statement([["1", "pff.bronze.pffplays", "true", "2.5"], [None, "x", "false", None]],
                                 [{"name": "n", "type_name": "BIGINT"}, {"name": "t", "type_name": "STRING"},
                                  {"name": "b", "type_name": "BOOLEAN"}, {"name": "f", "type_name": "DOUBLE"}])
    s = FakeSession({"/api/2.0/sql/statements": on_post})
    df = DatabricksSQL(cfg, session=s).query("SELECT * FROM pff.bronze.pffplays LIMIT 2")
    assert posted["disposition"] == "INLINE" and posted["format"] == "JSON_ARRAY" and posted["on_wait_timeout"] == "CONTINUE"
    assert posted["warehouse_id"] == "abc123"
    assert df["n"].to_list() == [1, None] and df["b"].to_list() == [True, False] and df["f"].to_list() == [2.5, None]
    assert df.schema["n"] == pl.Int64


def test_external_links_path_polls_then_fetches_arrow_without_auth_header():
    cfg = DatabricksConfig(host=HOST, token="t", http_path="/sql/1.0/warehouses/abc123")
    tbl = pa.table({"game_key": [59848, 59849], "n": [10, 20]})
    buf = io.BytesIO()
    with ipc.new_stream(buf, tbl.schema) as w:
        w.write_table(tbl)
    states = iter(["RUNNING", "SUCCEEDED"])
    done = {"statement_id": "s2", "status": {"state": "SUCCEEDED"},
            "manifest": {"schema": {"columns": [{"name": "game_key"}, {"name": "n"}]}, "chunks": [{"chunk_index": 0}]},
            "result": {"external_links": [{"external_link": "https://storage.blob.core.windows.net/x?sig=1"}]}}
    posted = {}

    def on_post(kw):
        posted.update(kw["json"])
        return FakeResp(200, {"statement_id": "s2", "status": {"state": "PENDING"}})
    s = FakeSession({"/api/2.0/sql/statements/s2": lambda kw: FakeResp(200, done if next(states) == "SUCCEEDED" else {"statement_id": "s2", "status": {"state": "RUNNING"}}),
                     "/api/2.0/sql/statements": on_post})
    fetched = {}

    class R:
        content = buf.getvalue()

    def fake_get(url, **kw):
        fetched["url"], fetched["kw"] = url, kw
        return R()
    orig, C.requests.get = C.requests.get, fake_get
    orig_sleep, C.time.sleep = C.time.sleep, lambda s_: None
    try:
        df = DatabricksSQL(cfg, session=s).query("SELECT game_key, n FROM pff.bronze.pffplays")
    finally:
        C.requests.get, C.time.sleep = orig, orig_sleep
    assert posted["disposition"] == "EXTERNAL_LINKS" and posted["format"] == "ARROW_STREAM"
    assert df["game_key"].to_list() == [59848, 59849]
    assert "headers" not in fetched["kw"], "presigned storage URL must not receive the bearer token"


def test_warehouse_is_auto_picked_when_http_path_unset():
    cfg = DatabricksConfig(host=HOST, token="t", http_path="")
    s = FakeSession({"/api/2.0/sql/warehouses": FakeResp(200, WH)})
    sql = DatabricksSQL(cfg, session=s)
    assert sql.warehouse_id == "abc123" and sql.picked_warehouse["name"] == "Serverless Starter"


def test_azure_service_principal_token_is_fetched_and_cached():
    C._AAD_CACHE.clear()
    cfg = DatabricksConfig(host=HOST, token="", http_path="/sql/1.0/warehouses/abc123",
                           azure_tenant_id="tenant", azure_client_id="cid", azure_client_secret="sec")
    calls = []

    def on_token(kw):
        calls.append(kw["data"])
        return FakeResp(200, {"access_token": "aad-tok", "expires_in": 3600})
    s = FakeSession({"login.microsoftonline.com/tenant/oauth2/v2.0/token": on_token,
                     "/api/2.0/preview/scim/v2/Me": FakeResp(200, {"userName": "sp@panthers", "active": True})})
    uc = C.UnityCatalogClient(cfg, session=s)
    assert uc.whoami()["user"] == "sp@panthers"
    uc.whoami()
    assert len(calls) == 1, "second call must use the cached token"
    assert calls[0]["scope"] == f"{C.AZURE_DATABRICKS_RESOURCE}/.default" and calls[0]["grant_type"] == "client_credentials"
    me_call = [c for c in s.calls if "scim" in c[1]][0]
    assert me_call[2]["headers"]["Authorization"] == "Bearer aad-tok"
    assert cfg.missing() == []


def test_probe_stops_at_the_first_failing_rung_with_a_remedy():
    class Denied(FakeSession):
        def get(self, url, **kw):
            raise requests.ConnectionError("CONNECT tunnel failed, response 403")
    rep = probe(DatabricksConfig(host=HOST, token="t"), session=Denied({}))
    assert [r.name for r in rep.rungs] == ["host"] and rep.rungs[0].ok is False and "network policy" in rep.rungs[0].remedy
    assert rep.ok is False and "FAIL] host" in rep.format()

    s = FakeSession({"unity-catalog/catalogs": FakeResp(401, {"error_code": "PERMISSION_DENIED"}),
                     "/scim/v2/Me": FakeResp(403, {"detail": "Invalid access token"})})
    rep = probe(DatabricksConfig(host=HOST, token="expired"), session=s)
    assert [r.name for r in rep.rungs] == ["host", "auth"] and rep.rungs[0].ok is True and rep.rungs[1].ok is False
    assert "regenerate the PAT" in rep.rungs[1].remedy

    rep = probe(DatabricksConfig(host=HOST, token=""), session=s)
    assert rep.rungs[1].detail == "no credential"


def test_probe_full_ladder_against_fakes():
    cfg = DatabricksConfig(host=HOST, token="t", http_path="")
    cols = lambda names: [{"name": n, "type_name": "STRING"} for n in names]

    def on_statement(kw):
        stmt = kw["json"]["statement"]
        if stmt.startswith("SELECT 1"):
            return _inline_statement([["1"]], [{"name": "one", "type_name": "INT"}])
        if "COUNT(*)" in stmt:
            return _inline_statement([["1019359"]], [{"name": "n", "type_name": "BIGINT"}])
        if "pffplays" in stmt:
            return _inline_statement([[""] * 7], cols(["pff_GAMEID", "pff_PLAYID", "pff_GSISGAMEKEY", "pff_GSISPLAYID", "pff_GAMESEASON", "pff_RUNPASS", "pff_PASSCOVERAGE"]))
        if "pffdefense" in stmt:
            return _inline_statement([[""] * 6], cols(["pff_GAMEID", "pff_PLAYID", "pff_GSISPLAYERID", "pff_POSITION", "pff_GAMEPOSITION", "pff_ROLE"]))  # BOXPLAYER missing
        return _inline_statement([[""] * 7], cols(["gsis_game_id", "gsis_play_id", "gsis_player_id", "season", "position", "assignment", "modifier1"]))
    s = FakeSession({"unity-catalog/catalogs": FakeResp(401, {}),
                     "/scim/v2/Me": FakeResp(200, {"userName": "akhi@panthers.nfl.com", "displayName": "Akhi"}),
                     "unity-catalog/schemas": FakeResp(200, {"schemas": [{"name": "bronze"}, {"name": "silver"}]}),
                     "/api/2.0/sql/warehouses": FakeResp(200, WH),
                     "/api/2.0/sql/statements": on_statement})
    rep = probe(cfg, session=s)
    names = [r.name for r in rep.rungs]
    assert names == ["host", "auth", "catalog", "warehouse", "sql", "table:pffplays", "table:pffdefense", "table:coverage_defense"]
    by = {r.name: r for r in rep.rungs}
    assert by["auth"].ok and "akhi@panthers.nfl.com" in by["auth"].detail
    assert by["catalog"].ok and by["warehouse"].ok and "auto-picked Serverless Starter" in by["warehouse"].detail
    assert by["sql"].ok and by["table:pffplays"].ok and "1,019,359 rows" in by["table:pffplays"].detail
    assert by["table:pffdefense"].ok is False and "pff_BOXPLAYER" in by["table:pffdefense"].detail
    assert rep.ok is False
    d = rep.to_dict()
    assert json.dumps(d) and d["rungs"][0]["name"] == "host"


def test_azure_cli_token_is_used_when_no_pat_or_sp(monkeypatch):
    """`az login` then nothing else: the chain must call `az account get-access-token` for the
    Databricks resource, cache it, and send it as Bearer."""
    import subprocess
    import types

    C._AAD_CACHE.clear()
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout=json.dumps({"accessToken": "cli-tok", "expires_in": 3000}), stderr="")
    monkeypatch.setattr(C.shutil, "which", lambda name: "/usr/bin/az" if name == "az" else None)
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    cfg = DatabricksConfig(host=HOST, token="", http_path="/sql/1.0/warehouses/abc123")
    assert cfg.missing() == []
    s = FakeSession({"/scim/v2/Me": FakeResp(200, {"userName": "akhi@panthers.nfl.com"})})
    uc = C.UnityCatalogClient(cfg, session=s)
    assert uc.whoami()["user"] == "akhi@panthers.nfl.com"
    uc.whoami()
    assert len(calls) == 1 and calls[0][1:5] == ["account", "get-access-token", "--resource", C.AZURE_DATABRICKS_RESOURCE]
    assert s.calls[0][2]["headers"]["Authorization"] == "Bearer cli-tok"

    # not logged in → the probe names it rather than failing on a 401
    C._AAD_CACHE.clear()
    monkeypatch.setattr(C.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="Please run 'az login'"))
    rep = probe(cfg, session=FakeSession({"unity-catalog/catalogs": FakeResp(401, {})}))
    assert rep.rungs[-1].name == "auth" and rep.rungs[-1].ok is False and "az login" in rep.rungs[-1].remedy


def test_databricks_cli_token_is_preferred_over_azure_cli(monkeypatch):
    """`databricks auth login --host …` once; the chain calls `databricks auth token --host …`."""
    import types

    C._AAD_CACHE.clear()
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[0].endswith("databricks"):
            return types.SimpleNamespace(returncode=0, stdout=json.dumps({"access_token": "dbx-tok", "token_type": "Bearer"}), stderr="")
        return types.SimpleNamespace(returncode=0, stdout=json.dumps({"accessToken": "cli-tok"}), stderr="")
    monkeypatch.setattr(C.shutil, "which", lambda name: f"/opt/homebrew/bin/{name}" if name in ("az", "databricks") else None)
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    cfg = DatabricksConfig(host=HOST, token="", http_path="/sql/1.0/warehouses/abc123")
    s = FakeSession({"/scim/v2/Me": FakeResp(200, {"userName": "akhi@panthers.nfl.com"})})
    assert C.UnityCatalogClient(cfg, session=s).whoami()["user"] == "akhi@panthers.nfl.com"
    assert len(calls) == 1 and calls[0][1:3] == ["auth", "token"] and calls[0][-2:] == ["--host", HOST]
    assert s.calls[0][2]["headers"]["Authorization"] == "Bearer dbx-tok"

    # CLI installed, never logged in: both CLIs fail → the probe says so and names the login command
    C._AAD_CACHE.clear()
    monkeypatch.setattr(C.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="not logged in"))
    rep = probe(cfg, session=FakeSession({"unity-catalog/catalogs": FakeResp(401, {})}))
    r = rep.rungs[-1]
    assert r.name == "auth" and r.ok is False and "Databricks CLI / Azure CLI present" in r.detail and f"databricks auth login --host {HOST}" in r.remedy
