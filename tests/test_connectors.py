import base64
import json
import os
from pathlib import Path

import polars as pl
import pytest
import requests

from position_hub import config
from position_hub.config import DatabricksConfig, LocalDataConfig, OpenFieldConfig, ThunderConfig, table_name
from position_hub.databricks.client import DataSource, UnityCatalogClient
from position_hub.telemetry.openfield import OpenFieldClient, decode_jwt_claims, token_product
from position_hub.telemetry.pff_ultimate import film_links_for_snaps, pff_ultimate_play_url
from position_hub.telemetry.thunder import ThunderClient, gsis_payload, launch_by_gsis
from position_hub.viewer.export import export_viewer_json


class FakeResp:
    def __init__(self, status, body, is_json=True):
        self.status_code, self._body, self._json = status, body, is_json
        self.ok = status < 400
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if not self._json:
            raise ValueError("not json")
        return self._body if not isinstance(self._body, str) else json.loads(self._body)


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _hit(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for key, resp in self.routes.items():
            if key in url:
                return resp(kw) if callable(resp) else resp
        return FakeResp(404, {"Message": "nf"})

    def get(self, url, **kw):
        return self._hit("GET", url, **kw)

    def post(self, url, **kw):
        return self._hit("POST", url, **kw)


# ── Unity Catalog names ────────────────────────────────────────────────────────────────────────
def test_table_registry_is_pff_bronze_and_overridable(monkeypatch):
    assert table_name("pffdefense") == "pff.bronze.pffdefense"
    assert table_name("coverage_defense") == "pff.bronze.coverage_defense"
    monkeypatch.setenv("POSHUB_TABLE_PFFDEFENSE", "pff.silver.pffdefense_clean")
    assert table_name("pffdefense") == "pff.silver.pffdefense_clean"
    with pytest.raises(KeyError):
        table_name("nope")


def test_uc_client_paginates_and_separates_unreachable_from_auth(monkeypatch):
    cfg = DatabricksConfig(host="https://adb-7405617646104787.7.azuredatabricks.net", token="dapiXXX", http_path="/sql/1.0/warehouses/abc")
    pages = iter([FakeResp(200, {"catalogs": [{"name": "pff"}], "next_page_token": "t2"}),
                  FakeResp(200, {"catalogs": [{"name": "ngs"}]})])
    s = FakeSession({"unity-catalog/catalogs": lambda kw: next(pages)})
    uc = UnityCatalogClient(cfg, session=s)
    assert [c["name"] for c in uc.catalogs()] == ["pff", "ngs"]
    assert s.calls[0][2]["headers"]["Authorization"] == "Bearer dapiXXX"

    class Boom(FakeSession):
        def get(self, url, **kw):
            raise requests.ConnectionError("CONNECT tunnel failed, response 403")
    ok, detail = UnityCatalogClient(cfg, session=Boom({})).reachable()
    assert ok is False and "403" in detail


def test_local_datasource_reads_export_layout(tmp_path):
    d = tmp_path / "data" / "pff_export" / "pffdefense"
    d.mkdir(parents=True)
    pl.DataFrame({"pff_GAMEID": [1, 2], "pff_POSITION": ["FSL", "LEO"]}).write_parquet(d / "part-0.parquet")
    src = DataSource(mode="local", local=LocalDataConfig(root=tmp_path))
    out = src.read("pffdefense", ["pff_POSITION"])
    assert out["pff_POSITION"].to_list() == ["FSL", "LEO"]
    with pytest.raises(FileNotFoundError):
        src.read("pffplays")


# ── Thunder ────────────────────────────────────────────────────────────────────────────────────
def test_thunder_uses_api_scheme_not_basic_and_reports_two_facts():
    cfg = ThunderConfig(username="u@panthers.nfl.com", password="pw", vendor_guid="")
    s = FakeSession({"GetHealth": FakeResp(200, "\"<Health><Status>ok</Status></Health>\""),
                     "GetAllViews": FakeResp(200, [{"Id": "v1", "Name": "Sideline"}])})
    t = ThunderClient(cfg, session=s)
    st = t.status()
    assert st == {"vendor_up": True, "health_raw": "<Health><Status>ok</Status></Health>", "credential_present": True, "credential_valid": True}
    hdr = [c for c in s.calls if "GetAllViews" in c[1]][0][2]["headers"]["Authorization"]
    assert hdr == "API " + base64.b64encode(b"u@panthers.nfl.com:pw").decode()
    assert not hdr.startswith("Basic")
    # GetHealth goes out WITHOUT a credential
    assert "Authorization" not in [c for c in s.calls if "GetHealth" in c[1]][0][2]["headers"]


def test_thunder_500_is_flagged_as_likely_credential_problem():
    cfg = ThunderConfig(username="u", password="wrong")
    s = FakeSession({"GetAllViews": FakeResp(500, {"Message": "An error has occurred."})})
    r = ThunderClient(cfg, session=s).views()
    assert r.ok is False and r.likely_auth is True and r.status == 500
    r2 = ThunderClient(ThunderConfig(username="", password=""), session=s).views()
    assert r2.ok is False and r2.likely_auth and "no credential" in r2.error


def test_thunder_deep_link_speaks_our_keys():
    assert gsis_payload([(59848, 101), (59848, 140), (59900, 7)]) == "^59848|101,140^59900|7"
    url = launch_by_gsis([(59848, 101)], token="TOK", vendor="VEND")
    assert url.startswith("http://localhost:8080/XOS/LaunchPlayerByGSIS?gameCodePlayId=<root><authentication token='TOK' vendor='VEND'/>")
    assert "<payload>^59848|101</payload>" in url
    with pytest.raises(ValueError):
        launch_by_gsis([], "t", "v")


def test_thunder_sso_needs_vendor_guid_and_posts_api_header():
    cfg = ThunderConfig(username="u", password="p", vendor_guid="")
    assert ThunderClient(cfg, session=FakeSession({})).sso_token().error == "missing: THUNDER_VENDOR_GUID"
    cfg = ThunderConfig(username="u", password="p", vendor_guid="G")
    s = FakeSession({"GenerateToken": FakeResp(200, {"GenerateTokenResult": "abc"})})
    r = ThunderClient(cfg, session=s).sso_token()
    assert r.ok and r.data == {"token": "abc", "expires_in_min": 15}
    assert s.calls[0][2]["json"] == {"productId": "G"} and s.calls[0][2]["headers"]["Authorization"].startswith("API ")


# ── OpenField ──────────────────────────────────────────────────────────────────────────────────
def _jwt(payload: dict) -> str:
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'none'})}.{b(payload)}.sig"


