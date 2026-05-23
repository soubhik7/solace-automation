"""
src/workflows/exporter.py — Full Service Config Exporter
=========================================================
Snapshots all live Solace objects for one service (country) into a portable
JSON file that can be cloned to another country via Cloner.

Export covers:
  Phase 1  — Event Portal design objects
    • Application Domain
    • Schemas + Schema Versions   (content included)
    • Events + Event Versions     (topics reconstructed from addressLevels)
    • Applications + App Versions (produce/consume wired by event name)

  Phase 2  — Broker cluster objects (SEMP)
    • Client Profiles
    • ACL Profiles + publish/subscribe topic exceptions
    • Client Usernames            (passwords excluded — never export secrets)
    • Queues + topic subscriptions
    • REST Delivery Points + consumers + queue bindings

Usage
-----
    from workflows.exporter import Exporter
    exp = Exporter(ctx)
    data = exp.export(service_id="5yv0da6tr85",
                      domain_name="MarsAutomation-AU",
                      country_code="AU")
    exp.export_to_file("config/au/service.json",
                       service_id="5yv0da6tr85",
                       domain_name="MarsAutomation-AU",
                       country_code="AU")
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from client import SolaceClient
from context import Context
from api.cloud_svc    import CloudServiceAPI
from api.event_portal import EventPortalAPI
from api.semp         import SempAPI

logger = logging.getLogger(__name__)

# ── system objects that should never be cloned ─────────────────────────────────
_SKIP_PROFILES = {"default"}
_SKIP_ACLS     = {"default"}
_SKIP_USERS    = {"default", "solace-cloud-client"}
_SYS_PREFIX    = "#"


class Exporter:
    """
    Exports a full Solace service config (EP + cluster) to a portable dict / JSON.

    The exported JSON uses *name-based references* (not IDs) so that country
    substitution in Cloner works cleanly across all fields.
    """

    def __init__(self, ctx: Context):
        self.ctx    = ctx
        self.client = SolaceClient.from_context(ctx.as_dict())
        self.cloud  = CloudServiceAPI(self.client)
        self.ep     = EventPortalAPI(self.client)

    # ══════════════════════════════════════════════════════════════════════════
    def export(self,
               service_id:   str = None,
               domain_name:  str = None,
               country_code: str = None) -> dict:
        """
        Fetch and return a complete service config dict.

        Parameters
        ----------
        service_id   : Solace Cloud service ID (defaults to active context)
        domain_name  : EP domain name to export  (e.g. 'MarsAutomation-AU')
        country_code : Country code tag  (e.g. 'AU').
                       If domain_name is omitted, tries to find a domain whose
                       name contains this country code.
        """
        sid = service_id or self.ctx.service_id
        if not sid:
            raise ValueError(
                "No service ID — supply --id or run: python3 solace.py service use <id>")

        logger.info("═" * 60)
        logger.info("Exporting service %s  country=%s", sid, country_code or "(any)")
        logger.info("═" * 60)

        # 1. Service metadata + SEMP credentials
        logger.info("── Fetching service details ...")
        svc   = self.cloud.get_service(sid)
        creds = self.cloud.extract_semp_creds(svc)
        vpn   = creds["vpnName"]

        # 2. Build SEMP client scoped to this service's broker
        semp_client = SolaceClient(
            token     = self.ctx.token,
            semp_base = creds["sempBaseUrl"],
            semp_user = creds["sempUsername"],
            semp_pass = creds["sempPassword"],
        )
        semp = SempAPI(semp_client, vpn)

        # 3. Export cluster objects
        logger.info("── Exporting cluster objects  VPN=%s ...", vpn)
        cluster = self._export_cluster(semp, vpn)

        # 4. Export Event Portal objects
        logger.info("── Exporting Event Portal objects ...")
        ep_config = self._export_ep(domain_name=domain_name,
                                    country_code=country_code)

        result = {
            "exportedAt":    datetime.now(timezone.utc).isoformat(),
            "sourceCountry": (country_code or "").upper(),
            "environment":   "exported",
            "service": {
                "serviceId":     sid,
                "name":          svc.get("name", ""),
                "datacenterId":  svc.get("datacenterId", ""),
                "serviceTypeId":  svc.get("serviceTypeId",  ""),
                "serviceClassId": svc.get("serviceClassId", ""),
            },
            "eventPortal":       ep_config,
            "clusterManagement": cluster,
        }

        logger.info("")
        logger.info("✓ Export complete")
        logger.info("  schemas=%d  events=%d  apps=%d",
                    len(ep_config.get("schemas", [])),
                    len(ep_config.get("events", [])),
                    len(ep_config.get("applications", [])))
        logger.info("  profiles=%d  acls=%d  users=%d  queues=%d  rdps=%d",
                    len(cluster.get("clientProfiles", [])),
                    len(cluster.get("aclProfiles", [])),
                    len(cluster.get("clientUsernames", [])),
                    len(cluster.get("queues", [])),
                    len(cluster.get("restDeliveryPoints", [])))
        return result

    def export_to_file(self, output_path: str, **kwargs) -> dict:
        """Export and write JSON to *output_path*. Returns the config dict."""
        data = self.export(**kwargs)
        out  = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2))
        logger.info("✓ Written → %s", output_path)
        return data

    # ══════════════════════════════════════════════════════════════════════════
    # CLUSTER (SEMP)
    # ══════════════════════════════════════════════════════════════════════════
    def _export_cluster(self, semp: SempAPI, vpn: str) -> dict:

        # ── Client Profiles ────────────────────────────────────────────────
        profiles = []
        for p in semp.list_client_profiles():
            name = p["clientProfileName"]
            if name in _SKIP_PROFILES or name.startswith(_SYS_PREFIX):
                continue
            profiles.append({"name": name})
        logger.info("  client profiles  : %d", len(profiles))

        # ── ACL Profiles + topic exceptions ───────────────────────────────
        acl_profiles = []
        for a in semp.list_acl_profiles():
            name = a["aclProfileName"]
            if name in _SKIP_ACLS or name.startswith(_SYS_PREFIX):
                continue

            pub_exc = [
                e.get("publishTopicException", "")
                for e in semp.list_publish_exceptions(name)
            ]
            sub_exc = [
                e.get("subscribeTopicException", "")
                for e in semp.list_subscribe_exceptions(name)
            ]
            acl_profiles.append({
                "name":                name,
                "publishDefault":      a.get("publishTopicDefaultAction",   "disallow"),
                "subscribeDefault":    a.get("subscribeTopicDefaultAction",  "disallow"),
                "publishExceptions":   [t for t in pub_exc if t],
                "subscribeExceptions": [t for t in sub_exc if t],
            })
        logger.info("  ACL profiles     : %d", len(acl_profiles))

        # ── Client Usernames (passwords excluded) ─────────────────────────
        usernames = []
        for u in semp.list_client_usernames():
            name = u["clientUsername"]
            if name in _SKIP_USERS or name.startswith(_SYS_PREFIX):
                continue
            usernames.append({
                "name":          name,
                "password":      "",   # NEVER export passwords
                "clientProfile": u.get("clientProfileName", "default"),
                "aclProfile":    u.get("aclProfileName",    "default"),
                "enabled":       u.get("enabled", True),
            })
        logger.info("  client usernames : %d", len(usernames))

        # ── Queues + topic subscriptions ──────────────────────────────────
        queues = []
        for q in semp.list_queues():
            name = q["queueName"]
            if name.startswith(_SYS_PREFIX):
                continue
            subs = [
                s.get("subscriptionTopic", "")
                for s in semp.list_queue_subscriptions(name)
            ]
            queues.append({
                "name":          name,
                "accessType":    q.get("accessType",   "non-exclusive"),
                "owner":         q.get("owner",        ""),
                "subscriptions": [t for t in subs if t],
            })
        logger.info("  queues           : %d", len(queues))

        # ── REST Delivery Points + consumers + bindings ───────────────────
        rdps = []
        for r in semp.list_rdps():
            rdp_name = r["restDeliveryPointName"]
            if rdp_name.startswith(_SYS_PREFIX):
                continue

            consumers = []
            for c in semp.list_rest_consumers(rdp_name):
                consumers.append({
                    "name":       c.get("restConsumerName", ""),
                    "host":       c.get("remoteHost",       ""),
                    "port":       c.get("remotePort",       443),
                    "tlsEnabled": c.get("tlsEnabled",       True),
                    "httpMethod": c.get("httpMethod",       "post"),
                })

            bindings = [
                b.get("queueBindingName", "")
                for b in semp.list_queue_bindings(rdp_name)
            ]

            # Grab postRequestTarget from first binding if present
            post_target = "/"
            raw_bindings = semp.list_queue_bindings(rdp_name)
            if raw_bindings:
                post_target = raw_bindings[0].get("postRequestTarget", "/")

            rdps.append({
                "name":              rdp_name,
                "clientProfile":     r.get("clientProfileName", "default"),
                "enabled":           r.get("enabled", True),
                "postRequestTarget": post_target,
                "consumers":         consumers,
                "queueBindings":     [b for b in bindings if b],
            })
        logger.info("  RDPs             : %d", len(rdps))

        return {
            "vpnName":            vpn,   # replaced at provision time for new service
            "clientProfiles":     profiles,
            "aclProfiles":        acl_profiles,
            "clientUsernames":    usernames,
            "queues":             queues,
            "restDeliveryPoints": rdps,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # EVENT PORTAL
    # ══════════════════════════════════════════════════════════════════════════
    def _export_ep(self,
                   domain_name:  str = None,
                   country_code: str = None) -> dict:
        """Export EP objects. References are name-based (not ID) for portability."""

        domain = self._resolve_domain(domain_name, country_code)
        if not domain:
            return {
                "domainName":        domain_name or f"Domain-{country_code or 'UNKNOWN'}",
                "domainDescription": "",
                "schemas":           [],
                "events":            [],
                "applications":      [],
            }

        domain_id = domain["id"]
        logger.info("  EP domain: '%s' (id=%s)", domain["name"], domain_id)

        # ── Schemas ────────────────────────────────────────────────────────
        # Use a dict keyed by schema name so we keep only the latest version
        schemas_dict: dict[str, dict] = {}
        schema_name_to_ver_id: dict[str, str] = {}   # for event linking

        for s in self.ep.list_schemas(domain_id=domain_id):
            versions = self.ep.list_schema_versions(schema_id=s["id"])
            if not versions:
                continue
            # Last version = most recently created
            sv = versions[-1]
            content = sv.get("content", "")
            try:
                content_parsed = json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                content_parsed = content or {}

            schemas_dict[s["name"]] = {
                "name":        s["name"],
                "type":        s.get("schemaType", "jsonSchema"),
                "version":     sv.get("version", "1.0.0"),
                "description": sv.get("description", ""),
                "content":     content_parsed,
            }
            schema_name_to_ver_id[s["name"]] = sv["id"]

        schemas_out = list(schemas_dict.values())
        logger.info("  schemas          : %d", len(schemas_out))

        # ── Events ────────────────────────────────────────────────────────
        # Use dict keyed by event name → keep latest version only
        events_dict: dict[str, dict] = {}
        event_name_to_ver_id: dict[str, str] = {}   # for app linking

        for e in self.ep.list_events(domain_id=domain_id):
            versions = self.ep.list_event_versions(event_id=e["id"])
            if not versions:
                continue
            # Prefer the version with a valid topic; otherwise take last
            ev = next((v for v in reversed(versions) if self._reconstruct_topic(v)),
                      versions[-1])
            topic = self._reconstruct_topic(ev)

            # Reverse-map schemaVersionId → schema name
            sv_id = ev.get("schemaVersionId", "")
            schema_ref = next(
                (n for n, vid in schema_name_to_ver_id.items() if vid == sv_id),
                ""
            )

            events_dict[e["name"]] = {
                "name":        e["name"],
                "version":     ev.get("version", "1.0.0"),
                "description": ev.get("description", ""),
                "topic":       topic,
                "schemaRef":   schema_ref,  # name, resolved at provision time
            }
            event_name_to_ver_id[e["name"]] = ev["id"]

        events_out = list(events_dict.values())
        logger.info("  events           : %d", len(events_out))

        # ── Applications ──────────────────────────────────────────────────
        # Use dict keyed by app name → keep latest version only
        apps_dict: dict[str, dict] = {}

        for a in self.ep.list_applications(domain_id=domain_id):
            versions = self.ep.list_application_versions(app_id=a["id"])
            if not versions:
                continue
            av = versions[-1]   # latest version
            produced_ids = av.get("declaredProducedEventVersionIds", [])
            consumed_ids = av.get("declaredConsumedEventVersionIds", [])

            produces_names = [
                n for n, vid in event_name_to_ver_id.items() if vid in produced_ids
            ]
            consumes_names = [
                n for n, vid in event_name_to_ver_id.items() if vid in consumed_ids
            ]

            apps_dict[a["name"]] = {
                "name":        a["name"],
                "type":        a.get("applicationType", "standard"),
                "version":     av.get("version", "1.0.0"),
                "description": av.get("description", ""),
                "produces":    produces_names,
                "consumes":    consumes_names,
            }

        apps_out = list(apps_dict.values())
        logger.info("  applications     : %d", len(apps_out))

        return {
            "domainName":        domain["name"],
            "domainDescription": domain.get("description", ""),
            "schemas":           schemas_out,
            "events":            events_out,
            "applications":      apps_out,
        }

    # ── helpers ────────────────────────────────────────────────────────────────
    def _resolve_domain(self, domain_name: str, country_code: str):
        if domain_name:
            d = self.ep.find_domain(domain_name)
            if not d:
                logger.warning("  Domain '%s' not found — EP section will be empty", domain_name)
            return d

        if country_code:
            code = country_code.upper()
            matches = [d for d in self.ep.list_domains()
                       if code in d["name"].upper()]
            if matches:
                logger.info("  Auto-found domain '%s' for country=%s",
                            matches[0]["name"], code)
                return matches[0]
            logger.warning("  No domain found matching country code '%s'", code)
            return None

        logger.info("  No domain_name or country_code given — skipping EP export")
        return None

    @staticmethod
    def _reconstruct_topic(event_version: dict) -> str:
        """Rebuild 'mars/orders/{orderId}/created' from address level array."""
        try:
            levels = (event_version
                      .get("deliveryDescriptor", {})
                      .get("address", {})
                      .get("addressLevels", []))
            parts = []
            for lvl in levels:
                n = lvl.get("name", "")
                if lvl.get("addressLevelType") == "variable":
                    parts.append(f"{{{n}}}")
                else:
                    parts.append(n)
            return "/".join(parts)
        except Exception:
            return ""
