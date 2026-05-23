"""
src/workflows/provision.py — Full Orchestration Workflow
=========================================================
Reads a service config (JSON) and runs the complete provisioning pipeline.

Supports two config formats (both handled automatically):

  ── Legacy (single-object, backward compatible) ──────────────────────────
  eventPortal:
    schema           : single schema dict
    event            : single event dict
    sourceApplication: single app dict (producer)
    targetApplication: single app dict (consumer)

  clusterManagement:
    clientProfile    : single profile dict
    aclProfile       : single ACL dict
    clientUsername   : single username dict
    queues           : list of queue dicts  (always a list)
    restDeliveryPoint: single RDP dict

  ── Extended (multi-object, from Exporter/Cloner) ────────────────────────
  eventPortal:
    schemas          : list of schema dicts  (name-based schema refs)
    events           : list of event dicts   (schemaRef = schema name)
    applications     : list of app dicts     (produces/consumes = event names)

  clusterManagement:
    clientProfiles   : list of profile dicts
    aclProfiles      : list of ACL dicts (with publishExceptions[] & subscribeExceptions[])
    clientUsernames  : list of username dicts
    queues           : list of queue dicts
    restDeliveryPoints: list of RDP dicts (consumers[] + queueBindings[])

Phases
------
  Phase 1 — Event Portal Design
  Phase 2 — Cluster Management (broker runtime)
"""

from __future__ import annotations
import json
import logging
from pathlib import Path

from client import SolaceClient, SolaceError
from api.event_portal import EventPortalAPI
from api.semp import SempAPI
from api.cloud_svc import CloudServiceAPI
from context import Context

logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(p.read_text())


