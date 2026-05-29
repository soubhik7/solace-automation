#!/usr/bin/env python3
"""
mcp_server.py — Solace Automation MCP Server
=============================================
Exposes export / clone / provision / replicate as MCP tools over SSE so that
Langflow (or any MCP client) can call them at:

    http://localhost:8000/sse

Usage
-----
    pip install fastmcp
    python3 mcp_server.py

Environment
-----------
All settings are read from langflow.env (same file used by the Langflow flow),
then overridden by real environment variables if set.

Tools exposed
-------------
  export_service    — snapshot a live Solace service to a config JSON file
  clone_service     — clone a config to a new country
  provision_service — provision Event Portal + cluster from a config file
  replicate_service — full pipeline: export → clone → create service → provision
"""

import json
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

# ── path setup (mirrors solace.py) ────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

# ── load langflow.env ─────────────────────────────────────────────────────────
_ENV_FILE = ROOT / "langflow.env"

def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()

_load_env_file(_ENV_FILE)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger("solace-mcp")

# ── helpers ───────────────────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _build_ctx():
    from context import Context
    ctx = Context.load()
    if not ctx.token:
        raise RuntimeError("SOLACE_API_TOKEN not set — add it to langflow.env or export it")
    return ctx


# ── MCP server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="Solace Automation",
    instructions=(
        "Tools to manage Solace Cloud services: export a live service config, "
        "clone it to a new country, provision Event Portal and broker objects, "
        "or run the full replicate pipeline in one shot."
    ),
)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL: export_service
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def export_service(
    service_id: str = "",
    country: str = "",
    domain_name: str = "",
    output_path: str = "",
) -> str:
    """
    Export a live Solace service to a portable JSON config file.

    Args:
        service_id:  Solace Cloud service ID (defaults to SOLACE_SERVICE_ID env var)
        country:     Country/environment code tag, e.g. 'DEV' or 'AU' (defaults to SOLACE_COUNTRY)
        domain_name: Event Portal domain name to export (defaults to SOLACE_DOMAIN_NAME)
        output_path: Where to write the JSON file (defaults to SOLACE_OUTPUT_PATH)

    Returns JSON summary with status, output path, and object counts.
    """
    from workflows.exporter import Exporter

    sid     = service_id  or _env("SOLACE_SERVICE_ID")
    country = country     or _env("SOLACE_COUNTRY", "DEV")
    dom     = domain_name or _env("SOLACE_DOMAIN_NAME", "")
    out     = output_path or _env(
        "SOLACE_OUTPUT_PATH",
        str(ROOT / "config" / country.lower() / "service.json"),
    )

    if not sid:
        return json.dumps({"status": "error", "message": "service_id is required (or set SOLACE_SERVICE_ID)"})

    try:
        ctx = _build_ctx()
        exp = Exporter(ctx)
        data = exp.export_to_file(
            output_path=out,
            service_id=sid,
            domain_name=dom or None,
            country_code=country or None,
        )
        ep  = data.get("eventPortal", {})
        cm  = data.get("clusterManagement", {})
        return json.dumps({
            "status":      "ok",
            "output":      out,
            "service_id":  sid,
            "country":     country,
            "ep_objects": {
                "schemas":      len(ep.get("schemas", [])),
                "events":       len(ep.get("events", [])),
                "applications": len(ep.get("applications", [])),
            },
            "cluster_objects": {
                "clientProfiles":     len(cm.get("clientProfiles", [])),
                "aclProfiles":        len(cm.get("aclProfiles", [])),
                "clientUsernames":    len(cm.get("clientUsernames", [])),
                "queues":             len(cm.get("queues", [])),
                "restDeliveryPoints": len(cm.get("restDeliveryPoints", [])),
            },
        }, indent=2)
    except Exception as exc:
        logger.exception("export_service failed")
        return json.dumps({"status": "error", "message": str(exc)})


