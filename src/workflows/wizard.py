"""
src/workflows/wizard.py — Interactive Guided Wizard
=====================================================
Zero hardcoded values.  Every name, topic, datacenter, and service type
is either derived from user input or fetched live from the Solace Cloud API.

Flows
-----
  1  Create new integration from scratch
       Project prefix  →  live datacenter pick  →  live service-type pick
       →  EP domain  →  schemas  →  events  →  applications
       →  client profile  →  ACL  →  username  →  queues  →  RDP

  2  Clone existing country → new country
       Export source live config  →  clone diff preview
       →  interactive customisation (domain, topic prefix, REST hosts, extra queues)
       →  confirm  →  create service  →  provision

  3  Event Portal design objects only
       Domain  →  schemas  →  events  →  applications

  4  Cluster / broker objects only
       Client profile  →  ACL  →  username  →  queues  →  RDP

Usage
-----
    python3 solace.py wizard                  # menu
    python3 solace.py wizard --flow 1         # jump to create-from-scratch
    python3 solace.py wizard --flow 2         # jump to clone
"""

from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

from client           import SolaceClient, SolaceError
from context          import Context
from api.cloud_svc    import CloudServiceAPI
from api.event_portal import EventPortalAPI
from api.semp         import SempAPI
from workflows.exporter  import Exporter
from workflows.cloner    import Cloner
from workflows.provision import Provisioner

logger = logging.getLogger(__name__)

# ── ANSI colours (disabled gracefully on non-TTY) ─────────────────────────────
_TTY = sys.stdout.isatty()
def _c(code, t): return f"\033[{code}m{t}\033[0m" if _TTY else t
def bold(t):   return _c("1",  t)
def cyan(t):   return _c("96", t)
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def red(t):    return _c("91", t)
def dim(t):    return _c("2",  t)


