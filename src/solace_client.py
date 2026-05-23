"""
Solace Base HTTP Client
=======================
Handles authenticated REST calls to:
  - Solace Event Portal Designer API  (https://api.solace.cloud/api/v2/architecture/*)
    → uses Bearer token auth (SOLACE_API_TOKEN)

  - Solace SEMP v2 Config API on the broker (https://<broker-host>:943/SEMP/v2/config/*)
    → uses HTTP Basic Auth (SEMP admin username + password from the service details)

Auth split
----------
  EP Designer  → Bearer token via Authorization header
  SEMP broker  → Basic auth (semp_username / semp_password)
"""

import os
import logging
import requests
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Default Base URLs ────────────────────────────────────────────────────────
EP_BASE_URL = "https://api.solace.cloud/api/v2/architecture"   # Event Portal Designer


class SolaceAPIError(Exception):
    """Raised when Solace API returns a non-2xx response."""
    def __init__(self, method: str, url: str, status: int, body: Any):
        self.method = method
        self.url    = url
        self.status = status
        self.body   = body
        super().__init__(f"[{status}] {method} {url} → {body}")


class SolaceClient:
    """
    Thin wrapper around requests.Session for Solace Cloud APIs.

    Parameters
    ----------
    token          : Solace Cloud API token (Bearer) — for Event Portal API
    base_ep        : Event Portal Designer base URL
    semp_base_url  : SEMP v2 Config base URL on the broker,
                     e.g. "https://mr-connection-xxx.messaging.solace.cloud:943/SEMP/v2/config"
    semp_username  : SEMP admin username (from service managementProtocols)
    semp_password  : SEMP admin password

    Usage
    -----
    client = SolaceClient(
        token         = os.environ["SOLACE_API_TOKEN"],
        semp_base_url = "https://mr-connection-xxx.messaging.solace.cloud:943/SEMP/v2/config",
        semp_username = "msgvpn-xxx-admin",
        semp_password = "abc123",
    )
    domains = client.ep_get("/applicationDomains")
    queues  = client.semp_get("/msgVpns/msgvpn-xxx/queues")
    """

    def __init__(self,
                 token: Optional[str] = None,
                 base_ep: str = EP_BASE_URL,
                 semp_base_url: str = "",
                 semp_username: str = "",
                 semp_password: str = ""):
        self.token         = token or os.environ["SOLACE_API_TOKEN"]
        self.base_ep       = base_ep.rstrip("/")
        self.semp_base_url = semp_base_url.rstrip("/")
        self.semp_username = semp_username
        self.semp_password = semp_password

        # Session for Event Portal (Bearer auth)
        self._ep_session = requests.Session()
        self._ep_session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })

        # Session for SEMP (Basic auth)
        self._semp_session = requests.Session()
        if semp_username and semp_password:
            self._semp_session.auth = (semp_username, semp_password)
        self._semp_session.headers.update({
            "Content-Type": "application/json",
            "Accept":       "application/json",
        })

    # ── Internal helper ──────────────────────────────────────────────────────
    def _request(self, session: requests.Session, method: str, url: str, **kwargs) -> Any:
        logger.debug("%s %s", method, url)
        resp = session.request(method, url, **kwargs)
        try:
            body = resp.json()
        except Exception:
            body = resp.text

        if not resp.ok:
            raise SolaceAPIError(method, url, resp.status_code, body)

        logger.debug("→ %s", resp.status_code)
        return body

    # ── Event Portal Designer API (Bearer token) ──────────────────────────────
    def ep_get(self, path: str, params: dict = None) -> Any:
        return self._request(self._ep_session, "GET",    f"{self.base_ep}{path}", params=params)

    def ep_post(self, path: str, payload: dict) -> Any:
        return self._request(self._ep_session, "POST",   f"{self.base_ep}{path}", json=payload)

    def ep_patch(self, path: str, payload: dict) -> Any:
        return self._request(self._ep_session, "PATCH",  f"{self.base_ep}{path}", json=payload)

    def ep_delete(self, path: str) -> Any:
        return self._request(self._ep_session, "DELETE", f"{self.base_ep}{path}")

    # ── SEMP v2 Broker API (Basic auth) ───────────────────────────────────────
    def semp_get(self, path: str, params: dict = None) -> Any:
        return self._request(self._semp_session, "GET",    f"{self.semp_base_url}{path}", params=params)

    def semp_post(self, path: str, payload: dict) -> Any:
        return self._request(self._semp_session, "POST",   f"{self.semp_base_url}{path}", json=payload)

    def semp_patch(self, path: str, payload: dict) -> Any:
        return self._request(self._semp_session, "PATCH",  f"{self.semp_base_url}{path}", json=payload)

    def semp_delete(self, path: str) -> Any:
        return self._request(self._semp_session, "DELETE", f"{self.semp_base_url}{path}")