# ══════════════════════════════════════════════════════════════════════════════
# TOOL: clone_service
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def clone_service(
    from_country: str = "",
    to_country: str = "",
    datacenter: str = "",
    service_name: str = "",
    source_config_path: str = "",
    output_path: str = "",
) -> str:
    """
    Clone a service config to a new country by substituting all country codes.

    Args:
        from_country:       Source country code, e.g. 'DEV' (defaults to SOLACE_FROM_COUNTRY)
        to_country:         Target country code, e.g. 'SG'  (defaults to SOLACE_TO_COUNTRY)
        datacenter:         Target datacenter ID, e.g. 'aks-australiaeast' (defaults to SOLACE_DATACENTER)
        service_name:       Override name for the new service (defaults to SOLACE_SERVICE_NAME)
        source_config_path: Path to the source JSON config (defaults to SOLACE_SOURCE_CONFIG)
        output_path:        Where to write the cloned JSON (defaults to SOLACE_OUTPUT_PATH)

    Returns JSON summary with output path, countries, and generated password count.
    """
    from workflows.cloner import Cloner

    frm  = from_country        or _env("SOLACE_FROM_COUNTRY", "")
    to   = to_country          or _env("SOLACE_TO_COUNTRY", "")
    dc   = datacenter          or _env("SOLACE_DATACENTER", "")
    sn   = service_name        or _env("SOLACE_SERVICE_NAME", "")
    src  = source_config_path  or _env("SOLACE_SOURCE_CONFIG", "")
    out  = output_path         or _env(
        "SOLACE_OUTPUT_PATH",
        str(ROOT / "config" / (to.lower() or "clone") / "service.json"),
    )

    for val, name in [(frm, "from_country"), (to, "to_country"), (dc, "datacenter")]:
        if not val:
            return json.dumps({"status": "error", "message": f"'{name}' is required (or set env var)"})

    if not src:
        src = str(ROOT / "config" / frm.lower() / "service.json")

    if not Path(src).exists():
        return json.dumps({"status": "error", "message": f"Source config not found: {src} — run export_service first"})

    try:
        cloner = Cloner()
        cloned = cloner.clone_to_file(
            source_path=src,
            output_path=out,
            target_country=to,
            datacenter=dc,
            service_name=sn or None,
        )
        cm = cloned.get("clusterManagement", {})
        gen_pw = sum(1 for u in cm.get("clientUsernames", []) if u.get("password"))
        return json.dumps({
            "status":             "ok",
            "output":             out,
            "from":               frm,
            "to":                 to,
            "passwords_generated": gen_pw,
        }, indent=2)
    except Exception as exc:
        logger.exception("clone_service failed")
        return json.dumps({"status": "error", "message": str(exc)})


# ══════════════════════════════════════════════════════════════════════════════
# TOOL: provision_service
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def provision_service(
    config_path: str = "",
    dry_run: bool = False,
    skip_ep: bool = False,
    skip_cluster: bool = False,
) -> str:
    """
    Provision Event Portal objects and/or broker cluster objects from a config file.

    Args:
        config_path:  Path to service config JSON (defaults to SOLACE_CONFIG)
        dry_run:      Validate and report what would happen without making changes
        skip_ep:      Skip Event Portal phase (cluster only)
        skip_cluster: Skip cluster/broker phase (EP only)

    Returns JSON summary with status and provisioned object counts.
    """
    from workflows.provision import Provisioner

    cfg_path = config_path or _env("SOLACE_CONFIG", "")
    if not cfg_path:
        return json.dumps({"status": "error", "message": "config_path is required (or set SOLACE_CONFIG)"})
    if not Path(cfg_path).exists():
        return json.dumps({"status": "error", "message": f"Config not found: {cfg_path}"})

    if not dry_run:
        dry_run = _env("SOLACE_DRY_RUN", "false").lower() == "true"

    try:
        ctx = _build_ctx()
        provisioner = Provisioner(ctx, dry_run=dry_run)
        result = provisioner.run(cfg_path, skip_ep=skip_ep, skip_cluster=skip_cluster)
        return json.dumps({"status": "dry_run" if dry_run else "ok", "ep_ids": result}, indent=2)
    except Exception as exc:
        logger.exception("provision_service failed")
        return json.dumps({"status": "error", "message": str(exc)})