class Provisioner:
    """
    Orchestrates full Solace service provisioning from a JSON config.

    Usage
    -----
        ctx = Context.load()
        p   = Provisioner(ctx, dry_run=False)
        p.run("config/au/service.json")
    """

    def __init__(self, ctx: Context, dry_run: bool = False):
        self.ctx     = ctx
        self.dry_run = dry_run
        self.client  = SolaceClient.from_context(ctx.as_dict())
        self.ep      = EventPortalAPI(self.client)
        self._cloud  = CloudServiceAPI(self.client)

    def _semp(self, vpn: str) -> SempAPI:
        return SempAPI(self.client, vpn)

    # ──────────────────────────────────────────────────────────────────────────
    def run(self, config_path: str,
            skip_ep: bool = False,
            skip_cluster: bool = False) -> dict:
        """Top-level: load config and run both phases."""
        cfg = load_config(config_path)
        env = cfg.get("environment", "unknown")
        logger.info("=" * 60)
        logger.info("Provisioning  env=%s  dry_run=%s", env, self.dry_run)
        logger.info("=" * 60)

        ep_ids: dict = {}
        if not skip_ep:
            ep_ids = self.provision_event_portal(cfg)

        if not skip_cluster:
            self.provision_cluster(cfg, ep_ids)

        logger.info("")
        logger.info("🎉  Provisioning complete!")
        return ep_ids

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1 — EVENT PORTAL
    # ══════════════════════════════════════════════════════════════════════════
    def provision_event_portal(self, cfg: dict) -> dict:
        ep_cfg = cfg.get("eventPortal", {})
        ids: dict = {}

        logger.info("── Phase 1: Event Portal ─────────────────────────────")

        if self.dry_run:
            logger.info("  [DRY-RUN] Would create EP objects  domain=%s",
                        ep_cfg.get("domainName", "?"))
            return {}

        # Domain (always needed)
        domain = self.ep.get_or_create_domain(
            name        = ep_cfg["domainName"],
            description = ep_cfg.get("domainDescription", ""),
        )
        ids["domainId"] = domain["id"]

        # Choose format
        if "schemas" in ep_cfg:
            self._provision_ep_multi(ep_cfg, ids)
        else:
            self._provision_ep_single(ep_cfg, ids)

        logger.info("  ✓ Phase 1 complete  keys=%s", list(ids.keys()))
        return ids

    # ── Extended multi-object format ──────────────────────────────────────────
    def _provision_ep_multi(self, ep_cfg: dict, ids: dict) -> None:
        """
        Handle:
          schemas[]       — list of schema dicts (name, type, version, content)
          events[]        — list of event dicts  (name, version, topic, schemaRef)
          applications[]  — list of app dicts    (name, version, produces[], consumes[])

        References use names (not IDs) so they survive country substitution.
        """
        domain_id = ids["domainId"]

        # ── Schemas → track name: schema_version_id ────────────────────────
        schema_ver_map: dict[str, str] = {}   # schema_name → schema_version_id

        for sc in ep_cfg.get("schemas", []):
            s = self.ep.get_or_create_schema(
                name        = sc["name"],
                domain_id   = domain_id,
                schema_type = sc.get("type", "jsonSchema"),
            )
            # Only create a new version if schema was just created (no versions yet)
            existing_versions = self.ep.list_schema_versions(schema_id=s["id"])
            if existing_versions:
                sv = existing_versions[-1]
                logger.info("  Using existing schema version id=%s", sv["id"])
            else:
                content = sc.get("content", {})
                sv = self.ep.create_schema_version(
                    schema_id   = s["id"],
                    version     = sc.get("version", "1.0.0"),
                    content     = json.dumps(content) if isinstance(content, dict) else content,
                    description = sc.get("description", ""),
                )
            schema_ver_map[sc["name"]] = sv["id"]
            ids[f"schemaVersionId_{sc['name']}"] = sv["id"]

        # ── Events → track name: event_version_id ─────────────────────────
        event_ver_map: dict[str, str] = {}   # event_name → event_version_id

        for ev_cfg in ep_cfg.get("events", []):
            e = self.ep.get_or_create_event(
                name        = ev_cfg["name"],
                domain_id   = domain_id,
                description = ev_cfg.get("description", ""),
            )
            existing_ev_versions = self.ep.list_event_versions(event_id=e["id"])
            if existing_ev_versions:
                ev = existing_ev_versions[-1]
                logger.info("  Using existing event version id=%s", ev["id"])
            else:
                schema_ver_id = schema_ver_map.get(ev_cfg.get("schemaRef", ""))
                ev = self.ep.create_event_version(
                    event_id          = e["id"],
                    version           = ev_cfg.get("version", "1.0.0"),
                    topic             = ev_cfg["topic"],
                    schema_version_id = schema_ver_id,
                    description       = ev_cfg.get("description", ""),
                )
            event_ver_map[ev_cfg["name"]] = ev["id"]
            ids[f"eventVersionId_{ev_cfg['name']}"] = ev["id"]

        # ── Applications ──────────────────────────────────────────────────
        for app_cfg in ep_cfg.get("applications", []):
            a = self.ep.get_or_create_application(
                name        = app_cfg["name"],
                domain_id   = domain_id,
                app_type    = app_cfg.get("type", "standard"),
                description = app_cfg.get("description", ""),
            )
            existing_av = self.ep.list_application_versions(app_id=a["id"])
            if existing_av:
                av = existing_av[-1]
                logger.info("  Using existing app version id=%s", av["id"])
            else:
                produces = [event_ver_map[n] for n in app_cfg.get("produces", [])
                            if n in event_ver_map]
                consumes = [event_ver_map[n] for n in app_cfg.get("consumes", [])
                            if n in event_ver_map]
                av = self.ep.create_application_version(
                    app_id      = a["id"],
                    version     = app_cfg.get("version", "1.0.0"),
                    produces    = produces,
                    consumes    = consumes,
                    description = app_cfg.get("description", ""),
                )
            ids[f"appVersionId_{app_cfg['name']}"] = av["id"]

    # ── Legacy single-object format (backward compatible) ─────────────────────
    def _provision_ep_single(self, ep_cfg: dict, ids: dict) -> None:
        domain_id = ids["domainId"]

        # Schema
        sc_cfg = ep_cfg.get("schema", {})
        if sc_cfg:
            s = self.ep.create_schema(
                name        = sc_cfg["name"],
                domain_id   = domain_id,
                schema_type = sc_cfg.get("type", "jsonSchema"),
            )
            ids["schemaId"] = s["id"]
            content = sc_cfg.get("content", {})
            sv = self.ep.create_schema_version(
                schema_id   = ids["schemaId"],
                version     = sc_cfg.get("version", "1.0.0"),
                content     = json.dumps(content) if isinstance(content, dict) else content,
                description = sc_cfg.get("description", ""),
            )
            ids["schemaVersionId"] = sv["id"]

        # Event
        ev_cfg = ep_cfg.get("event", {})
        if ev_cfg:
            e = self.ep.create_event(
                name      = ev_cfg["name"],
                domain_id = domain_id,
            )
            ids["eventId"] = e["id"]
            evv = self.ep.create_event_version(
                event_id          = ids["eventId"],
                version           = ev_cfg.get("version", "1.0.0"),
                topic             = ev_cfg["topic"],
                schema_version_id = ids.get("schemaVersionId"),
                description       = ev_cfg.get("description", ""),
            )
            ids["eventVersionId"] = evv["id"]

        # Source Application
        src = ep_cfg.get("sourceApplication", {})
        if src:
            src_app = self.ep.create_application(
                name      = src["name"],
                domain_id = domain_id,
            )
            ids["sourceAppId"] = src_app["id"]
            src_ver = self.ep.create_application_version(
                app_id      = ids["sourceAppId"],
                version     = src.get("version", "1.0.0"),
                produces    = [ids["eventVersionId"]] if "eventVersionId" in ids else [],
                description = src.get("description", ""),
            )
            ids["sourceAppVersionId"] = src_ver["id"]

        # Target Application
        tgt = ep_cfg.get("targetApplication", {})
        if tgt:
            tgt_app = self.ep.create_application(
                name      = tgt["name"],
                domain_id = domain_id,
            )
            ids["targetAppId"] = tgt_app["id"]
            tgt_ver = self.ep.create_application_version(
                app_id      = ids["targetAppId"],
                version     = tgt.get("version", "1.0.0"),
                consumes    = [ids["eventVersionId"]] if "eventVersionId" in ids else [],
                description = tgt.get("description", ""),
            )
            ids["targetAppVersionId"] = tgt_ver["id"]

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2 — CLUSTER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════
    def provision_cluster(self, cfg: dict, ep_ids: dict = None) -> None:
        cl  = cfg.get("clusterManagement", {})
        vpn = cl.get("vpnName") or self.ctx.vpn_name
        semp = self._semp(vpn)

        logger.info("── Phase 2: Cluster Management  VPN=%s ───────────────", vpn)

        if self.dry_run:
            logger.info("  [DRY-RUN] Would create cluster objects in VPN=%s", vpn)
            return

        # Choose format: multi-object or legacy single-object
        if "clientProfiles" in cl:
            self._provision_cluster_multi(cl, semp)
        else:
            self._provision_cluster_single(cl, semp)

        logger.info("  ✓ Phase 2 complete")

    # ── Extended multi-object format ──────────────────────────────────────────
    def _provision_cluster_multi(self, cl: dict, semp: SempAPI) -> None:
        """
        Handle:
          clientProfiles[]     — list of {name}
          aclProfiles[]        — list of {name, publishDefault, subscribeDefault,
                                          publishExceptions[], subscribeExceptions[]}
          clientUsernames[]    — list of {name, password, clientProfile, aclProfile}
          queues[]             — list of {name, accessType, subscriptions[]}
          restDeliveryPoints[] — list of {name, consumers[], queueBindings[],
                                          postRequestTarget}
        """

        # Client Profiles
        for p in cl.get("clientProfiles", []):
            semp.create_client_profile(p["name"])

        # ACL Profiles + exceptions
        for a in cl.get("aclProfiles", []):
            semp.create_acl_profile(
                name              = a["name"],
                publish_default   = a.get("publishDefault",   "disallow"),
                subscribe_default = a.get("subscribeDefault", "disallow"),
            )
            for t in a.get("publishExceptions", []):
                semp.add_publish_exception(a["name"], t)
            for t in a.get("subscribeExceptions", []):
                semp.add_subscribe_exception(a["name"], t)

        # Client Usernames
        for u in cl.get("clientUsernames", []):
            semp.create_client_username(
                name           = u["name"],
                password       = u.get("password", ""),
                client_profile = u.get("clientProfile", "default"),
                acl_profile    = u.get("aclProfile", "default"),
            )

        # Queues + subscriptions
        for q in cl.get("queues", []):
            semp.create_queue(
                name        = q["name"],
                owner       = q.get("owner") or None,
                access_type = q.get("accessType", "non-exclusive"),
            )
            for topic in q.get("subscriptions", []):
                semp.add_queue_subscription(q["name"], topic)

        # REST Delivery Points
        for rdp_cfg in cl.get("restDeliveryPoints", []):
            semp.create_rdp(
                name           = rdp_cfg["name"],
                client_profile = rdp_cfg.get("clientProfile", "default"),
            )
            post_target = rdp_cfg.get("postRequestTarget", "/")
            for con in rdp_cfg.get("consumers", []):
                semp.create_rest_consumer(
                    rdp        = rdp_cfg["name"],
                    name       = con["name"],
                    host       = con["host"],
                    port       = con.get("port", 443),
                    tls        = con.get("tlsEnabled", True),
                    http_method= con.get("httpMethod", "post"),
                )
            for q_name in rdp_cfg.get("queueBindings", []):
                semp.bind_queue_to_rdp(
                    rdp         = rdp_cfg["name"],
                    queue       = q_name,
                    post_target = post_target,
                )

    # ── Legacy single-object format (backward compatible) ─────────────────────
    def _provision_cluster_single(self, cl: dict, semp: SempAPI) -> None:
        # Client Profile
        cp = cl.get("clientProfile", {})
        if cp:
            semp.create_client_profile(cp["name"])

        # ACL Profile + exceptions
        acl = cl.get("aclProfile", {})
        if acl:
            semp.create_acl_profile(
                name              = acl["name"],
                publish_default   = acl.get("publishDefault",   "disallow"),
                subscribe_default = acl.get("subscribeDefault", "disallow"),
            )
            for t in acl.get("publishExceptions", []):
                semp.add_publish_exception(acl["name"], t)
            for t in acl.get("subscribeExceptions", []):
                semp.add_subscribe_exception(acl["name"], t)

        # Client Username
        u = cl.get("clientUsername", {})
        if u:
            semp.create_client_username(
                name           = u["name"],
                password       = u.get("password", ""),
                client_profile = cp.get("name", "default") if cp else "default",
                acl_profile    = acl.get("name", "default") if acl else "default",
            )

        # Queues + subscriptions
        uname = u.get("name") if u else None
        for q in cl.get("queues", []):
            semp.create_queue(
                name        = q["name"],
                owner       = q.get("owner") or uname,
                access_type = q.get("accessType", "non-exclusive"),
            )
            for topic in q.get("subscriptions", []):
                semp.add_queue_subscription(q["name"], topic)

        # REST Delivery Point
        rdp_cfg = cl.get("restDeliveryPoint")
        if rdp_cfg:
            semp.create_rdp(rdp_cfg["name"])
            con = rdp_cfg["consumer"]
            semp.create_rest_consumer(
                rdp  = rdp_cfg["name"],
                name = con["name"],
                host = con["host"],
                port = con.get("port", 443),
                tls  = con.get("tlsEnabled", True),
            )
            for q_name in rdp_cfg.get("queueBindings", []):
                semp.bind_queue_to_rdp(
                    rdp         = rdp_cfg["name"],
                    queue       = q_name,
                    post_target = rdp_cfg.get("postRequestTarget", "/"),
                )
