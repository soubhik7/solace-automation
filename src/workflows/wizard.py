"""
src/workflows/wizard.py — Interactive Guided Wizard
=====================================================
Covers BOTH automation requirements without the user needing to know any flags:

  Flow 1 — Create new integration from scratch
    Walks the user through every object interactively:
    Service → EP Domain → Schemas → Events → Applications
             → Client Profile → ACL → Username → Queues → RDP

  Flow 2 — Clone existing country + guided customisation
    1. Export source country's live config
    2. Show what will change (clone diff)
    3. Let user review and override key fields interactively
       (domain name, topic prefix, REST host, extra queues, passwords)
    4. Confirm and provision

Usage
-----
    python solace.py wizard
    python solace.py wizard --flow 1      # jump straight to create-from-scratch
    python solace.py wizard --flow 2      # jump straight to clone
"""

from __future__ import annotations
import json
import logging
import sys
import secrets
import string
from pathlib import Path
from typing import Optional

from client      import SolaceClient
from context     import Context
from api.cloud_svc    import CloudServiceAPI
from api.event_portal import EventPortalAPI
from api.semp         import SempAPI
from workflows.exporter  import Exporter
from workflows.cloner    import Cloner
from workflows.provision import Provisioner

logger = logging.getLogger(__name__)

# ── ANSI colours (gracefully disabled on non-TTY) ─────────────────────────────
_TTY = sys.stdout.isatty()
def _c(code, text): return f"\033[{code}m{text}\033[0m" if _TTY else text
def bold(t):   return _c("1",    t)
def cyan(t):   return _c("96",   t)
def green(t):  return _c("92",   t)
def yellow(t): return _c("93",   t)
def dim(t):    return _c("2",    t)
def red(t):    return _c("91",   t)