# ══════════════════════════════════════════════════════════════════════════════
# TOOL: replicate_service
# ══════════════════════════════════════════════════════════════════════════════
@mcp.tool()
def replicate_service(
    from_country: str = "",
    to_country: str = "",
    datacenter: str = "",
    service_name: str = "",
    service_id: str = "",
    dry_run: bool = False,
) -> str:
    """
    Full one-shot replication pipeline: export the source service, clone it to a
    new country, create the new Solace Cloud messaging service, then provision all
    Event Portal and cluster objects.

    Args:
        from_country: Source country code, e.g. 'DEV' (defaults to SOLACE_FROM_COUNTRY)
        to_country:   Target country code, e.g. 'SG'  (defaults to SOLACE_TO_COUNTRY)
        datacenter:   Target datacenter ID             (defaults to SOLACE_DATACENTER)
        service_name: Name for the new service         (defaults to SOLACE_SERVICE_NAME)
        service_id:   Use existing service ID instead of creating one (optional)
        dry_run:      Export + clone only, skip service creation and provisioning

    Returns JSON summary with each pipeline stage result.
    """
    import time
    import copy
    import requests as req
    from workflows.exporter import Exporter
    from workflows.cloner import Cloner
    from workflows.provision import Provisioner, load_config

    frm = from_country or _env("SOLACE_FROM_COUNTRY", "")
    to  = to_country   or _env("SOLACE_TO_COUNTRY", "")
    dc  = datacenter   or _env("SOLACE_DATACENTER", "")
    sn  = service_name or _env("SOLACE_SERVICE_NAME", "")
    sid = service_id   or _env("SOLACE_SERVICE_ID", "")

    if not dry_run:
        dry_run = _env("SOLACE_DRY_RUN", "false").lower() == "true"

    for val, name in [(frm, "from_country"), (to, "to_country"), (dc, "datacenter")]:
        if not val:
            return json.dumps({"status": "error", "message": f"'{name}' is required"})

    tmp_path = ROOT / "config" / f"replicate-tmp-{frm.lower()}.json"
    out_path = ROOT / "config" / to.lower() / "service.json"
    stages: dict = {}

    try:
        ctx = _build_ctx()

        # ── Stage 1: export ────────────────────────────────────────────────
        logger.info("REPLICATE  stage=export  %s → %s", frm, to)
        exp  = Exporter(ctx)
        data = exp.export_to_file(
            output_path=str(tmp_path),
            service_id=sid or ctx.service_id,
            country_code=frm,
        )
        stages["export"] = {"status": "ok", "output": str(tmp_path)}

        # ── Stage 2: clone ─────────────────────────────────────────────────
        logger.info("REPLICATE  stage=clone")
        cloner = Cloner()
        cloned = cloner.clone_to_file(
            source_path=str(tmp_path),
            output_path=str(out_path),
            target_country=to,
            datacenter=dc,
            service_name=sn or None,
        )
        stages["clone"] = {"status": "ok", "output": str(out_path)}

        if dry_run:
            stages["provision"] = {"status": "skipped", "reason": "dry_run=true"}
            return json.dumps({"status": "dry_run", "stages": stages}, indent=2)

        # ── Stage 3: create messaging service ─────────────────────────────
        token = ctx.token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        svc_cfg = cloned.get("service", {})
        logger.info("REPLICATE  stage=create_service  name=%s", svc_cfg.get("name", ""))

        r = req.post(
            "https://api.solace.cloud/api/v0/services",
            json={
                "name":           svc_cfg.get("name", f"automation-{to.lower()}"),
                "datacenterId":   dc,
                "serviceTypeId":  svc_cfg.get("serviceTypeId",  "developer"),
                "serviceClassId": svc_cfg.get("serviceClassId", "developer"),
            },
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        new_svc    = r.json().get("data", {})
        new_svc_id = new_svc.get("serviceId", "")
        stages["create_service"] = {"status": "ok", "serviceId": new_svc_id}

        # Wait for service to become active (up to 10 min)
        logger.info("REPLICATE  waiting for service %s to become active ...", new_svc_id)
        for _ in range(60):
            time.sleep(10)
            info = req.get(
                f"https://api.solace.cloud/api/v0/services/{new_svc_id}",
                headers=headers, timeout=15,
            ).json().get("data", {})
            state = info.get("operationStatus", info.get("adminState", ""))
            logger.info("  state=%s", state)
            if state in ("completed", "succeeded", "active"):
                break
        new_vpn = info.get("msgVpnName", "")

        # Patch config with real serviceId + vpnName
        cloned["service"]["serviceId"]             = new_svc_id
        cloned["clusterManagement"]["vpnName"]     = new_vpn
        out_path.write_text(json.dumps(cloned, indent=2))

        # ── Stage 4: provision ─────────────────────────────────────────────
        logger.info("REPLICATE  stage=provision  vpn=%s", new_vpn)
        from api.cloud_svc import CloudServiceAPI
        from client import SolaceClient
        cloud   = CloudServiceAPI(SolaceClient.from_context(ctx.as_dict()))
        svc_det = cloud.get_service(new_svc_id)
        creds   = cloud.extract_semp_creds(svc_det)
        new_ctx = type(ctx)(ctx.as_dict())
        new_ctx.set_service(
            new_svc_id,
            creds["vpnName"],
            creds["sempBaseUrl"],
            creds["sempUsername"],
            creds["sempPassword"],
        )
        prov   = Provisioner(new_ctx)
        result = prov.run(str(out_path))
        stages["provision"] = {"status": "ok", "ep_ids": result}

        return json.dumps({"status": "ok", "stages": stages}, indent=2)

    except Exception as exc:
        logger.exception("replicate_service failed")
        return json.dumps({"status": "error", "message": str(exc), "stages": stages}, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Solace Automation MCP Server")
    p.add_argument("--host", default="0.0.0.0",    help="Bind host (default: 0.0.0.0)")
    p.add_argument("--port", default=8000, type=int, help="Bind port (default: 8000)")
    args = p.parse_args()

    logger.info("Starting Solace Automation MCP server  →  http://%s:%d/sse", args.host, args.port)
    logger.info("Connect Langflow MCP Tools to:  http://localhost:%d/sse", args.port)
    mcp.run(transport="sse", host=args.host, port=args.port)