def test_openfield_token_is_named_before_it_is_used():
    tok = _jwt({"iss": "https://backend-us.openfield.catapultsports.com", "scope": ["sensor-read-only"]})
    assert token_product(tok) == "openfield"
    assert decode_jwt_claims(tok)["iss"].endswith("catapultsports.com")
    assert token_product("not-a-jwt") == "unknown"
    s = FakeSession({"athletes": FakeResp(200, [{"id": "a1"}, {"id": "a2"}])})
    p = OpenFieldClient(OpenFieldConfig(token=tok), session=s).probe()
    assert p["token_product"] == "openfield" and p["auth_ok"] and p["n_athletes"] == 2
    assert s.calls[0][2]["headers"]["Authorization"] == f"Bearer {tok}"
    assert OpenFieldClient(OpenFieldConfig(token=""), session=s).probe()["token_present"] is False


# ── PFF Ultimate + viewer ──────────────────────────────────────────────────────────────────────
def test_film_links_join_through_pffplays_keys():
    assert pff_ultimate_play_url(123) == "https://ultimate.pff.com/play/123"
    snaps = pl.DataFrame({"game_key": [59848, 59848], "gsis_play_id": [101, 140], "nfl_id": [1, 2]})
    plays = pl.DataFrame({"game_key": [59848, 59848], "gsis_play_id": [101, 140], "pff_PLAYID": [900, 901]})
    out = film_links_for_snaps(snaps, plays, thunder_token="T", thunder_vendor="V")
    assert out["pff_ultimate_url"].to_list() == ["https://ultimate.pff.com/play/900", "https://ultimate.pff.com/play/901"]
    assert "^59848|140" in out["thunder_url"][1]
    assert film_links_for_snaps(snaps, plays)["thunder_url"].null_count() == 2


def test_viewer_export_shape(tmp_path):
    mix = pl.DataFrame({"nfl_id": [1], "season": [2025], "player_name": ["A"], "roster_pos": ["FS"], "peer_group": ["S"], "team": ["CAR"],
                        "snaps": [400], "pass_snap_share": [0.6], "primary_role": ["DEEP_MIDDLE"], "align_entropy": [0.7], "mean_depth": [11.0],
                        "box_rate": [0.2], "mean_bite_2s": [1.1], "mean_ground_covered_2s": [3.0], "share_DEEP_MIDDLE": [0.7], "share_BOX_SAFETY": [0.3],
                        "hard_share_DEEP_MIDDLE": [0.75], "resp_DEEP_ZONE": [0.6], "pct_share_DEEP_MIDDLE": [88.0]})
    doc = export_viewer_json(mix, tmp_path / "v.json", gates=[{"name": "g", "value": 0.9, "bar": 0.7, "pass": True, "n": 10, "note": ""}])
    p = doc["players"][0]
    assert p["align"] == {"DEEP_MIDDLE": 0.7, "BOX_SAFETY": 0.3} and p["pct"] == {"share_DEEP_MIDDLE": 88.0}
    assert json.loads((tmp_path / "v.json").read_text())["meta"]["gates"][0]["pass"] is True