class InteractiveWizard:
    """
    Fully interactive guided wizard.  No Solace knowledge required from the user.
    """

    def __init__(self, ctx: Context):
        self.ctx    = ctx
        self.client = SolaceClient.from_context(ctx.as_dict())
        self.cloud  = CloudServiceAPI(self.client)
        self.ep     = EventPortalAPI(self.client)

    # ══════════════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════════
    def run(self, force_flow: int = None):
        self._banner()
        flow = force_flow or self._ask_main_menu()
        try:
            if   flow == 1: self._flow_create_from_scratch()
            elif flow == 2: self._flow_clone_country()
            elif flow == 3: self._flow_ep_only()
            elif flow == 4: self._flow_cluster_only()
        except KeyboardInterrupt:
            print(f"\n\n{yellow('Aborted by user.')}\n")
            sys.exit(0)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 1 — CREATE FROM SCRATCH
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_create_from_scratch(self):
        self._section("Flow 1 — Create New Integration From Scratch")

        # ── Service ──────────────────────────────────────────────────────────
        self._header("Step 1 / 6  —  Messaging Service")

        use_existing = self._ask_yn(
            "Use the already-active service in context?",
            default = bool(self.ctx.service_id),
        )
        service_id = self.ctx.service_id
        vpn_name   = self.ctx.vpn_name

        if not use_existing:
            print(f"\n  {dim('Available datacenters:')}")
            dcs = self.cloud.list_datacenters()
            for d in dcs[:12]:
                print(f"    {d['id']:<30} {d.get('displayName','')}")
            print()
            svc_name   = self._ask("Service name",   "mars-automation")
            datacenter = self._ask("Datacenter ID",  "aks-centralus")
            svc_type   = self._ask("Service type ID (developer / enterprise)",  "developer")
            svc_class  = self._ask("Service class ID (developer / enterprise-kilo ...)", "developer")

            print(f"\n  {yellow('Creating service…')}")
            svc = self.cloud.create_service(
                name=svc_name, service_type=svc_type,
                service_class=svc_class, datacenter=datacenter,
            )
            service_id = svc["serviceId"]
            print(f"  serviceId={service_id}  state={svc.get('creationState')}")
            print(f"  {yellow('Waiting for service to be ready (this may take ~1 min)…')}")
            svc    = self.cloud.wait_for_service(service_id)
            creds  = self.cloud.extract_semp_creds(svc)
            vpn_name = creds["vpnName"]
            self.ctx.set_service(
                service_id=service_id, vpn_name=vpn_name,
                semp_base=creds["sempBaseUrl"],
                semp_user=creds["sempUsername"],
                semp_pass=creds["sempPassword"],
            )
            self.ctx.save()
            self.client = SolaceClient.from_context(self.ctx.as_dict())
            print(f"  {green('✓ Service ready')}  VPN={vpn_name}")

        # ── EP Domain ────────────────────────────────────────────────────────
        self._header("Step 2 / 6  —  Event Portal Domain")
        domain_name = self._ask("Application domain name", "MarsAutomation")
        domain_desc = self._ask("Domain description",      "", required=False)
        domain = EventPortalAPI(self.client).get_or_create_domain(domain_name, domain_desc)
        domain_id = domain["id"]
        print(f"  {green('✓')} Domain '{domain_name}'  id={domain_id}")

        # ── Schemas ──────────────────────────────────────────────────────────
        self._header("Step 3 / 6  —  Schemas")
        schemas = []     # [{name, type, version, content, description}]
        schema_ver_map: dict[str,str] = {}   # name → schemaVersionId

        while self._ask_yn("Add a schema?", default=True):
            s_name    = self._ask("  Schema name",    "OrderPayloadSchema")
            s_type    = self._ask("  Schema type (jsonSchema / avro / protobuf)", "jsonSchema")
            s_ver     = self._ask("  Version",         "1.0.0")
            s_desc    = self._ask("  Description",     "", required=False)
            s_file    = self._ask("  Schema content file path (or Enter to use empty)", "", required=False)
            s_content = "{}"
            if s_file and Path(s_file).exists():
                s_content = Path(s_file).read_text()
                print(f"  {green('✓')} Loaded schema from {s_file}")
            elif s_file:
                print(f"  {yellow('File not found — using empty schema')} {{}}")

            ep = EventPortalAPI(self.client)
            s  = ep.get_or_create_schema(s_name, domain_id, s_type)
            existing = ep.list_schema_versions(schema_id=s["id"])
            if existing:
                sv = existing[-1]
                print(f"  {green('✓')} Using existing schema version id={sv['id']}")
            else:
                sv = ep.create_schema_version(s["id"], s_ver, s_content, s_desc)
            schema_ver_map[s_name] = sv["id"]
            schemas.append({"name": s_name, "versionId": sv["id"]})
            print(f"  {green('✓')} Schema '{s_name}'  version_id={sv['id']}")

        # ── Events ───────────────────────────────────────────────────────────
        self._header("Step 4 / 6  —  Events")
        events = []
        event_ver_map: dict[str,str] = {}

        while self._ask_yn("Add an event?", default=True):
            e_name  = self._ask("  Event name",  "OrderCreated")
            e_topic = self._ask("  Topic string (use {var} for wildcards)",
                                "mars/orders/{orderId}/created")
            e_ver   = self._ask("  Version",     "1.0.0")
            e_desc  = self._ask("  Description", "", required=False)

            # Link to schema?
            e_schema_ver_id = None
            if schema_ver_map:
                link_schema = self._ask_yn(
                    f"  Link to a schema? (available: {list(schema_ver_map.keys())})",
                    default=True,
                )
                if link_schema:
                    if len(schema_ver_map) == 1:
                        e_schema_ver_id = next(iter(schema_ver_map.values()))
                        print(f"    → using '{next(iter(schema_ver_map.keys()))}'")
                    else:
                        schema_name = self._ask(
                            f"  Which schema? ({', '.join(schema_ver_map.keys())})",
                            next(iter(schema_ver_map.keys())),
                        )
                        e_schema_ver_id = schema_ver_map.get(schema_name)

            ep = EventPortalAPI(self.client)
            e  = ep.get_or_create_event(e_name, domain_id, e_desc)
            existing_ev = ep.list_event_versions(event_id=e["id"])
            if existing_ev:
                ev = existing_ev[-1]
                print(f"  {green('✓')} Using existing event version id={ev['id']}")
            else:
                ev = ep.create_event_version(
                    event_id=e["id"], version=e_ver, topic=e_topic,
                    schema_version_id=e_schema_ver_id, description=e_desc,
                )
            event_ver_map[e_name] = ev["id"]
            events.append({"name": e_name, "versionId": ev["id"]})
            print(f"  {green('✓')} Event '{e_name}'  topic={e_topic}  version_id={ev['id']}")

        # ── Applications ─────────────────────────────────────────────────────
        self._header("Step 5 / 6  —  Applications")
        apps = []
        all_event_names = list(event_ver_map.keys())

        while self._ask_yn("Add an application?", default=True):
            a_name = self._ask("  Application name", "MarsSourceSystem")
            a_desc = self._ask("  Description",      "", required=False)
            a_ver  = self._ask("  Version",          "1.0.0")

            produces = []
            consumes = []
            if all_event_names:
                print(f"  Available events: {all_event_names}")
                if self._ask_yn("  Does this app PUBLISH (produce) events?", default=True):
                    print("  Which events does it publish? (Enter name, blank to finish)")
                    produces = self._ask_from_list(all_event_names, "Produces event")
                if self._ask_yn("  Does this app SUBSCRIBE (consume) events?", default=False):
                    print("  Which events does it consume?")
                    consumes = self._ask_from_list(all_event_names, "Consumes event")

            ep = EventPortalAPI(self.client)
            a  = ep.get_or_create_application(a_name, domain_id, description=a_desc)
            existing_av = ep.list_application_versions(app_id=a["id"])
            if existing_av:
                av = existing_av[-1]
                print(f"  {green('✓')} Using existing app version id={av['id']}")
            else:
                av = ep.create_application_version(
                    app_id=a["id"], version=a_ver,
                    produces=[event_ver_map[n] for n in produces if n in event_ver_map],
                    consumes=[event_ver_map[n] for n in consumes if n in event_ver_map],
                    description=a_desc,
                )
            apps.append({"name": a_name, "versionId": av["id"]})
            print(f"  {green('✓')} App '{a_name}'  produces={produces}  consumes={consumes}")

        # ── Cluster Objects ──────────────────────────────────────────────────
        self._header("Step 6 / 6  —  Cluster / Broker Objects")
        semp = SempAPI(self.client, vpn_name)

        # Client profile
        profile_name = None
        if self._ask_yn("Create a Client Profile?", default=True):
            profile_name = self._ask("  Profile name", "mars-profile")
            semp.create_client_profile(profile_name)
            print(f"  {green('✓')} Client profile '{profile_name}' created")

        # ACL profile
        acl_name = None
        if self._ask_yn("Create an ACL Profile?", default=True):
            acl_name     = self._ask("  ACL name",             "mars-acl")
            pub_default  = self._ask("  Publish default (allow / disallow)", "disallow")
            sub_default  = self._ask("  Subscribe default (allow / disallow)", "disallow")
            semp.create_acl_profile(acl_name, publish_default=pub_default,
                                    subscribe_default=sub_default)
            print(f"  {green('✓')} ACL profile '{acl_name}'")

            while self._ask_yn("  Add publish topic exception?", default=True):
                t = self._ask("    Topic (e.g. mars/orders/>)", required=True)
                semp.add_publish_exception(acl_name, t)
                print(f"    {green('✓')} Publish exception '{t}' added")

            while self._ask_yn("  Add subscribe topic exception?", default=True):
                t = self._ask("    Topic", required=True)
                semp.add_subscribe_exception(acl_name, t)
                print(f"    {green('✓')} Subscribe exception '{t}' added")

        # Client username
        if self._ask_yn("Create a Client Username?", default=True):
            u_name    = self._ask("  Username",       "mars-user")
            u_pw      = self._ask_password("  Password (Enter to auto-generate)")
            u_profile = self._ask("  Client profile", profile_name or "default")
            u_acl     = self._ask("  ACL profile",    acl_name or "default")
            semp.create_client_username(u_name, u_pw, u_profile, u_acl)
            print(f"  {green('✓')} Client username '{u_name}' created")

        # Queues
        while self._ask_yn("Add a Queue?", default=True):
            q_name  = self._ask("  Queue name",   "mars-orders-q")
            q_type  = self._ask("  Access type (exclusive / non-exclusive)", "non-exclusive")
            semp.create_queue(q_name, access_type=q_type)
            print(f"  {green('✓')} Queue '{q_name}' created")
            while self._ask_yn("  Add topic subscription to this queue?", default=True):
                t = self._ask("    Topic", required=True)
                semp.add_queue_subscription(q_name, t)
                print(f"    {green('✓')} Subscription '{t}' added")

        # RDP
        while self._ask_yn("Add a REST Delivery Point (RDP)?", default=False):
            rdp_name = self._ask("  RDP name",     "mars-rdp")
            rdp_prof = self._ask("  Client profile", profile_name or "default")
            semp.create_rdp(rdp_name, client_profile=rdp_prof)

            cons_name = self._ask("  REST consumer name",   "mars-rest-consumer")
            cons_host = self._ask("  Target host (FQDN)",   required=True)
            cons_port = int(self._ask("  Port",             "443"))
            cons_tls  = self._ask_yn("  TLS?", default=True)
            semp.create_rest_consumer(rdp_name, cons_name, cons_host, cons_port, cons_tls)

            while self._ask_yn("  Bind a queue to this RDP?", default=True):
                q   = self._ask("    Queue name",    required=True)
                pth = self._ask("    POST path",     "/")
                semp.bind_queue_to_rdp(rdp_name, q, pth)
                print(f"    {green('✓')} Queue '{q}' bound → RDP '{rdp_name}'")
            print(f"  {green('✓')} RDP '{rdp_name}' configured")

        # ── Done ─────────────────────────────────────────────────────────────
        print(f"\n{'─'*60}")
        print(green("🎉  Integration created successfully!"))
        print(f"  Service ID : {service_id}")
        print(f"  VPN        : {vpn_name}")
        print(f"  EP domain  : {domain_name}  (id={domain_id})")
        print(f"  Objects    : {len(schemas)} schemas · {len(events)} events · {len(apps)} apps")
        print()
        print(f"  Inspect live cluster:")
        print(f"  {cyan('python solace.py cluster status')}")
        print(f"  {cyan('python solace.py domain list')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 2 — CLONE EXISTING COUNTRY
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_clone_country(self):
        self._section("Flow 2 — Clone Existing Country → New Country")

        # ── Source ───────────────────────────────────────────────────────────
        self._header("Step 1 / 4  —  Source Service")
        src_id = self._ask(
            "Source service ID",
            default=self.ctx.service_id or None,
            required=True,
        )
        src_country = self._ask("Source country code (e.g. AU, DEV)", required=True).upper()

        # ── Target ───────────────────────────────────────────────────────────
        self._header("Step 2 / 4  —  Target Country")
        tgt_country = self._ask("Target country code (e.g. SG, DE, US)", required=True).upper()
        svc_name    = self._ask("New service name",
                                f"mars-automation-{tgt_country.lower()}")

        print(f"\n  {dim('Available datacenters:')}")
        dcs = self.cloud.list_datacenters()
        for d in dcs[:12]:
            print(f"    {d['id']:<30} {d.get('displayName','')}")
        print()
        datacenter  = self._ask("Target datacenter ID", "aks-centralus")

        # ── Export source ────────────────────────────────────────────────────
        self._header("Step 3 / 4  —  Export Source Config")
        print(f"  Exporting service {src_id}  country={src_country} …")
        exp      = Exporter(self.ctx)
        src_data = exp.export(service_id=src_id, country_code=src_country)

        print(f"\n  {green('✓ Export complete')}")
        ep = src_data.get("eventPortal", {})
        cm = src_data.get("clusterManagement", {})
        self._print_summary(src_data, label="SOURCE")

        # ── Clone + customise ────────────────────────────────────────────────
        self._header("Step 4 / 4  —  Customise & Provision")

        c       = Cloner()
        cloned  = c.clone(
            source_config  = src_data,
            target_country = tgt_country,
            datacenter     = datacenter,
            service_name   = svc_name,
            generate_passwords = True,
        )

        print(f"\n  {bold('Clone diff preview:')}")
        print(Cloner.diff_summary(src_data, cloned))

        # Interactive overrides
        print(f"\n  {bold('Review & customise  (press Enter to keep default):')}\n")

        # EP domain name
        ep_out = cloned.setdefault("eventPortal", {})
        ep_out["domainName"] = self._ask(
            "EP domain name", ep_out.get("domainName", f"MarsAutomation-{tgt_country}")
        )

        # Topic prefix — find the common prefix and let user change it
        all_topics = [e.get("topic","") for e in ep_out.get("events", [])]
        if all_topics:
            prefix = all_topics[0].split("/")[0] if all_topics else "mars"
            new_prefix = self._ask(
                f"Topic prefix (currently '{prefix}')", prefix, required=False
            )
            if new_prefix and new_prefix != prefix:
                cloned = self._replace_topic_prefix(cloned, prefix, new_prefix)
                print(f"  {green('✓')} Topics updated to prefix '{new_prefix}'")

        # REST consumer host overrides
        cm_out = cloned.setdefault("clusterManagement", {})
        for rdp in cm_out.get("restDeliveryPoints", []):
            for con in rdp.get("consumers", []):
                old_host = con.get("host", "")
                new_host = self._ask(
                    f"REST consumer host (for '{con.get('name','')}')  current",
                    default=old_host, required=False,
                )
                if new_host:
                    con["host"] = new_host

        # Extra queues?
        print()
        while self._ask_yn("Add an extra queue to the clone?", default=False):
            q_name = self._ask("  Queue name", required=True)
            q_type = self._ask("  Access type", "non-exclusive")
            subs   = []
            while self._ask_yn("  Add topic subscription?", default=True):
                subs.append(self._ask("    Topic", required=True))
            cm_out.setdefault("queues", []).append({
                "name": q_name, "accessType": q_type, "subscriptions": subs,
            })
            print(f"  {green('✓')} Queue '{q_name}' added to clone")

        # Override passwords?
        if self._ask_yn("Manually set passwords for client usernames?", default=False):
            for u in cm_out.get("clientUsernames", []):
                pw = self._ask_password(f"  Password for '{u['name']}'")
                if pw:
                    u["password"] = pw

        # Save clone config
        out_path = f"config/{tgt_country.lower()}/service.json"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(cloned, indent=2))
        print(f"\n  {green('✓')} Clone config saved → {out_path}")

        # Final summary
        print(f"\n  {bold('Final config summary:')}")
        self._print_summary(cloned, label="TARGET")

        # ── Confirm + provision ───────────────────────────────────────────────
        if not self._ask_yn("\nCreate new service and provision everything?", default=True):
            print(f"\n  Config saved. To provision later:\n"
                  f"  {cyan(f'python solace.py provision run --config {out_path}')}\n")
            return

        # Create new messaging service
        print(f"\n  {yellow('Creating new messaging service …')}")
        svc = self.cloud.create_service(
            name          = cloned["service"]["name"],
            service_type  = cloned["service"].get("serviceTypeId",  "developer"),
            service_class = cloned["service"].get("serviceClassId", "developer"),
            datacenter    = cloned["service"]["datacenterId"],
        )
        new_sid = svc["serviceId"]
        print(f"  serviceId={new_sid}  state={svc.get('creationState')}")
        print(f"  {yellow('Waiting for service to be ready …')}")
        svc   = self.cloud.wait_for_service(new_sid)
        creds = self.cloud.extract_semp_creds(svc)

        # Save new service to context
        self.ctx.set_service(
            service_id = new_sid,
            vpn_name   = creds["vpnName"],
            semp_base  = creds["sempBaseUrl"],
            semp_user  = creds["sempUsername"],
            semp_pass  = creds["sempPassword"],
        )
        self.ctx.save()
        self.client = SolaceClient.from_context(self.ctx.as_dict())

        # Inject real VPN name into cloned config
        cloned["service"]["serviceId"] = new_sid
        cloned["clusterManagement"]["vpnName"] = creds["vpnName"]
        Path(out_path).write_text(json.dumps(cloned, indent=2))
        print(f"  {green('✓ Service ready')}  VPN={creds['vpnName']}")

        # Provision EP + cluster
        print(f"\n  {yellow('Provisioning Event Portal …')}")
        p = Provisioner(self.ctx)
        p.provision_event_portal(cloned)

        print(f"\n  {yellow('Provisioning Cluster Objects …')}")
        p.provision_cluster(cloned)

        # Final status
        print(f"\n{'─'*60}")
        print(green("🎉  Replication complete!"))
        print(f"  Source : {src_country}  →  {service_id_label(src_id)}")
        print(f"  Target : {tgt_country}  →  service {new_sid}")
        print(f"  Config : {out_path}")
        print()
        print(f"  {cyan('python solace.py cluster status')}")
        print(f"  {cyan('python solace.py domain list')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 3 — EP ONLY
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_ep_only(self):
        self._section("Flow 3 — Event Portal Design Only")
        self._header("Domain")

        domain_name = self._ask("Application domain name", required=True)
        domain_desc = self._ask("Description", "", required=False)
        domain = EventPortalAPI(self.client).get_or_create_domain(domain_name, domain_desc)
        domain_id = domain["id"]
        print(f"  {green('✓')} Domain '{domain_name}'  id={domain_id}")

        schema_ver_map: dict[str,str] = {}

        # Schemas
        self._header("Schemas")
        while self._ask_yn("Add a schema?", default=True):
            s_name = self._ask("  Schema name",   required=True)
            s_type = self._ask("  Type", "jsonSchema")
            s_ver  = self._ask("  Version", "1.0.0")
            s_file = self._ask("  Content file path (or Enter for empty)", "", required=False)
            s_content = "{}"
            if s_file and Path(s_file).exists():
                s_content = Path(s_file).read_text()
            ep = EventPortalAPI(self.client)
            s  = ep.get_or_create_schema(s_name, domain_id, s_type)
            existing = ep.list_schema_versions(schema_id=s["id"])
            sv = existing[-1] if existing else ep.create_schema_version(s["id"], s_ver, s_content)
            schema_ver_map[s_name] = sv["id"]
            print(f"  {green('✓')} Schema '{s_name}'  version_id={sv['id']}")

        # Events
        self._header("Events")
        event_ver_map: dict[str,str] = {}
        while self._ask_yn("Add an event?", default=True):
            e_name  = self._ask("  Event name",  required=True)
            e_topic = self._ask("  Topic",        required=True)
            e_ver   = self._ask("  Version", "1.0.0")
            sv_id   = None
            if schema_ver_map:
                if self._ask_yn(f"  Link to schema? ({list(schema_ver_map.keys())})", True):
                    sn = self._ask("  Schema name", next(iter(schema_ver_map.keys())))
                    sv_id = schema_ver_map.get(sn)
            ep = EventPortalAPI(self.client)
            e  = ep.get_or_create_event(e_name, domain_id)
            existing_ev = ep.list_event_versions(event_id=e["id"])
            ev = existing_ev[-1] if existing_ev else ep.create_event_version(
                e["id"], e_ver, e_topic, sv_id)
            event_ver_map[e_name] = ev["id"]
            print(f"  {green('✓')} Event '{e_name}'  topic={e_topic}")

        # Applications
        self._header("Applications")
        while self._ask_yn("Add an application?", default=True):
            a_name = self._ask("  App name",    required=True)
            a_ver  = self._ask("  Version", "1.0.0")
            produces, consumes = [], []
            if event_ver_map:
                print(f"  Events: {list(event_ver_map.keys())}")
                if self._ask_yn("  Produces events?", False):
                    produces = self._ask_from_list(list(event_ver_map.keys()), "Produces")
                if self._ask_yn("  Consumes events?", False):
                    consumes = self._ask_from_list(list(event_ver_map.keys()), "Consumes")
            ep = EventPortalAPI(self.client)
            a  = ep.get_or_create_application(a_name, domain_id)
            existing_av = ep.list_application_versions(app_id=a["id"])
            if not existing_av:
                ep.create_application_version(
                    a["id"], a_ver,
                    produces=[event_ver_map[n] for n in produces if n in event_ver_map],
                    consumes=[event_ver_map[n] for n in consumes if n in event_ver_map],
                )
            print(f"  {green('✓')} App '{a_name}'")

        print(f"\n{green('✓ Event Portal design complete!')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 4 — CLUSTER ONLY
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_cluster_only(self):
        self._section("Flow 4 — Cluster / Broker Objects Only")
        vpn = self.ctx.vpn_name
        if not vpn:
            vpn = self._ask("VPN name", required=True)
        semp = SempAPI(self.client, vpn)
        print(f"  Target VPN: {cyan(vpn)}\n")

        if self._ask_yn("Create Client Profile?", True):
            name = self._ask("  Name", required=True)
            semp.create_client_profile(name)
            print(f"  {green('✓')} Client profile '{name}'")

        if self._ask_yn("Create ACL Profile?", True):
            name = self._ask("  Name", required=True)
            pub  = self._ask("  Publish default", "disallow")
            sub  = self._ask("  Subscribe default", "disallow")
            semp.create_acl_profile(name, publish_default=pub, subscribe_default=sub)
            while self._ask_yn("  Add publish exception?", True):
                semp.add_publish_exception(name, self._ask("    Topic", required=True))
            while self._ask_yn("  Add subscribe exception?", True):
                semp.add_subscribe_exception(name, self._ask("    Topic", required=True))
            print(f"  {green('✓')} ACL profile '{name}'")

        if self._ask_yn("Create Client Username?", True):
            name = self._ask("  Name",           required=True)
            pw   = self._ask_password("  Password")
            prof = self._ask("  Client profile", "default")
            acl  = self._ask("  ACL profile",    "default")
            semp.create_client_username(name, pw, prof, acl)
            print(f"  {green('✓')} Client username '{name}'")

        while self._ask_yn("Add Queue?", True):
            name = self._ask("  Name",        required=True)
            atyp = self._ask("  Access type", "non-exclusive")
            semp.create_queue(name, access_type=atyp)
            while self._ask_yn("  Add topic subscription?", True):
                semp.add_queue_subscription(name, self._ask("    Topic", required=True))
            print(f"  {green('✓')} Queue '{name}'")

        if self._ask_yn("Add REST Delivery Point?", False):
            name = self._ask("  RDP name",      required=True)
            prof = self._ask("  Client profile", "default")
            semp.create_rdp(name, client_profile=prof)
            cname = self._ask("  Consumer name", required=True)
            host  = self._ask("  Host",          required=True)
            port  = int(self._ask("  Port", "443"))
            tls   = self._ask_yn("  TLS?", True)
            semp.create_rest_consumer(name, cname, host, port, tls)
            while self._ask_yn("  Bind a queue?", True):
                q   = self._ask("    Queue name", required=True)
                pth = self._ask("    POST path",  "/")
                semp.bind_queue_to_rdp(name, q, pth)
            print(f"  {green('✓')} RDP '{name}'")

        print(f"\n{green('✓ Cluster objects created!')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # PROMPT HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _ask(self, prompt: str, default: str = None, required: bool = True) -> str:
        suffix = f" [{default}]" if default else ""
        while True:
            ans = input(f"  {cyan('?')} {prompt}{suffix}: ").strip()
            if ans:
                return ans
            if default is not None:
                return default
            if not required:
                return ""
            print(f"    {red('This field is required.')}")

    def _ask_yn(self, prompt: str, default: bool = True) -> bool:
        hint = f"{bold('Y')}/n" if default else f"y/{bold('N')}"
        ans  = input(f"  {cyan('?')} {prompt} [{hint}]: ").strip().lower()
        if not ans:
            return default
        return ans.startswith("y")

    def _ask_password(self, prompt: str) -> str:
        ans = input(f"  {cyan('?')} {prompt} (Enter = auto-generate): ").strip()
        if not ans:
            pw = Cloner._gen_password()
            print(f"    {yellow('Auto-generated:')} {pw}")
            return pw
        return ans

    def _ask_from_list(self, options: list[str], label: str) -> list[str]:
        selected = []
        for opt in options:
            if self._ask_yn(f"  {label}: {bold(opt)}?", default=False):
                selected.append(opt)
        return selected

    def _ask_main_menu(self) -> int:
        opts = [
            ("1", "Create new integration from scratch",
             "Guided setup: service → EP design → cluster objects"),
            ("2", "Clone existing country → new country",
             "Export live config, substitute country, customise, provision"),
            ("3", "Event Portal design objects only",
             "Add domain / schema / event / application"),
            ("4", "Cluster / broker objects only",
             "Add profile / ACL / username / queue / RDP"),
        ]
        print(f"\n{bold('What would you like to do?')}\n")
        for num, title, desc in opts:
            print(f"  {cyan(f'[{num}]')} {bold(title)}")
            print(f"       {dim(desc)}")
        print()
        while True:
            try:
                ans = int(input(f"  {cyan('?')} Enter choice [1-4]: ").strip())
                if 1 <= ans <= 4:
                    return ans
            except (ValueError, EOFError):
                pass
            print(f"    {red('Please enter 1, 2, 3, or 4.')}")

    # ── display helpers ────────────────────────────────────────────────────────
    def _banner(self):
        print()
        print(bold("  ╔══════════════════════════════════════════════════╗"))
        print(bold("  ║    Solace Cloud Automation — Interactive Wizard  ║"))
        print(bold("  ╚══════════════════════════════════════════════════╝"))
        print()
        print(f"  Active service : {cyan(self.ctx.service_id or '(none)')}")
        print(f"  VPN            : {cyan(self.ctx.vpn_name   or '(none)')}")
        print()

    def _section(self, title: str):
        print(f"\n{bold('═'*62)}")
        print(f"  {bold(cyan(title))}")
        print(f"{'═'*62}\n")

    def _header(self, title: str):
        print(f"\n  {bold('── ' + title + ' ' + '─'*(50-len(title)))}")

    def _print_summary(self, cfg: dict, label: str = ""):
        ep = cfg.get("eventPortal", {})
        cm = cfg.get("clusterManagement", {})
        tag = f"[{label}]  " if label else ""
        print(f"\n  {bold(tag + 'Summary:')}")
        print(f"    Service     : {cfg.get('service',{}).get('name','')}  "
              f"({cfg.get('service',{}).get('datacenterId','')})")
        print(f"    EP domain   : {ep.get('domainName','')}")
        print(f"    Schemas     : {', '.join(s['name'] for s in ep.get('schemas',[]))  or '—'}")
        print(f"    Events      : {', '.join(e['name'] for e in ep.get('events',[]))   or '—'}")
        print(f"    Applications: {', '.join(a['name'] for a in ep.get('applications',[]))  or '—'}")
        print(f"    Profiles    : {', '.join(p['name'] for p in cm.get('clientProfiles',[]))  or '—'}")
        print(f"    Queues      : {', '.join(q['name'] for q in cm.get('queues',[]))   or '—'}")
        print(f"    RDPs        : {', '.join(r['name'] for r in cm.get('restDeliveryPoints',[]))  or '—'}")

    # ── utility ───────────────────────────────────────────────────────────────
    @staticmethod
    def _replace_topic_prefix(cfg: dict, old: str, new: str) -> dict:
        """Replace topic prefix in all event topics and ACL exceptions."""
        import copy, re
        cfg = copy.deepcopy(cfg)
        for e in cfg.get("eventPortal", {}).get("events", []):
            t = e.get("topic", "")
            if t.startswith(old + "/"):
                e["topic"] = new + t[len(old):]
        for acl in cfg.get("clusterManagement", {}).get("aclProfiles", []):
            acl["publishExceptions"] = [
                new + t[len(old):] if t.startswith(old + "/") else t
                for t in acl.get("publishExceptions", [])
            ]
            acl["subscribeExceptions"] = [
                new + t[len(old):] if t.startswith(old + "/") else t
                for t in acl.get("subscribeExceptions", [])
            ]
        for q in cfg.get("clusterManagement", {}).get("queues", []):
            q["subscriptions"] = [
                new + t[len(old):] if t.startswith(old + "/") else t
                for t in q.get("subscriptions", [])
            ]
        return cfg


def service_id_label(sid: str) -> str:
    return f"service {sid}" if sid else "(unknown)"
