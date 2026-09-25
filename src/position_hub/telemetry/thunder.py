"""Thunder / XOS — Catapult's film product. Python port of panthers_projects/web/lib/thunder/*.

⛔ Everything below was MEASURED in the sister repo (evaluation/thunder_auth_probe.py, 2026-08-31):
  * Auth scheme is the custom  `Authorization: API <base64(username:password)>`. NOT Basic, NOT Bearer.
    Basic returns 500, identical to sending nothing.
  * A bad or missing credential returns 500 {"Message":"An error has occurred."}, NOT 401. So a
    credential problem looks like a vendor outage. GetHealth answers without a credential and is the
    only way to separate "vendor down" from "credential wrong" — check it first, report both facts.
  * GetHealth's body is XML wrapped in a JSON string.
  * A Catapult OpenField JWT is NOT a Thunder credential (see openfield.py).
  * GetURLsForElement takes a media ELEMENT guid (from play data), not a play id; the signed
    CloudFront URLs it returns live ~1.1 days.
  * The deep link `LaunchPlayerByGSIS` speaks OUR keys: game_key + gsis_play_id.
Spec: https://tclightningservices.xosdigital.com/Api/swagger/docs/v1 (ThunderAPI v1, 39 endpoints).
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any, Iterable

import requests

from ..config import ThunderConfig

SOB = {  # side-of-ball GUIDs, stable server-side; required by GetContentsOfGamePlan
    "defense": "66d039cb-23cc-db11-9ce4-0015c50846d6",
    "offense": "783055bf-23cc-db11-9ce4-0015c50846d6",
    "special_teams": "122f34d4-23cc-db11-9ce4-0015c50846d6",
}


@dataclass
class ThunderResult:
    ok: bool
    status: int = 0
    data: Any = None
    error: str = ""
    likely_auth: bool = False


def _api_header(user: str, pw: str) -> dict[str, str]:
    return {"Authorization": "API " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


def _likely_auth(status: int, raw: str) -> bool:
    return status in (401, 403) or (status == 500 and re.search(r"an error has occurred", raw, re.I) is not None)


class ThunderClient:
    def __init__(self, cfg: ThunderConfig | None = None, session: requests.Session | None = None, timeout: int = 60):
        self.cfg = cfg or ThunderConfig()
        self.s = session or requests.Session()
        self.timeout = timeout

    # ── plumbing ───────────────────────────────────────────────────────────────────────────────
    def _call(self, path: str, params: dict[str, str] | None = None, *, need_credential: bool = True) -> ThunderResult:
        headers = {"Accept": "application/json"}
        if need_credential:
            if not self.cfg.has_credential:
                return ThunderResult(False, 0, error="no credential — set THUNDER_USERNAME and THUNDER_PASSWORD", likely_auth=True)
            headers.update(_api_header(self.cfg.username, self.cfg.password))
        url = f"{self.cfg.base_url}/ThunderAPI/{path}"
        try:
            r = self.s.get(url, headers=headers, params=params or {}, timeout=self.timeout)
        except requests.RequestException as e:
            return ThunderResult(False, 0, error=f"network: {e}")
        raw = r.text
        if not r.ok:
            return ThunderResult(False, r.status_code, error=f"HTTP {r.status_code}: {raw[:200]}", likely_auth=_likely_auth(r.status_code, raw))
        try:
            return ThunderResult(True, r.status_code, data=r.json())
        except ValueError:
            return ThunderResult(False, r.status_code, error=f"unparseable: {raw[:200]}")

    # ── two facts, reported separately ─────────────────────────────────────────────────────────
    def health(self) -> ThunderResult:
        """Answers WITHOUT a credential. Body is XML inside a JSON string; returned as-is."""
        return self._call("GetHealth", need_credential=False)

    def status(self) -> dict:
        h = self.health()
        vendor_up = h.ok and "ok" in str(h.data).lower()
        out = {"vendor_up": vendor_up, "health_raw": str(h.data)[:200] if h.ok else h.error,
               "credential_present": self.cfg.has_credential, "credential_valid": None}
        if self.cfg.has_credential and vendor_up:
            v = self.views()
            out["credential_valid"] = v.ok
            if not v.ok:
                out["credential_error"] = v.error
        return out

    # ── endpoints we consume ───────────────────────────────────────────────────────────────────
    def views(self) -> ThunderResult:
        return self._call("GetAllViews")

    def root_gameplan_folder(self) -> ThunderResult:
        return self._call("GetRootGameplanFolder")

    def gameplan_contents(self, gameplan_id: str, side_of_ball: str = "defense") -> ThunderResult:
        return self._call("GetContentsOfGamePlan", {"gameplanId": gameplan_id, "sideOfBallId": SOB[side_of_ball]})

    def folder_detail(self, root_folder_id: str, side_of_ball: str = "defense") -> ThunderResult:
        # `check=true` is required or the call 404s
        return self._call("GetFolderDetail", {"rootFolderId": root_folder_id, "check": "true", "sobId": SOB[side_of_ball]})

    def plays_for_edit(self, edit_id: str) -> ThunderResult:
        return self._call("GetPlaysForEdit", {"editID": edit_id})

    def plays(self, play_guids: Iterable[str]) -> ThunderResult:
        return self._call("GetPlays", {"playIDs": ":".join(play_guids)})

    def urls_for_element(self, element_guid: str) -> ThunderResult:
        """Signed CloudFront MP4 URLs (renditions _450 / _1200). Valid ~1.1 days; never cache longer."""
        return self._call("GetURLsForElement", {"element": element_guid})

    # ── SSO token for deep links (third host) ──────────────────────────────────────────────────
    def sso_token(self, duration_min: int | None = None) -> ThunderResult:
        missing = [n for n, v in (("THUNDER_USERNAME", self.cfg.username), ("THUNDER_PASSWORD", self.cfg.password),
                                  ("THUNDER_VENDOR_GUID", self.cfg.vendor_guid)) if not v]
        if missing:
            return ThunderResult(False, 0, error=f"missing: {', '.join(missing)}", likely_auth=True)
        path = "/GenerateTokenWithDuration" if duration_min else "/GenerateToken"
        body = {"productId": self.cfg.vendor_guid}
        if duration_min:
            body["durationInMins"] = str(duration_min)
        try:
            r = self.s.post(self.cfg.sso_url + path, json=body, timeout=20,
                            headers={"Content-Type": "application/json", **_api_header(self.cfg.username, self.cfg.password)})
        except requests.RequestException as e:
            return ThunderResult(False, 0, error=f"network: {e}")
        if not r.ok:
            return ThunderResult(False, r.status_code, error=f"HTTP {r.status_code}: {r.text[:200]}")
        j = r.json()
        tok = j.get("GenerateTokenResult") or j.get("GenerateTokenWithDurationResult")
        if not tok:
            return ThunderResult(False, r.status_code, error=f"no token in response: {r.text[:200]}")
        return ThunderResult(True, r.status_code, data={"token": tok, "expires_in_min": duration_min or 15})


# ── deep links: pure string construction, no secret of its own ─────────────────────────────────
PREFIX = {"desktop": "http://localhost:8080", "desktop-tls": "https://localhost:8081", "cloud": "thunderCloud:/"}


def _wrap(token: str, vendor: str, payload: str) -> str:
    return f"<root><authentication token='{token}' vendor='{vendor}'/><payload>{payload}</payload></root>"


def gsis_payload(plays: Iterable[tuple[int | str, int | str]]) -> str:
    """[(game_key, gsis_play_id), ...] → ^game|p,p^game|p  (grouped per game, order preserved)."""
    by_game: dict[str, list[str]] = {}
    for g, p in plays:
        by_game.setdefault(str(g), []).append(str(p))
    return "".join(f"^{g}|{','.join(ps)}" for g, ps in by_game.items())


def launch_by_gsis(plays: list[tuple[int | str, int | str]], token: str, vendor: str, target: str = "desktop") -> str:
    if not plays:
        raise ValueError("no plays")
    return f"{PREFIX[target]}/XOS/LaunchPlayerByGSIS?gameCodePlayId=" + _wrap(token, vendor, gsis_payload(plays))


def launch_by_play_guids(guids: list[str], token: str, vendor: str, target: str = "desktop") -> str:
    return f"{PREFIX[target]}/XOS/LaunchPlayerByPlays?plays=" + _wrap(token, vendor, ",".join(guids))
