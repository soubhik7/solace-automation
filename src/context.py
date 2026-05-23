"""
src/context.py — Active-Context Manager
========================================
Persists the currently-selected Solace service (service ID, VPN name,
SEMP URL + credentials) in .solace-context.json so every subsequent
CLI command works without re-passing flags.

Usage
-----
    ctx = Context.load()
    ctx.set_service(service_id, vpn_name, semp_base, semp_user, semp_pass)
    ctx.save()

    # later
    client = SolaceClient.from_context(ctx.as_dict())
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

CONTEXT_FILE = Path(".solace-context.json")


class Context:
    def __init__(self, data: dict = None):
        self._d: dict = data or {}

    # ── persistence ────────────────────────────────────────────────────────
    @classmethod
    def load(cls) -> "Context":
        if CONTEXT_FILE.exists():
            try:
                return cls(json.loads(CONTEXT_FILE.read_text()))
            except Exception:
                pass
        return cls({
            "token":       os.environ.get("SOLACE_API_TOKEN", ""),
            "serviceId":   "",
            "vpnName":     "",
            "sempBaseUrl": "",
            "sempUsername":"",
            "sempPassword":"",
        })

    def save(self) -> None:
        CONTEXT_FILE.write_text(json.dumps(self._d, indent=2))

    # ── setters ────────────────────────────────────────────────────────────
    def set_token(self, token: str) -> None:
        self._d["token"] = token

    def set_service(self, service_id: str, vpn_name: str,
                    semp_base: str, semp_user: str, semp_pass: str) -> None:
        self._d.update({
            "serviceId":   service_id,
            "vpnName":     vpn_name,
            "sempBaseUrl": semp_base,
            "sempUsername": semp_user,
            "sempPassword": semp_pass,
        })

    # ── getters ────────────────────────────────────────────────────────────
    @property
    def token(self)       -> str: return self._d.get("token", os.environ.get("SOLACE_API_TOKEN", ""))
    @property
    def service_id(self)  -> str: return self._d.get("serviceId", "")
    @property
    def vpn_name(self)    -> str: return self._d.get("vpnName", "")
    @property
    def semp_base(self)   -> str: return self._d.get("sempBaseUrl", "")
    @property
    def semp_user(self)   -> str: return self._d.get("sempUsername", "")
    @property
    def semp_pass(self)   -> str: return self._d.get("sempPassword", "")

    def as_dict(self) -> dict:
        return dict(self._d)

    def require_service(self) -> None:
        if not self.service_id:
            raise SystemExit("❌  No active service. Run:  python3 solace.py service use <service-id>")

    def require_semp(self) -> None:
        self.require_service()
        if not self.semp_base:
            raise SystemExit("❌  No SEMP credentials. Run:  python3 solace.py service use <service-id>")

    def summary(self) -> str:
        return (
            f"  token      : {'set ✅' if self.token else 'NOT SET ❌'}\n"
            f"  serviceId  : {self.service_id or '(none)'}\n"
            f"  vpnName    : {self.vpn_name   or '(none)'}\n"
            f"  sempBaseUrl: {self.semp_base  or '(none)'}\n"
            f"  sempUsername: {self.semp_user  or '(none)'}"
        )
