"""
src/api/cloud_svc.py — Solace Cloud Service API
================================================
Manages Solace Cloud messaging services (the broker VMs) via:
  https://api.solace.cloud/api/v0/services
  https://api.solace.cloud/api/v0/datacenters
  https://api.solace.cloud/api/v0/serviceTypes

──────────────────────────────────────────────────────────────────
 API REFERENCE
──────────────────────────────────────────────────────────────────
 GET    /api/v0/datacenters              list available datacenters
 GET    /api/v0/serviceTypes             list service types + classes
 GET    /api/v0/services                 list all services
 POST   /api/v0/services                 create a new service
 GET    /api/v0/services/{id}            get service details + SEMP creds
 PATCH  /api/v0/services/{id}            update service
 DELETE /api/v0/services/{id}            delete service
──────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import logging
import time
from typing import Optional
from client import SolaceClient

logger = logging.getLogger(__name__)


class CloudServiceAPI:

    def __init__(self, client: SolaceClient):
        self.c = client

    # ── Datacenters ────────────────────────────────────────────────────────
    def list_datacenters(self, service_class: str = None) -> list[dict]:
        """GET /api/v0/datacenters — optionally filter by service class support."""
        resp = self.c.cloud_get("/api/v0/datacenters")
        dcs = resp.get("data", [])
        if service_class:
            dcs = [d for d in dcs if service_class in d.get("supportedServiceClasses", [])]
        return dcs

    # ── Service types ──────────────────────────────────────────────────────
    def list_service_types(self) -> list[dict]:
        """GET /api/v0/serviceTypes — returns types + their classes (developer, enterprise…)."""
        resp = self.c.cloud_get("/api/v0/serviceTypes")
        return resp.get("data", [])

    def get_service_type_map(self) -> dict[str, list[str]]:
        """Returns {serviceTypeId: [serviceClassId, ...]} for easy validation."""
        result = {}
        for st in self.list_service_types():
            result[st["id"]] = [sc["id"] for sc in st.get("serviceClasses", [])]
        return result

    # ── Services ───────────────────────────────────────────────────────────
    def list_services(self) -> list[dict]:
        """GET /api/v0/services — list all services in the organization."""
        resp = self.c.cloud_get("/api/v0/services")
        return resp.get("data", [])

    def get_service(self, service_id: str) -> dict:
        """GET /api/v0/services/{id} — full service details including SEMP credentials."""
        resp = self.c.cloud_get(f"/api/v0/services/{service_id}")
        return resp.get("data", resp)

    def create_service(self, name: str, service_type: str,
                       service_class: str, datacenter: str,
                       admin_state: str = "start") -> dict:
        """
        POST /api/v0/services — provision a new messaging service.

        Parameters
        ----------
        name          : display name for the service
        service_type  : e.g. 'developer', 'enterprise', 'enterprise-standalone'
        service_class : e.g. 'developer', 'enterprise-kilo', 'enterprise-1k-standalone'
        datacenter    : datacenter id, e.g. 'aks-centralus', 'aks-australiaeast'
        admin_state   : 'start' (default) | 'stop'
        """
        payload = {
            "name":           name,
            "serviceTypeId":  service_type,
            "serviceClassId": service_class,
            "datacenterId":   datacenter,
            "adminState":     admin_state,
            "partitionId":    "default",
        }
        logger.info("Creating service '%s' (%s/%s) in %s ...", name, service_type, service_class, datacenter)
        resp = self.c.cloud_post("/api/v0/services", payload)
        svc = resp.get("data", resp)
        logger.info("✓ Service created → serviceId=%s  state=%s", svc.get("serviceId"), svc.get("creationState"))
        return svc

    def wait_for_service(self, service_id: str,
                          poll_secs: int = 15, timeout_secs: int = 600) -> dict:
        """
        Poll GET /api/v0/services/{id} until creationState == 'completed'.
        Returns the final service dict.
        """
        deadline = time.time() + timeout_secs
        attempt  = 0
        while time.time() < deadline:
            attempt += 1
            svc   = self.get_service(service_id)
            state = svc.get("creationState", "unknown")
            host  = ""
            for ep in svc.get("serviceConnectionEndpoints", []):
                hosts = ep.get("hostNames", [])
                if hosts:
                    host = hosts[0]
            logger.info("  [%d] serviceId=%s  state=%s  host=%s", attempt, service_id, state, host)

            if state == "completed":
                logger.info("✓ Service ready: %s", host)
                return svc
            if state in ("failed", "error"):
                raise RuntimeError(f"Service provisioning failed: state={state}")
            time.sleep(poll_secs)

        raise TimeoutError(f"Service {service_id} not ready after {timeout_secs}s")

    def delete_service(self, service_id: str) -> None:
        """DELETE /api/v0/services/{id}"""
        self.c.cloud_delete(f"/api/v0/services/{service_id}")
        logger.info("Deleted service: %s", service_id)

    def extract_semp_creds(self, service: dict) -> dict:
        """
        Extract SEMP admin credentials and base URL from a service dict.
        Returns: {semp_base_url, semp_username, semp_password, vpn_name, broker_host}
        """
        vpn_name    = service.get("msgVpnName", "")
        broker_host = ""
        semp_port   = 943

        for ep in service.get("serviceConnectionEndpoints", []):
            hosts = ep.get("hostNames", [])
            ports = ep.get("ports", {})
            if hosts:
                broker_host = hosts[0]
                semp_port   = ports.get("serviceManagementTlsListenPort", 943)
                break

        semp_base = f"https://{broker_host}:{semp_port}/SEMP/v2/config" if broker_host else ""

        # Prefer "SEMP Manager" (mission-control-manager = full admin)
        # Fall back to "SEMP" (vpn-scoped admin)
        semp_user = semp_pass = ""
        for preferred in ("SEMP Manager", "SEMP"):
            for proto in service.get("managementProtocols", []):
                if proto.get("name") == preferred:
                    semp_user = proto.get("username", "")
                    semp_pass = proto.get("password", "")
                    break
            if semp_user:
                break

        return {
            "sempBaseUrl":  semp_base,
            "sempUsername": semp_user,
            "sempPassword": semp_pass,
            "vpnName":      vpn_name,
            "brokerHost":   broker_host,
        }
