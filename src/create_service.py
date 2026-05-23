"""
create_service.py — Main Orchestration Script
=============================================
Automates the full Solace service provisioning lifecycle:

  Phase 1 — Event Portal Design (design-time objects)
    Step 1 : Create / reuse Application Domain
    Step 2 : Create Schema + SchemaVersion (JSON payload structure)
    Step 3 : Create Event + EventVersion   (topic binding)
    Step 4 : Create SourceApp + AppVersion  (publisher)
    Step 5 : Create TargetApp + AppVersion  (subscriber)

  Phase 2 — Cluster Management (runtime objects on the broker)
    Step 6 : Create Client Profile
    Step 7 : Create ACL Profile   (with topic exceptions)
    Step 8 : Create Client Username (credentials)
    Step 9 : Create Queue + Topic Subscriptions
    Step 10: Create REST Delivery Point + REST Consumer + Queue Binding

Usage
-----
  # Set env vars first
  export SOLACE_API_TOKEN="<your-token>"
  export SOLACE_SERVICE_ID="<messaging-service-id>"

  python create_service.py --config config/dev/service.json
  python create_service.py --config config/prod/service.json --dry-run
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from solace_client   import SolaceClient, SolaceAPIError
from event_portal    import EventPortalManager
from cluster_manager import ClusterManager

# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Config loader ────────────────────────────────────────────────────────────
def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)
    with open(path) as f:
        cfg = json.load(f)
    logger.info("Loaded config: %s", config_path)
    return cfg


# ─── Phase 1: Event Portal Design ────────────────────────────────────────────
def provision_event_portal(ep: EventPortalManager, cfg: dict, dry_run: bool) -> dict:
    """
    Create all Event Portal design-time objects and return their IDs
    so Phase 2 can reference them.
    """
    svc   = cfg["service"]
    env   = cfg["environment"]
    ep_cfg = cfg["eventPortal"]

    logger.info("=" * 60)
    logger.info("PHASE 1 — Event Portal Design  [env=%s]", env)
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Would create EP objects for domain=%s", ep_cfg["domainName"])
        return {}

    ids: dict = {}

    # Step 1 — Application Domain
    logger.info("── Step 1: Application Domain ──────────────────────")
    domain = ep.get_or_create_domain(
        name        = ep_cfg["domainName"],
        description = ep_cfg.get("domainDescription", f"Domain for {svc['name']} ({env})")
    )
    ids["domainId"] = domain["id"]

    # Step 2 — Schema + SchemaVersion
    logger.info("── Step 2: Schema ──────────────────────────────────")
    schema_cfg = ep_cfg["schema"]
    schema = ep.create_schema(
        name      = schema_cfg["name"],
        domain_id = ids["domainId"],
        schema_type = schema_cfg.get("type", "jsonSchema"),
    )
    ids["schemaId"] = schema["id"]

    schema_version = ep.create_schema_version(
        schema_id   = ids["schemaId"],
        version     = schema_cfg.get("version", "1.0.0"),
        content     = json.dumps(schema_cfg["content"], indent=2),
        description = schema_cfg.get("description", ""),
    )
    ids["schemaVersionId"] = schema_version["id"]

    # Step 3 — Event + EventVersion
    logger.info("── Step 3: Event ───────────────────────────────────")
    event_cfg = ep_cfg["event"]
    event = ep.create_event(
        name      = event_cfg["name"],
        domain_id = ids["domainId"],
    )
    ids["eventId"] = event["id"]

    event_version = ep.create_event_version(
        event_id          = ids["eventId"],
        version           = event_cfg.get("version", "1.0.0"),
        topic             = event_cfg["topic"],
        schema_version_id = ids["schemaVersionId"],
        description       = event_cfg.get("description", ""),
    )
    ids["eventVersionId"] = event_version["id"]

    # Step 4 — Source Application (Publisher)
    logger.info("── Step 4: Source Application (Publisher) ──────────")
    src_cfg = ep_cfg["sourceApplication"]
    src_app = ep.create_application(
        name      = src_cfg["name"],
        domain_id = ids["domainId"],
    )
    ids["sourceAppId"] = src_app["id"]

    src_app_version = ep.create_application_version(
        app_id  = ids["sourceAppId"],
        version = src_cfg.get("version", "1.0.0"),
        declared_produced_event_version_ids = [ids["eventVersionId"]],
        description = src_cfg.get("description", ""),
    )
    ids["sourceAppVersionId"] = src_app_version["id"]

    # Step 5 — Target Application (Subscriber / Consumer)
    logger.info("── Step 5: Target Application (Consumer) ───────────")
    tgt_cfg = ep_cfg["targetApplication"]
    tgt_app = ep.create_application(
        name      = tgt_cfg["name"],
        domain_id = ids["domainId"],
    )
    ids["targetAppId"] = tgt_app["id"]

    tgt_app_version = ep.create_application_version(
        app_id  = ids["targetAppId"],
        version = tgt_cfg.get("version", "1.0.0"),
        declared_consumed_event_version_ids = [ids["eventVersionId"]],
        description = tgt_cfg.get("description", ""),
    )
    ids["targetAppVersionId"] = tgt_app_version["id"]

    logger.info("✓ Phase 1 complete — EP object IDs: %s", json.dumps(ids, indent=2))
    return ids


# ─── Phase 2: Cluster Management ─────────────────────────────────────────────
def provision_cluster(cm: ClusterManager, cfg: dict, ep_ids: dict, dry_run: bool) -> None:
    """
    Create all runtime Cluster Management Objects on the Solace broker.
    """
    env  = cfg["environment"]
    cl   = cfg["clusterManagement"]

    logger.info("=" * 60)
    logger.info("PHASE 2 — Cluster Management   [env=%s]", env)
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Would create Cluster objects in VPN=%s", cm.vpn_name)
        return

    # Step 6 — Client Profile
    logger.info("── Step 6: Client Profile ──────────────────────────")
    cm.create_client_profile(cl["clientProfile"]["name"])

    # Step 7 — ACL Profile
    logger.info("── Step 7: ACL Profile ─────────────────────────────")
    acl_cfg = cl["aclProfile"]
    cm.create_acl_profile(
        acl_name               = acl_cfg["name"],
        publish_default        = acl_cfg.get("publishDefault",   "allow"),
        subscribe_default      = acl_cfg.get("subscribeDefault", "allow"),
    )
    # Add topic-level exceptions if defined
    for topic in acl_cfg.get("publishExceptions", []):
        cm.add_publish_exception(acl_cfg["name"], topic)
    for topic in acl_cfg.get("subscribeExceptions", []):
        cm.add_subscribe_exception(acl_cfg["name"], topic)

    # Step 8 — Client Username (credentials)
    logger.info("── Step 8: Client Username ─────────────────────────")
    user_cfg = cl["clientUsername"]
    cm.create_client_username(
        username       = user_cfg["name"],
        password       = user_cfg["password"],
        client_profile = cl["clientProfile"]["name"],
        acl_profile    = acl_cfg["name"],
    )

    # Step 9 — Queue + Topic Subscriptions
    logger.info("── Step 9: Queue + Subscriptions ───────────────────")
    for q in cl.get("queues", []):
        cm.create_queue(
            queue_name   = q["name"],
            owner        = user_cfg["name"],
            access_type  = q.get("accessType", "non-exclusive"),
        )
        for topic in q.get("subscriptions", []):
            cm.add_queue_subscription(q["name"], topic)

    # Step 10 — REST Delivery Point
    logger.info("── Step 10: REST Delivery Point ────────────────────")
    rdp_cfg = cl.get("restDeliveryPoint")
    if rdp_cfg:
        cm.create_rest_delivery_point(rdp_name = rdp_cfg["name"])
        cm.create_rest_consumer(
            rdp_name      = rdp_cfg["name"],
            consumer_name = rdp_cfg["consumer"]["name"],
            host          = rdp_cfg["consumer"]["host"],
            port          = rdp_cfg["consumer"].get("port", 443),
            tls_enabled   = rdp_cfg["consumer"].get("tlsEnabled", True),
        )
        for q_name in rdp_cfg.get("queueBindings", []):
            cm.bind_queue_to_rdp(
                rdp_name   = rdp_cfg["name"],
                queue_name = q_name,
                post_request_target = rdp_cfg.get("postRequestTarget", "/"),
            )

    logger.info("✓ Phase 2 complete")


# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Solace Service Provisioner")
    parser.add_argument("--config",   required=True, help="Path to service config JSON")
    parser.add_argument("--dry-run",  action="store_true", help="Print plan without making API calls")
    parser.add_argument("--skip-ep",  action="store_true", help="Skip Event Portal phase (Phase 1)")
    parser.add_argument("--skip-cluster", action="store_true", help="Skip Cluster Management phase (Phase 2)")
    args = parser.parse_args()

    cfg = load_config(args.config)

    token          = os.environ.get("SOLACE_API_TOKEN")
    service_id     = os.environ.get("SOLACE_SERVICE_ID", cfg.get("serviceId", ""))
    vpn_name       = cfg.get("clusterManagement", {}).get("vpnName", "default")

    # SEMP credentials — from env or config (populated by discover_semp step)
    semp_base_url  = os.environ.get("SEMP_BASE_URL",  cfg.get("sempBaseUrl", ""))
    semp_username  = os.environ.get("SEMP_USERNAME",  cfg.get("sempUsername", ""))
    semp_password  = os.environ.get("SEMP_PASSWORD",  cfg.get("sempPassword", ""))

    if not token and not args.dry_run:
        logger.error("SOLACE_API_TOKEN environment variable is required")
        sys.exit(1)

    if not semp_base_url and not args.skip_cluster and not args.dry_run:
        logger.error("SEMP_BASE_URL is required for Phase 2. Set it via env var or config.")
        sys.exit(1)

    client = SolaceClient(
        token         = token or "dry-run-token",
        semp_base_url = semp_base_url,
        semp_username = semp_username,
        semp_password = semp_password,
    )
    ep     = EventPortalManager(client)
    cm     = ClusterManager(client, service_id=service_id, vpn_name=vpn_name)

    ep_ids = {}
    try:
        # Phase 1 — Event Portal
        if not args.skip_ep:
            ep_ids = provision_event_portal(ep, cfg, dry_run=args.dry_run)

        # Phase 2 — Cluster Management
        if not args.skip_cluster:
            provision_cluster(cm, cfg, ep_ids, dry_run=args.dry_run)

    except SolaceAPIError as e:
        logger.error("API Error: %s", e)
        sys.exit(1)

    logger.info("")
    logger.info("🎉 Solace service provisioning complete!")


if __name__ == "__main__":
    main()
