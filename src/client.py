"""
src/client.py — Unified Solace HTTP Client
==========================================
Single client that handles both auth modes:

  Bearer token  → Event Portal Designer API  (https://api.solace.cloud/api/v2/architecture/*)
  Bearer token  → Solace Cloud API           (https://api.solace.cloud/api/v0/*)
  Basic auth    → Broker SEMP v2 API         (https://<broker>:943/SEMP/v2/config/*)
"""

from __future__ import annotations
import logging
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Optional

logger = logging.getLogger(__name__)

EP_BASE    = "https://api.solace.cloud/api/v2/architecture"
CLOUD_BASE = "https://api.solace.cloud"


class SolaceError(Exception):
    def __init__(self, method: str, url: str, status: int, body: Any):
        self.method, self.url, self.status, self.body = method, url, status, body
        super().__init__(f"[{status}] {method} {url}\n{body}")


def _make_session(retries: int = 3) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


class SolaceClient:
    """
    Thin, retry-capable wrapper.  One instance per runtime; re-used across API modules.

    Instantiate via SolaceClient.from_env() or SolaceClient.from_context(ctx).
    """

    def __init__(self,
                 token: str,
                 semp_base: str = "",
                 semp_user: str = "",
                 semp_pass: str = "",
                 ep_base: str = EP_BASE,
                 cloud_base: str = CLOUD_BASE):
        self.token      = token
        self.ep_base    = ep_base.rstrip("/")
        self.cloud_base = cloud_base.rstrip("/")
        self.semp_base  = semp_base.rstrip("/")

        # ── Event Portal + Cloud session (Bearer) ──────────────────────────
        self._cloud = _make_session()
        self._cloud.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })

        # ── SEMP session (Basic auth) ───────────────────────────────────────
        self._semp = _make_session()
        if semp_user and semp_pass:
            self._semp.auth = (semp_user, semp_pass)
        self._semp.headers.update({
            "Content-Type": "application/json",
            "Accept":       "application/json",
        })

    # ── factory helpers ────────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> "SolaceClient":
        return cls(
            token     = os.environ["SOLACE_API_TOKEN"],
            semp_base = os.environ.get("SEMP_BASE_URL", ""),
            semp_user = os.environ.get("SEMP_USERNAME", ""),
            semp_pass = os.environ.get("SEMP_PASSWORD", ""),
        )

    @classmethod
    def from_context(cls, ctx: dict) -> "SolaceClient":
        return cls(
            token     = ctx["token"],
            semp_base = ctx.get("sempBaseUrl", ""),
            semp_user = ctx.get("sempUsername", ""),
            semp_pass = ctx.get("sempPassword", ""),
        )

    def with_semp(self, semp_base: str, semp_user: str, semp_pass: str) -> "SolaceClient":
        """Return a new client with SEMP credentials set (immutable pattern)."""
        return SolaceClient(
            token=self.token, ep_base=self.ep_base, cloud_base=self.cloud_base,
            semp_base=semp_base, semp_user=semp_user, semp_pass=semp_pass,
        )

    # ── low-level request ──────────────────────────────────────────────────
    def _req(self, sess: requests.Session, method: str, url: str, **kw) -> Any:
        logger.debug("%-6s %s", method, url)
        r = sess.request(method, url, **kw)
        try:
            body = r.json()
        except Exception:
            body = r.text
        if not r.ok:
            raise SolaceError(method, url, r.status_code, body)
        return body

    # ── Event Portal Designer  (Bearer) ────────────────────────────────────
    def ep_get   (self, path: str, params: dict = None) -> Any:
        return self._req(self._cloud, "GET",    self.ep_base + path, params=params)
    def ep_post  (self, path: str, body: dict)          -> Any:
        return self._req(self._cloud, "POST",   self.ep_base + path, json=body)
    def ep_patch (self, path: str, body: dict)          -> Any:
        return self._req(self._cloud, "PATCH",  self.ep_base + path, json=body)
    def ep_delete(self, path: str)                      -> Any:
        return self._req(self._cloud, "DELETE", self.ep_base + path)

    # ── Solace Cloud (Mission Control) (Bearer) ────────────────────────────
    def cloud_get   (self, path: str, params: dict = None) -> Any:
        return self._req(self._cloud, "GET",    self.cloud_base + path, params=params)
    def cloud_post  (self, path: str, body: dict)           -> Any:
        return self._req(self._cloud, "POST",   self.cloud_base + path, json=body)
    def cloud_patch (self, path: str, body: dict)           -> Any:
        return self._req(self._cloud, "PATCH",  self.cloud_base + path, json=body)
    def cloud_delete(self, path: str)                       -> Any:
        return self._req(self._cloud, "DELETE", self.cloud_base + path)

    # ── SEMP v2 Broker (Basic) ─────────────────────────────────────────────
    def semp_get   (self, path: str, params: dict = None) -> Any:
        return self._req(self._semp, "GET",    self.semp_base + path, params=params)
    def semp_post  (self, path: str, body: dict)          -> Any:
        return self._req(self._semp, "POST",   self.semp_base + path, json=body)
    def semp_patch (self, path: str, body: dict)          -> Any:
        return self._req(self._semp, "PATCH",  self.semp_base + path, json=body)
    def semp_put   (self, path: str, body: dict)          -> Any:
        return self._req(self._semp, "PUT",    self.semp_base + path, json=body)
    def semp_delete(self, path: str)                      -> Any:
        return self._req(self._semp, "DELETE", self.semp_base + path)