class InteractiveWizard:
    """
    Fully interactive guided wizard.
    No defaults are hardcoded — every value comes from user input or live API calls.
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
            print(f"\n\n{yellow('Aborted.')}\n")
            sys.exit(0)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 1 — CREATE FROM SCRATCH
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_create_from_scratch(self):
        self._section("Flow 1 — Create New Integration From Scratch")

        # ── Project identity ─────────────────────────────────────────────────
        self._header("Step 1 / 6  —  Project Identity")
        pfx = self._ask_prefix()
        env = self._ask(
            "Environment / country label",
            hint="e.g. AU, US, DEV, PROD — used in all object names",
            required=True,
        ).lower()

        # ── Messaging Service ────────────────────────────────────────────────
        self._header("Step 2 / 6  —  Messaging Service")

        use_existing = self._ask_yn(
            "Use the service already active in context?",
            default=bool(self.ctx.service_id),
        )
        service_id = None
        vpn_name   = None

        if not use_existing:
            svc_name   = self._ask("Service name", f"{pfx}-{env}")
            datacenter = self._pick_datacenter()
            svc_type, svc_class = self._pick_service_type_class()

            # ── Try to create; handle quota / broker errors gracefully ────────
            while True:
                print(f"\n  {yellow('Creating service …')}")
                try:
                    svc = self.cloud.create_service(
                        name=svc_name, service_type=svc_type,
                        service_class=svc_class, datacenter=datacenter,
                    )
                    break   # success

                except SolaceError as exc:
                    body     = exc.body if isinstance(exc.body, dict) else {}
                    sub_code = body.get("subCode", "")
                    message  = body.get("message", str(exc))

                    print(f"\n  {red('✗ Service creation failed')}")
                    print(f"    {yellow(message)}\n")

                    if "5000_5600" in sub_code:
                        # Quota exceeded — suggest a different service class
                        print(f"  {dim('Your account has no quota for that service class.')}")
                        print(f"  {dim('Try a different type (e.g. Free / Developer).')}")
                    elif "5000_102" in sub_code:
                        # No enabled brokers in that datacenter
                        print(f"  {dim('No brokers available in that datacenter for that service type.')}")
                        print(f"  {dim('Try a different datacenter or service type.')}")

                    # Offer recovery options
                    print()
                    if self.ctx.service_id:
                        print(f"  {bold('Options:')}")
                        print(f"    {cyan('[1]')} Try a different service type / datacenter")
                        print(f"    {cyan('[2]')} Use the existing service in context  "
                              f"({cyan(self.ctx.service_id)})")
                        choice = input(f"  {cyan('?')} Choose [1/2]: ").strip()
                        if choice == "2":
                            use_existing = True
                            break
                    else:
                        print(f"  {bold('Options:')}")
                        print(f"    {cyan('[1]')} Try a different service type / datacenter")
                        print(f"    {cyan('[2]')} Enter an existing service ID manually")
                        choice = input(f"  {cyan('?')} Choose [1/2]: ").strip()
                        if choice == "2":
                            service_id = self._ask("Existing service ID", required=True)
                            svc   = self.cloud.get_service(service_id)
                            creds = self.cloud.extract_semp_creds(svc)
                            vpn_name = creds["vpnName"]
                            self.ctx.set_service(
                                service_id=service_id, vpn_name=vpn_name,
                                semp_base=creds["sempBaseUrl"],
                                semp_user=creds["sempUsername"],
                                semp_pass=creds["sempPassword"],
                            )
                            self.ctx.save()
                            self.client = SolaceClient.from_context(self.ctx.as_dict())
                            print(f"  {green('✓ Using service')}  {service_id}  VPN={vpn_name}")
                            use_existing = True
                            break

                    # retry — repick datacenter + service type
                    print()
                    datacenter = self._pick_datacenter()
                    svc_type, svc_class = self._pick_service_type_class()

            if not use_existing:
                service_id = svc["serviceId"]
                print(f"  serviceId={service_id}  state={svc.get('creationState')}")
                print(f"  {yellow('Waiting for service to be ready (~1 min) …')}")
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

        # ── Re-resolve IDs from context if we fell back to existing service ──
        if use_existing:
            service_id = self.ctx.service_id
            vpn_name   = self.ctx.vpn_name
            if not service_id:
                service_id = self._ask("Service ID", required=True)
                svc   = self.cloud.get_service(service_id)
                creds = self.cloud.extract_semp_creds(svc)
                vpn_name = creds["vpnName"]
                self.ctx.set_service(
                    service_id=service_id, vpn_name=vpn_name,
                    semp_base=creds["sempBaseUrl"],
                    semp_user=creds["sempUsername"],
                    semp_pass=creds["sempPassword"],
                )
                self.ctx.save()
                self.client = SolaceClient.from_context(self.ctx.as_dict())
            print(f"  {green('✓ Using existing service')}  {service_id}  VPN={vpn_name}")

        # ── EP Domain ────────────────────────────────────────────────────────
        self._header("Step 3 / 6  —  Event Portal Domain")
        domain_name = self._ask(
            "Application domain name",
            f"{pfx.capitalize()}{env.upper()}",
        )
        domain_desc = self._ask("Description", required=False)
        domain = EventPortalAPI(self.client).get_or_create_domain(domain_name, domain_desc or "")
        domain_id = domain["id"]
        print(f"  {green('✓')} Domain '{domain_name}'  id={domain_id}")

        # ── Schemas ──────────────────────────────────────────────────────────
        self._header("Step 4 / 6  —  Schemas")
        schema_ver_map: dict[str, str] = {}   # name → schema_version_id

        while self._ask_yn("Add a schema?", default=True):
            s_name = self._ask("  Schema name", required=True)
            s_type = self._ask_choice_inline(
                "  Schema type",
                ["jsonSchema", "avro", "protobuf", "xmlSchema"],
                default="jsonSchema",
            )
            s_ver   = self._ask("  Version", "1.0.0")
            s_desc  = self._ask("  Description", required=False)
            s_file  = self._ask("  Schema content file path (Enter = empty schema)", required=False)
            s_content = "{}"
            if s_file and Path(s_file).exists():
                s_content = Path(s_file).read_text()
                print(f"  {green('✓')} Loaded from {s_file}")
            elif s_file:
                print(f"  {yellow('File not found — using empty schema {{}}')}")

            ep = EventPortalAPI(self.client)
            s  = ep.get_or_create_schema(s_name, domain_id, s_type)
            existing = ep.list_schema_versions(schema_id=s["id"])
            sv = existing[-1] if existing else ep.create_schema_version(
                s["id"], s_ver, s_content, s_desc or "")
            schema_ver_map[s_name] = sv["id"]
            print(f"  {green('✓')} Schema '{s_name}'  version_id={sv['id']}")

        # ── Events ───────────────────────────────────────────────────────────
        self._header("Step 4 / 6  —  Events")
        event_ver_map: dict[str, str] = {}   # name → event_version_id

        while self._ask_yn("Add an event?", default=True):
            e_name  = self._ask("  Event name", required=True)
            e_topic = self._ask(
                "  Topic string",
                hint=f"e.g. {pfx}/{env}/orders/{{orderId}}/created",
                required=True,
            )
            e_ver   = self._ask("  Version", "1.0.0")
            e_desc  = self._ask("  Description", required=False)
            sv_id   = None
            if schema_ver_map:
                if self._ask_yn(f"  Link to a schema? (available: {list(schema_ver_map)})", True):
                    sn    = self._ask_from_options("  Which schema?", list(schema_ver_map.keys()))
                    sv_id = schema_ver_map.get(sn)

            ep = EventPortalAPI(self.client)
            e  = ep.get_or_create_event(e_name, domain_id, e_desc or "")
            existing_ev = ep.list_event_versions(event_id=e["id"])
            ev = existing_ev[-1] if existing_ev else ep.create_event_version(
                e["id"], e_ver, e_topic, sv_id, e_desc or "")
            event_ver_map[e_name] = ev["id"]
            print(f"  {green('✓')} Event '{e_name}'  topic={e_topic}")

        # ── Applications ─────────────────────────────────────────────────────
        self._header("Step 5 / 6  —  Applications")
        all_events = list(event_ver_map.keys())

        while self._ask_yn("Add an application?", default=True):
            a_name = self._ask("  Application name", required=True)
            a_ver  = self._ask("  Version", "1.0.0")
            a_desc = self._ask("  Description", required=False)
            produces, consumes = [], []
            if all_events:
                print(f"  Available events: {all_events}")
                if self._ask_yn("  Does this app PRODUCE (publish) events?", False):
                    produces = self._ask_from_checklist(all_events, "Produces")
                if self._ask_yn("  Does this app CONSUME (subscribe) events?", False):
                    consumes = self._ask_from_checklist(all_events, "Consumes")

            ep = EventPortalAPI(self.client)
            a  = ep.get_or_create_application(a_name, domain_id, description=a_desc or "")
            existing_av = ep.list_application_versions(app_id=a["id"])
            if not existing_av:
                ep.create_application_version(
                    a["id"], a_ver,
                    produces=[event_ver_map[n] for n in produces if n in event_ver_map],
                    consumes=[event_ver_map[n] for n in consumes if n in event_ver_map],
                    description=a_desc or "",
                )
            print(f"  {green('✓')} App '{a_name}'  produces={produces}  consumes={consumes}")

        # ── Cluster Objects ──────────────────────────────────────────────────
        self._header("Step 6 / 6  —  Cluster / Broker Objects")
        semp = SempAPI(self.client, vpn_name)

        profile_name = None
        if self._ask_yn("Create a Client Profile?", True):
            profile_name = self._ask("  Profile name", f"{pfx}-{env}-profile")
            semp.create_client_profile(profile_name)
            print(f"  {green('✓')} Client profile '{profile_name}'")

        acl_name = None
        if self._ask_yn("Create an ACL Profile?", True):
            acl_name    = self._ask("  ACL name", f"{pfx}-{env}-acl")
            pub_default = self._ask_choice_inline(
                "  Publish default action", ["disallow", "allow"], "disallow")
            sub_default = self._ask_choice_inline(
                "  Subscribe default action", ["disallow", "allow"], "disallow")
            semp.create_acl_profile(
                acl_name,
                publish_default=pub_default,
                subscribe_default=sub_default,
            )
            print(f"  {green('✓')} ACL profile '{acl_name}'")
            while self._ask_yn("  Add publish topic exception?", True):
                t = self._ask("    Topic", hint=f"e.g. {pfx}/{env}/>", required=True)
                semp.add_publish_exception(acl_name, t)
                print(f"    {green('✓')} Publish exception '{t}'")
            while self._ask_yn("  Add subscribe topic exception?", True):
                t = self._ask("    Topic", required=True)
                semp.add_subscribe_exception(acl_name, t)
                print(f"    {green('✓')} Subscribe exception '{t}'")

        if self._ask_yn("Create a Client Username?", True):
            u_name    = self._ask("  Username", f"{pfx}-{env}-user")
            u_pw      = self._ask_password("  Password")
            u_profile = self._ask("  Client profile", profile_name or "")
            u_acl     = self._ask("  ACL profile",    acl_name or "")
            semp.create_client_username(u_name, u_pw, u_profile, u_acl)
            print(f"  {green('✓')} Client username '{u_name}'")

        while self._ask_yn("Add a Queue?", True):
            q_name = self._ask("  Queue name", f"{pfx}-{env}-q")
            q_type = self._ask_choice_inline(
                "  Access type", ["non-exclusive", "exclusive"], "non-exclusive")
            semp.create_queue(q_name, access_type=q_type)
            print(f"  {green('✓')} Queue '{q_name}'")
            while self._ask_yn("  Add topic subscription?", True):
                t = self._ask("    Topic", hint=f"e.g. {pfx}/{env}/>", required=True)
                semp.add_queue_subscription(q_name, t)
                print(f"    {green('✓')} Subscription '{t}'")

        while self._ask_yn("Add a REST Delivery Point (RDP)?", False):
            rdp_name  = self._ask("  RDP name",       f"{pfx}-{env}-rdp")
            rdp_prof  = self._ask("  Client profile", profile_name or "")
            semp.create_rdp(rdp_name, client_profile=rdp_prof)
            con_name  = self._ask("  REST consumer name",   f"{pfx}-{env}-consumer")
            con_host  = self._ask("  Target host (FQDN)",   required=True)
            con_port  = int(self._ask("  Port", "443"))
            con_tls   = self._ask_yn("  TLS?", True)
            semp.create_rest_consumer(rdp_name, con_name, con_host, con_port, con_tls)
            while self._ask_yn("  Bind a queue to this RDP?", True):
                q   = self._ask("    Queue name", required=True)
                pth = self._ask("    POST target path", "/")
                semp.bind_queue_to_rdp(rdp_name, q, pth)
                print(f"    {green('✓')} Queue '{q}' bound")
            print(f"  {green('✓')} RDP '{rdp_name}'")

        print(f"\n{'─'*60}")
        print(green("🎉  Integration created successfully!"))
        print(f"  Service : {service_id}  VPN={vpn_name}")
        print(f"  Domain  : {domain_name}  id={domain_id}")
        print()
        print(f"  {cyan('python3 solace.py cluster status')}")
        print(f"  {cyan('python3 solace.py domain list')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 2 — CLONE EXISTING COUNTRY
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_clone_country(self):
        self._section("Flow 2 — Clone Existing Country → New Country")

        # ── Source details ───────────────────────────────────────────────────
        self._header("Step 1 / 4  —  Source Service")
        src_id      = self._ask("Source service ID",
                                self.ctx.service_id or None, required=True)
        src_country = self._ask(
            "Source country / environment code",
            hint="e.g. AU, DEV, US  (must match what appears in object names)",
            required=True,
        ).upper()

        # ── Target ───────────────────────────────────────────────────────────
        self._header("Step 2 / 4  —  Target Details")
        tgt_country = self._ask(
            "Target country / environment code",
            hint="e.g. SG, DE, JP",
            required=True,
        ).upper()
        datacenter = self._pick_datacenter()

        # ── Export source ────────────────────────────────────────────────────
        self._header("Step 3 / 4  —  Export Source Config")
        print(f"  Exporting service {src_id}  country={src_country} …")
        exp      = Exporter(self.ctx)
        src_data = exp.export(service_id=src_id, country_code=src_country)
        print(f"\n  {green('✓ Export complete')}")
        self._print_summary(src_data, label="SOURCE")

        # ── Clone (automatic country substitution) ────────────────────────
        self._header("Step 4 / 4  —  Customise & Provision")
        c      = Cloner()
        cloned = c.clone(
            source_config      = src_data,
            target_country     = tgt_country,
            datacenter         = datacenter,
            generate_passwords = True,
        )
        # service name is derived by Cloner from substitution — let user confirm/override
        cloned["service"]["name"] = self._ask(
            "New service name",
            default=cloned["service"]["name"],
        )

        print(f"\n  {bold('Clone diff preview:')}")
        print(Cloner.diff_summary(src_data, cloned))

        # ── Interactive field overrides ───────────────────────────────────────
        print(f"\n  {bold('Review & customise each setting  (Enter = keep):')}\n")

        # EP domain
        ep_out = cloned.setdefault("eventPortal", {})
        current_domain = ep_out.get("domainName", "")
        ep_out["domainName"] = self._ask("EP domain name", current_domain)

        # Topic prefix — extract from cloned data, not hardcoded
        events = ep_out.get("events", [])
        if events:
            first_topic = events[0].get("topic", "")
            current_prefix = first_topic.split("/")[0] if "/" in first_topic else first_topic
            new_prefix = self._ask(
                f"Topic prefix  (current: '{current_prefix}')",
                default=current_prefix,
                required=False,
            )
            if new_prefix and new_prefix != current_prefix:
                cloned = self._replace_topic_prefix(cloned, current_prefix, new_prefix)
                print(f"  {green('✓')} Topics updated: '{current_prefix}' → '{new_prefix}'")

        # REST consumer hosts
        cm_out = cloned.setdefault("clusterManagement", {})
        for rdp in cm_out.get("restDeliveryPoints", []):
            for con in rdp.get("consumers", []):
                old_host = con.get("host", "")
                new_host = self._ask(
                    f"REST consumer host for '{con.get('name', '')}'",
                    default=old_host,
                    required=False,
                )
                if new_host:
                    con["host"] = new_host

        # Extra queues
        print()
        while self._ask_yn("Add an extra queue to the target?", False):
            q_name = self._ask("  Queue name", required=True)
            q_type = self._ask_choice_inline(
                "  Access type", ["non-exclusive", "exclusive"], "non-exclusive")
            subs = []
            while self._ask_yn("  Add topic subscription?", True):
                subs.append(self._ask("    Topic", required=True))
            cm_out.setdefault("queues", []).append({
                "name": q_name, "accessType": q_type, "subscriptions": subs,
            })
            print(f"  {green('✓')} Extra queue '{q_name}' added")

        # Password override
        if self._ask_yn("Manually set passwords? (default = auto-generated)", False):
            for u in cm_out.get("clientUsernames", []):
                pw = self._ask_password(f"  Password for '{u['name']}'")
                if pw:
                    u["password"] = pw

        # ── Save clone config ─────────────────────────────────────────────────
        out_path = f"config/{tgt_country.lower()}/service.json"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(cloned, indent=2))
        print(f"\n  {green('✓')} Clone config saved → {out_path}")

        self._print_summary(cloned, label="TARGET")

        if not self._ask_yn("\nCreate new service and provision everything now?", True):
            print(f"\n  Config saved. Run when ready:\n"
                  f"  {cyan(f'python3 solace.py provision run --config {out_path}')}\n")
            return

        # ── Create new messaging service ──────────────────────────────────────
        print(f"\n  {yellow('Creating new messaging service …')}")
        svc = self.cloud.create_service(
            name          = cloned["service"]["name"],
            service_type  = cloned["service"].get("serviceTypeId"),
            service_class = cloned["service"].get("serviceClassId"),
            datacenter    = cloned["service"]["datacenterId"],
        )
        new_sid = svc["serviceId"]
        print(f"  serviceId={new_sid}  state={svc.get('creationState')}")
        print(f"  {yellow('Waiting for service to be ready …')}")
        svc   = self.cloud.wait_for_service(new_sid)
        creds = self.cloud.extract_semp_creds(svc)

        self.ctx.set_service(
            service_id=new_sid,
            vpn_name=creds["vpnName"],
            semp_base=creds["sempBaseUrl"],
            semp_user=creds["sempUsername"],
            semp_pass=creds["sempPassword"],
        )
        self.ctx.save()
        self.client = SolaceClient.from_context(self.ctx.as_dict())

        cloned["service"]["serviceId"] = new_sid
        cloned["clusterManagement"]["vpnName"] = creds["vpnName"]
        Path(out_path).write_text(json.dumps(cloned, indent=2))
        print(f"  {green('✓ Service ready')}  VPN={creds['vpnName']}")

        # ── Provision ─────────────────────────────────────────────────────────
        print(f"\n  {yellow('Provisioning Event Portal …')}")
        p = Provisioner(self.ctx)
        p.provision_event_portal(cloned)

        print(f"\n  {yellow('Provisioning cluster objects …')}")
        p.provision_cluster(cloned)

        print(f"\n{'─'*60}")
        print(green("🎉  Replication complete!"))
        print(f"  {src_country}  →  {tgt_country}  ({new_sid})")
        print(f"  Config: {out_path}")
        print()
        print(f"  {cyan('python3 solace.py cluster status')}")
        print(f"  {cyan('python3 solace.py domain list')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 3 — EP ONLY
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_ep_only(self):
        self._section("Flow 3 — Event Portal Design Only")

        pfx = self._ask_prefix()
        env = self._ask("Environment / country label", required=True).lower()

        self._header("Domain")
        domain_name = self._ask("Application domain name",
                                f"{pfx.capitalize()}{env.upper()}")
        domain_desc = self._ask("Description", required=False)
        domain = EventPortalAPI(self.client).get_or_create_domain(
            domain_name, domain_desc or "")
        domain_id = domain["id"]
        print(f"  {green('✓')} Domain '{domain_name}'  id={domain_id}")

        schema_ver_map: dict[str, str] = {}

        self._header("Schemas")
        while self._ask_yn("Add a schema?", True):
            s_name = self._ask("  Schema name", required=True)
            s_type = self._ask_choice_inline(
                "  Type", ["jsonSchema", "avro", "protobuf", "xmlSchema"], "jsonSchema")
            s_ver  = self._ask("  Version", "1.0.0")
            s_file = self._ask("  Content file path (Enter = empty)", required=False)
            s_content = "{}"
            if s_file and Path(s_file).exists():
                s_content = Path(s_file).read_text()
            ep = EventPortalAPI(self.client)
            s  = ep.get_or_create_schema(s_name, domain_id, s_type)
            existing = ep.list_schema_versions(schema_id=s["id"])
            sv = existing[-1] if existing else ep.create_schema_version(
                s["id"], s_ver, s_content)
            schema_ver_map[s_name] = sv["id"]
            print(f"  {green('✓')} Schema '{s_name}'  version_id={sv['id']}")

        event_ver_map: dict[str, str] = {}
        self._header("Events")
        while self._ask_yn("Add an event?", True):
            e_name  = self._ask("  Event name", required=True)
            e_topic = self._ask("  Topic string",
                                hint=f"e.g. {pfx}/{env}/orders/{{orderId}}/created",
                                required=True)
            e_ver   = self._ask("  Version", "1.0.0")
            sv_id   = None
            if schema_ver_map:
                if self._ask_yn(f"  Link to schema? ({list(schema_ver_map)})", True):
                    sn    = self._ask_from_options("  Which schema?",
                                                   list(schema_ver_map.keys()))
                    sv_id = schema_ver_map.get(sn)
            ep = EventPortalAPI(self.client)
            e  = ep.get_or_create_event(e_name, domain_id)
            existing_ev = ep.list_event_versions(event_id=e["id"])
            ev = existing_ev[-1] if existing_ev else ep.create_event_version(
                e["id"], e_ver, e_topic, sv_id)
            event_ver_map[e_name] = ev["id"]
            print(f"  {green('✓')} Event '{e_name}'  topic={e_topic}")

        self._header("Applications")
        while self._ask_yn("Add an application?", True):
            a_name   = self._ask("  Application name", required=True)
            a_ver    = self._ask("  Version", "1.0.0")
            produces, consumes = [], []
            if event_ver_map:
                print(f"  Events: {list(event_ver_map)}")
                if self._ask_yn("  Produces events?", False):
                    produces = self._ask_from_checklist(list(event_ver_map), "Produces")
                if self._ask_yn("  Consumes events?", False):
                    consumes = self._ask_from_checklist(list(event_ver_map), "Consumes")
            ep = EventPortalAPI(self.client)
            a  = ep.get_or_create_application(a_name, domain_id)
            existing_av = ep.list_application_versions(app_id=a["id"])
            if not existing_av:
                ep.create_application_version(
                    a["id"], a_ver,
                    produces=[event_ver_map[n] for n in produces if n in event_ver_map],
                    consumes=[event_ver_map[n] for n in consumes if n in event_ver_map],
                )
            print(f"  {green('✓')} App '{a_name}'  produces={produces}  consumes={consumes}")

        print(f"\n{green('✓ Event Portal design complete!')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW 4 — CLUSTER ONLY
    # ══════════════════════════════════════════════════════════════════════════
    def _flow_cluster_only(self):
        self._section("Flow 4 — Cluster / Broker Objects Only")

        pfx = self._ask_prefix()
        env = self._ask("Environment / country label", required=True).lower()

        vpn = self.ctx.vpn_name
        if not vpn:
            vpn = self._ask("VPN name", required=True)
        print(f"  Target VPN: {cyan(vpn)}\n")
        semp = SempAPI(self.client, vpn)

        profile_name = None
        if self._ask_yn("Create Client Profile?", True):
            profile_name = self._ask("  Name", f"{pfx}-{env}-profile")
            semp.create_client_profile(profile_name)
            print(f"  {green('✓')} Client profile '{profile_name}'")

        acl_name = None
        if self._ask_yn("Create ACL Profile?", True):
            acl_name    = self._ask("  Name", f"{pfx}-{env}-acl")
            pub_default = self._ask_choice_inline(
                "  Publish default", ["disallow", "allow"], "disallow")
            sub_default = self._ask_choice_inline(
                "  Subscribe default", ["disallow", "allow"], "disallow")
            semp.create_acl_profile(
                acl_name, publish_default=pub_default, subscribe_default=sub_default)
            print(f"  {green('✓')} ACL profile '{acl_name}'")
            while self._ask_yn("  Add publish exception?", True):
                t = self._ask("    Topic",
                              hint=f"e.g. {pfx}/{env}/>", required=True)
                semp.add_publish_exception(acl_name, t)
                print(f"    {green('✓')} Publish exception '{t}'")
            while self._ask_yn("  Add subscribe exception?", True):
                t = self._ask("    Topic", required=True)
                semp.add_subscribe_exception(acl_name, t)
                print(f"    {green('✓')} Subscribe exception '{t}'")

        if self._ask_yn("Create Client Username?", True):
            u_name    = self._ask("  Name",           f"{pfx}-{env}-user")
            u_pw      = self._ask_password("  Password")
            u_profile = self._ask("  Client profile", profile_name or "")
            u_acl     = self._ask("  ACL profile",    acl_name or "")
            semp.create_client_username(u_name, u_pw, u_profile, u_acl)
            print(f"  {green('✓')} Client username '{u_name}'")

        while self._ask_yn("Add Queue?", True):
            q_name = self._ask("  Name", f"{pfx}-{env}-q")
            q_type = self._ask_choice_inline(
                "  Access type", ["non-exclusive", "exclusive"], "non-exclusive")
            semp.create_queue(q_name, access_type=q_type)
            print(f"  {green('✓')} Queue '{q_name}'")
            while self._ask_yn("  Add topic subscription?", True):
                t = self._ask("    Topic",
                              hint=f"e.g. {pfx}/{env}/>", required=True)
                semp.add_queue_subscription(q_name, t)
                print(f"    {green('✓')} Subscription '{t}'")

        if self._ask_yn("Add REST Delivery Point?", False):
            rdp_name = self._ask("  RDP name",       f"{pfx}-{env}-rdp")
            rdp_prof = self._ask("  Client profile", profile_name or "")
            semp.create_rdp(rdp_name, client_profile=rdp_prof)
            con_name = self._ask("  Consumer name",  f"{pfx}-{env}-consumer")
            con_host = self._ask("  Target host",    required=True)
            con_port = int(self._ask("  Port", "443"))
            con_tls  = self._ask_yn("  TLS?", True)
            semp.create_rest_consumer(rdp_name, con_name, con_host, con_port, con_tls)
            while self._ask_yn("  Bind a queue?", True):
                q   = self._ask("    Queue name", required=True)
                pth = self._ask("    POST target path", "/")
                semp.bind_queue_to_rdp(rdp_name, q, pth)
                print(f"    {green('✓')} Queue '{q}' bound")
            print(f"  {green('✓')} RDP '{rdp_name}'")

        print(f"\n{green('✓ Cluster objects created!')}\n")

    # ══════════════════════════════════════════════════════════════════════════
    # LIVE API PICKERS  (no hardcoded values)
    # ══════════════════════════════════════════════════════════════════════════
    def _pick_datacenter(self) -> str:
        """Fetch live datacenter list and let the user pick by number or ID."""
        print(f"\n  {bold('Available datacenters:')} (fetching from API…)")
        dcs = self.cloud.list_datacenters()
        if not dcs:
            return self._ask("Datacenter ID", required=True)
        print()
        for i, d in enumerate(dcs, 1):
            provider = d.get("provider", "")
            region   = d.get("displayName", d["id"])
            print(f"    {cyan(f'[{i}]'):>10}  {d['id']:<32} {provider:<6} {region}")
        print()
        while True:
            ans = input(f"  {cyan('?')} Enter number or datacenter ID: ").strip()
            try:
                idx = int(ans)
                if 1 <= idx <= len(dcs):
                    chosen = dcs[idx - 1]["id"]
                    print(f"  {green('✓')} Datacenter: {chosen}")
                    return chosen
            except ValueError:
                if any(d["id"] == ans for d in dcs):
                    print(f"  {green('✓')} Datacenter: {ans}")
                    return ans
            print(f"    {red(f'Enter a number 1–{len(dcs)} or a valid datacenter ID.')}")

    def _pick_service_type_class(self) -> tuple[str, str]:
        """Fetch live service types+classes and let the user pick by number."""
        print(f"\n  {bold('Available service types:')} (fetching from API…)")
        types   = self.cloud.list_service_types()
        options: list[tuple[str, str, str]] = []  # (typeId, classId, label)
        for st in types:
            for sc in st.get("serviceClasses", []):
                label = f"{st.get('serviceTypeName', st['id'])} / {sc.get('serviceClassName', sc['id'])}"
                options.append((st["id"], sc["id"], label))
        if not options:
            type_id  = self._ask("Service type ID",  required=True)
            class_id = self._ask("Service class ID", required=True)
            return type_id, class_id
        print()
        for i, (tid, cid, label) in enumerate(options, 1):
            print(f"    {cyan(f'[{i}]'):>10}  {label:<55} "
                  f"{dim(f'type={tid}  class={cid}')}")
        print()
        while True:
            try:
                idx = int(input(f"  {cyan('?')} Enter number: ").strip())
                if 1 <= idx <= len(options):
                    tid, cid, label = options[idx - 1]
                    print(f"  {green('✓')} Service type: {label}")
                    return tid, cid
            except (ValueError, EOFError):
                pass
            print(f"    {red(f'Enter a number 1–{len(options)}.')}")

    # ══════════════════════════════════════════════════════════════════════════
    # PROMPT HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _ask_prefix(self) -> str:
        """Ask for a project/application prefix — no default, user must type."""
        print(f"\n  {dim('The prefix is used to generate all object names (queues, profiles, etc.)')}")
        return self._ask(
            "Project / application prefix",
            hint="e.g. acme, orders, retail, finance",
            required=True,
        )

    def _ask(self, prompt: str, default: str = None,
             hint: str = None, required: bool = True) -> str:
        hint_str    = f"  {dim(hint)}" if hint else ""
        default_str = f" [{bold(default)}]" if default else ""
        if hint_str:
            print(hint_str)
        while True:
            ans = input(f"  {cyan('?')} {prompt}{default_str}: ").strip()
            if ans:
                return ans
            if default is not None:
                return default
            if not required:
                return ""
            print(f"    {red('Required — please enter a value.')}")

    def _ask_yn(self, prompt: str, default: bool = True) -> bool:
        hint = f"{bold('Y')}/n" if default else f"y/{bold('N')}"
        ans  = input(f"  {cyan('?')} {prompt} [{hint}]: ").strip().lower()
        return (ans.startswith("y") if ans else default)

    def _ask_password(self, prompt: str) -> str:
        ans = input(f"  {cyan('?')} {prompt} (Enter = auto-generate): ").strip()
        if not ans:
            pw = Cloner._gen_password()
            print(f"    {yellow('Auto-generated:')} {pw}")
            return pw
        return ans

    def _ask_choice_inline(self, prompt: str, options: list[str],
                           default: str = None) -> str:
        """Pick from a short list shown inline: [a / b / c]."""
        opts_str = " / ".join(
            bold(o) if o == default else o for o in options
        )
        while True:
            ans = input(f"  {cyan('?')} {prompt} [{opts_str}]: ").strip().lower()
            if not ans and default:
                return default
            match = next((o for o in options if o.lower() == ans), None)
            if match:
                return match
            print(f"    {red('Choose one of: ' + ', '.join(options))}")

    def _ask_from_options(self, prompt: str, options: list[str]) -> str:
        """Pick one option from a numbered list."""
        for i, o in enumerate(options, 1):
            print(f"      [{i}] {o}")
        while True:
            ans = input(f"  {cyan('?')} {prompt}: ").strip()
            try:
                idx = int(ans)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            except ValueError:
                if ans in options:
                    return ans
            print(f"    {red(f'Enter a number 1–{len(options)} or the exact name.')}")

    def _ask_from_checklist(self, options: list[str], label: str) -> list[str]:
        """Show each option as Y/N — returns list of selected."""
        selected = []
        for opt in options:
            if self._ask_yn(f"  {label}: {bold(opt)}?", False):
                selected.append(opt)
        return selected

    def _ask_main_menu(self) -> int:
        opts = [
            ("1", "Create new integration from scratch",
             "Guided: service → EP design → cluster objects — no flags needed"),
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

    # ══════════════════════════════════════════════════════════════════════════
    # DISPLAY HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _banner(self):
        print()
        print(bold("  ╔══════════════════════════════════════════════════╗"))
        print(bold("  ║    Solace Cloud Automation — Interactive Wizard  ║"))
        print(bold("  ╚══════════════════════════════════════════════════╝"))
        print()
        print(f"  Active service : {cyan(self.ctx.service_id or '(none)')}")
        print(f"  VPN            : {cyan(self.ctx.vpn_name   or '(none)')}")
        print(f"  Token          : {'set ✅' if self.ctx.token else red('NOT SET ❌')}")
        print()

    def _section(self, title: str):
        print(f"\n{bold('═'*62)}")
        print(f"  {bold(cyan(title))}")
        print(f"{'═'*62}\n")

    def _header(self, title: str):
        pad = max(0, 52 - len(title))
        print(f"\n  {bold('── ' + title + ' ' + '─' * pad)}")

    def _print_summary(self, cfg: dict, label: str = ""):
        ep  = cfg.get("eventPortal", {})
        cm  = cfg.get("clusterManagement", {})
        svc = cfg.get("service", {})
        tag = f"[{label}]  " if label else ""
        print(f"\n  {bold(tag + 'Summary:')}")
        print(f"    Service     : {svc.get('name','')}  "
              f"({svc.get('datacenterId','')})")
        print(f"    EP domain   : {ep.get('domainName', '—')}")
        schemas = [s['name'] for s in ep.get('schemas', [])]
        events  = [e['name'] for e in ep.get('events', [])]
        apps    = [a['name'] for a in ep.get('applications', [])]
        profs   = [p['name'] for p in cm.get('clientProfiles', [])]
        queues  = [q['name'] for q in cm.get('queues', [])]
        rdps    = [r['name'] for r in cm.get('restDeliveryPoints', [])]
        print(f"    Schemas     : {', '.join(schemas)  or '—'}")
        print(f"    Events      : {', '.join(events)   or '—'}")
        print(f"    Applications: {', '.join(apps)     or '—'}")
        print(f"    Profiles    : {', '.join(profs)    or '—'}")
        print(f"    Queues      : {', '.join(queues)   or '—'}")
        print(f"    RDPs        : {', '.join(rdps)     or '—'}")

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITY
    # ══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _replace_topic_prefix(cfg: dict, old: str, new: str) -> dict:
        """Replace topic prefix in event topics, ACL exceptions, queue subscriptions."""
        import copy
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
