"""Catapult OpenField — athlete GPS / sensor telemetry (the product the club's JWT is actually for).

The token found in the sister project decodes to issuer backend-us.openfield.catapultsports.com with
scopes {connect, catapultr, sensor-read-only, athletes-update, tags-update, activities-update,
annotations-update, parameters-update} and customer id 1302. Those are practice-load / GPS scopes.
It was tried against Thunder (film) and failed, correctly: different product.

⛔ UNVERIFIED FROM THIS ENVIRONMENT: no OpenField call has been made from this repo yet (no token
in the container; host not on the network allow-list). The endpoint paths below follow the public
OpenField Connect API (v6: /athletes, /activities, /activities/{id}/athletes/{id}/sensor,
/activities/{id}/periods, /parameters, /tags) and are Bearer-auth. `probe()` is the first thing to
run once OPENFIELD_TOKEN is set; it reports reachability, auth, and the athlete count separately.

Why this matters for role attribution: practice GPS gives per-athlete load by drill/period, which
is the only source that can say what role a player REHEARSES (e.g. the deep-safety drill share)
versus what the games show. That is a later phase; here the connector and a per-athlete summary.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import requests

from ..config import OpenFieldConfig


def decode_jwt_claims(token: str) -> dict:
    """Payload of a JWT without verifying it (we only need to see what product issued it)."""
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    pad = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(pad))
    except Exception:
        return {}


def token_product(token: str) -> str:
    """'openfield' | 'thunder-like' | 'unknown' — so a wrong-product token is named, not debugged."""
    c = decode_jwt_claims(token)
    iss = str(c.get("iss", ""))
    if "openfield" in iss or "catapultsports" in json.dumps(c).lower():
        return "openfield"
    if not c:
        return "unknown"
    return "thunder-like"


@dataclass
class OFResult:
    ok: bool
    status: int = 0
    data: Any = None
    error: str = ""


class OpenFieldClient:
    def __init__(self, cfg: OpenFieldConfig | None = None, session: requests.Session | None = None, timeout: int = 60):
        self.cfg = cfg or OpenFieldConfig()
        self.s = session or requests.Session()
        self.timeout = timeout

    def _get(self, path: str, **params: Any) -> OFResult:
        if not self.cfg.token:
            return OFResult(False, 0, error="no OPENFIELD_TOKEN")
        try:
            r = self.s.get(f"{self.cfg.base_url}/{path.lstrip('/')}", params=params, timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.cfg.token}", "Accept": "application/json"})
        except requests.RequestException as e:
            return OFResult(False, 0, error=f"network: {e}")
        if not r.ok:
            return OFResult(False, r.status_code, error=f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            return OFResult(True, r.status_code, data=r.json())
        except ValueError:
            return OFResult(False, r.status_code, error=f"unparseable: {r.text[:200]}")

    def probe(self) -> dict:
        out = {"token_present": bool(self.cfg.token), "token_product": token_product(self.cfg.token) if self.cfg.token else None,
               "reachable": None, "auth_ok": None, "n_athletes": None}
        if not self.cfg.token:
            return out
        r = self._get("athletes")
        out["reachable"] = r.status != 0
        out["auth_ok"] = r.ok
        if r.ok and isinstance(r.data, list):
            out["n_athletes"] = len(r.data)
        elif not r.ok:
            out["error"] = r.error
        return out

    def athletes(self) -> OFResult:
        return self._get("athletes")

    def activities(self, start_time: int | None = None, end_time: int | None = None) -> OFResult:
        params = {k: v for k, v in (("startTime", start_time), ("endTime", end_time)) if v is not None}
        return self._get("activities", **params)

    def activity_periods(self, activity_id: str) -> OFResult:
        return self._get(f"activities/{activity_id}/periods")

    def activity_athletes(self, activity_id: str) -> OFResult:
        return self._get(f"activities/{activity_id}/athletes")

    def sensor(self, activity_id: str, athlete_id: str) -> OFResult:
        """10 Hz GPS/IMU stream for one athlete in one activity (scope: sensor-read-only)."""
        return self._get(f"activities/{activity_id}/athletes/{athlete_id}/sensor")

    def parameters(self) -> OFResult:
        return self._get("parameters")
