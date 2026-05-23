#!/usr/bin/env python3
"""
solace.py — Solace Cloud Automation CLI
========================================
Single entry point for all Solace Cloud API operations.

USAGE
-----
  python3 solace.py <group> <command> [options]

GROUPS
------
  context   — show/set active token & service
  service   — Solace Cloud messaging services
  dc        — datacenters & service types
  domain    — Event Portal application domains
  schema    — Event Portal schemas & versions
  event     — Event Portal events & versions
  app       — Event Portal applications & versions
  cluster   — Broker cluster objects (credentials, queues, RDP)
  provision — Full orchestration from a JSON config file

QUICK START
-----------
  export SOLACE_API_TOKEN=<your-token>
  python3 solace.py context show
  python3 solace.py service list
  python3 solace.py service datacenters                          # list available datacenters
  python3 solace.py service create --name my-svc --datacenter <dc-id> --type <type-id> --class <class-id>
  python3 solace.py service use <service-id>
  python3 solace.py domain create --name MyDomain
  python3 solace.py provision run --config config/dev/service.json
"""

import argparse
import json
import logging
import os
import sys

# ── make src importable ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from context import Context
from client  import SolaceClient, SolaceError
from api.cloud_svc    import CloudServiceAPI
from api.event_portal import EventPortalAPI
from api.semp         import SempAPI
from workflows.provision import Provisioner, load_config
from workflows.exporter  import Exporter
from workflows.cloner    import Cloner
from workflows.wizard    import InteractiveWizard

# ── logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── output helpers ─────────────────────────────────────────────────────────────
def _print(obj, indent: int = 2):
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=indent))
    else:
        print(obj)

def _table(rows: list[dict], cols: list[str]):
    if not rows:
        print("  (no results)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = "  " + "  ".join(c.ljust(widths[c]) for c in cols)
    sep    = "  " + "  ".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print("  " + "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))

def _ok(msg: str):
    print(f"\n✅  {msg}\n")

def _fail(msg: str):
    print(f"\n❌  {msg}\n", file=sys.stderr)
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT
# ══════════════════════════════════════════════════════════════════════════════
def cmd_context(args, ctx: Context, _):
    if args.context_cmd == "show":
        print("\n── Active Context ────────────────────────────────")
        print(ctx.summary())
        print()

    elif args.context_cmd == "set-token":
        ctx.set_token(args.token)
        ctx.save()
        _ok(f"Token saved to .solace-context.json")

    elif args.context_cmd == "clear":
        Context({}).save()
        _ok("Context cleared")


# ══════════════════════════════════════════════════════════════════════════════
# DATACENTERS & SERVICE TYPES
# ══════════════════════════════════════════════════════════════════════════════
def cmd_dc(args, ctx: Context, cloud: CloudServiceAPI):
    if args.dc_cmd == "list":
        dcs = cloud.list_datacenters(service_class=args.service_class)
        _table(dcs, ["id", "displayName", "provider", "continent"])

    elif args.dc_cmd == "types":
        for st in cloud.list_service_types():
            print(f"\n  serviceTypeId : {st['id']}  ({st['serviceTypeName']})")
            for sc in st.get("serviceClasses", []):
                print(f"    serviceClassId : {sc['id']}  — {sc['serviceClassName']}")


# ══════════════════════════════════════════════════════════════════════════════
# SERVICES
# ══════════════════════════════════════════════════════════════════════════════
def cmd_service(args, ctx: Context, cloud: CloudServiceAPI):
    if args.svc_cmd == "list":
        svcs = cloud.list_services()
        _table(svcs, ["serviceId", "name", "datacenterId", "serviceClassId",
                       "creationState", "adminState"])

    elif args.svc_cmd == "info":
        sid = args.id or ctx.service_id
        if not sid:
            _fail("Provide --id or run 'service use' first")
        svc = cloud.get_service(sid)
        creds = cloud.extract_semp_creds(svc)
        print(json.dumps({**{k: svc.get(k) for k in
                             ["serviceId","name","datacenterId","serviceClassId",
                              "creationState","msgVpnName"]}, **creds}, indent=2))

    elif args.svc_cmd == "create":
        svc = cloud.create_service(
            name          = args.name,
            service_type  = args.type,
            service_class = getattr(args, "class"),   # 'class' is a keyword
            datacenter    = args.datacenter,
        )
        print(f"\n  serviceId    : {svc.get('serviceId')}")
        print(f"  creationState: {svc.get('creationState')}")
        print(f"\n  → Run: python3 solace.py service use {svc.get('serviceId')}\n")

    elif args.svc_cmd == "wait":
        sid = args.id or ctx.service_id
        if not sid:
            _fail("Provide --id")
        svc = cloud.wait_for_service(sid)
        creds = cloud.extract_semp_creds(svc)
        print(f"\n  ✅ Service ready")
        print(f"  brokerHost   : {creds['brokerHost']}")
        print(f"  sempBaseUrl  : {creds['sempBaseUrl']}")
        print(f"\n  → Run: python3 solace.py service use {sid}\n")

    elif args.svc_cmd == "use":
        sid  = args.id
        svc  = cloud.get_service(sid)
        creds = cloud.extract_semp_creds(svc)
        ctx.set_service(
            service_id = sid,
            vpn_name   = creds["vpnName"],
            semp_base  = creds["sempBaseUrl"],
            semp_user  = creds["sempUsername"],
            semp_pass  = creds["sempPassword"],
        )
        ctx.save()
        print(f"\n  ✅ Active service set to: {svc.get('name')} ({sid})")
        print(f"  vpnName    : {creds['vpnName']}")
        print(f"  sempBaseUrl: {creds['sempBaseUrl']}\n")

    elif args.svc_cmd == "delete":
        cloud.delete_service(args.id)
        _ok(f"Service {args.id} deleted")

    elif args.svc_cmd == "export":
        sid = args.id or ctx.service_id
        if not sid:
            _fail("Provide --id or run 'service use' first")
        out = args.out or f"config/{args.country.lower() if args.country else 'export'}/service.json"
        exp = Exporter(ctx)
        exp.export_to_file(
            output_path  = out,
            service_id   = sid,
            domain_name  = args.domain,
            country_code = args.country,
        )
        _ok(f"Exported → {out}")


# ══════════════════════════════════════════════════════════════════════════════
# DOMAINS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_domain(args, ctx: Context, ep: EventPortalAPI):
    if args.domain_cmd == "list":
        _table(ep.list_domains(), ["id", "name", "description"])

    elif args.domain_cmd == "get":
        _print(ep.get_domain(args.id))

    elif args.domain_cmd == "create":
        d = ep.create_domain(name=args.name, description=args.description or "")
        _ok(f"Domain created  id={d['id']}  name={d['name']}")

    elif args.domain_cmd == "update":
        fields = {}
        if args.name:        fields["name"]        = args.name
        if args.description: fields["description"] = args.description
        d = ep.update_domain(args.id, **fields)
        _ok(f"Domain updated id={args.id}")

    elif args.domain_cmd == "delete":
        ep.delete_domain(args.id)
        _ok(f"Domain {args.id} deleted")


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_schema(args, ctx: Context, ep: EventPortalAPI):
    if args.schema_cmd == "list":
        _table(ep.list_schemas(domain_id=args.domain_id), ["id", "name", "schemaType"])

    elif args.schema_cmd == "get":
        _print(ep.get_schema(args.id))

    elif args.schema_cmd == "create":
        content = "{}"
        if args.file:
            content = open(args.file).read()
        elif args.content:
            content = args.content

        s = ep.create_schema(
            name        = args.name,
            domain_id   = args.domain_id,
            schema_type = args.type or "jsonSchema",
        )
        sv = ep.create_schema_version(
            schema_id   = s["id"],
            version     = args.version or "1.0.0",
            content     = content,
            description = args.description or "",
        )
        _ok(f"Schema created  schema_id={s['id']}  version_id={sv['id']}")

    elif args.schema_cmd == "delete":
        ep.delete_schema(args.id)
        _ok(f"Schema {args.id} deleted")

    elif args.schema_cmd == "versions":
        _table(ep.list_schema_versions(schema_id=args.schema_id),
               ["id", "version", "displayName"])

    elif args.schema_cmd == "promote":
        r = ep.update_schema_version_state(args.id, state=args.state or "released")
        _ok(f"Schema version {args.id} promoted to {args.state}")


# ══════════════════════════════════════════════════════════════════════════════
# EVENTS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_event(args, ctx: Context, ep: EventPortalAPI):
    if args.event_cmd == "list":
        _table(ep.list_events(domain_id=args.domain_id), ["id", "name"])

    elif args.event_cmd == "get":
        _print(ep.get_event(args.id))

    elif args.event_cmd == "create":
        e = ep.create_event(
            name        = args.name,
            domain_id   = args.domain_id,
            description = args.description or "",
        )
        ev = ep.create_event_version(
            event_id          = e["id"],
            version           = args.version or "1.0.0",
            topic             = args.topic,
            schema_version_id = args.schema_version_id,
            description       = args.description or "",
        )
        _ok(f"Event created  event_id={e['id']}  version_id={ev['id']}  topic={args.topic}")

    elif args.event_cmd == "delete":
        ep.delete_event(args.id)
        _ok(f"Event {args.id} deleted")

    elif args.event_cmd == "versions":
        _table(ep.list_event_versions(event_id=args.event_id),
               ["id", "version", "displayName"])

    elif args.event_cmd == "promote":
        ep.update_event_version_state(args.id, state=args.state or "released")
        _ok(f"Event version {args.id} promoted to {args.state}")


# ══════════════════════════════════════════════════════════════════════════════
# APPLICATIONS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_app(args, ctx: Context, ep: EventPortalAPI):
    if args.app_cmd == "list":
        _table(ep.list_applications(domain_id=args.domain_id),
               ["id", "name", "applicationType"])

    elif args.app_cmd == "get":
        _print(ep.get_application(args.id))

    elif args.app_cmd == "create":
        a = ep.create_application(
            name        = args.name,
            domain_id   = args.domain_id,
            app_type    = args.type or "standard",
            description = args.description or "",
        )
        av = ep.create_application_version(
            app_id      = a["id"],
            version     = args.version or "1.0.0",
            produces    = args.produces or [],
            consumes    = args.consumes or [],
            description = args.description or "",
        )
        _ok(f"App created  app_id={a['id']}  version_id={av['id']}")

    elif args.app_cmd == "delete":
        ep.delete_application(args.id)
        _ok(f"Application {args.id} deleted")

    elif args.app_cmd == "versions":
        _table(ep.list_application_versions(app_id=args.app_id),
               ["id", "version", "displayName"])

    elif args.app_cmd == "asyncapi":
        spec = ep.get_asyncapi(args.version_id, fmt=args.format or "json")
        _print(spec)

    elif args.app_cmd == "promote":
        ep.update_application_version_state(args.id, state=args.state or "released")
        _ok(f"App version {args.id} promoted to {args.state}")


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER MANAGEMENT  (SEMP)
# ══════════════════════════════════════════════════════════════════════════════
def cmd_cluster(args, ctx: Context, semp: SempAPI):
    sub = args.cluster_cmd

    # ── client-profile ─────────────────────────────────────────────────────
    if sub == "profile-list":
        _table(semp.list_client_profiles(), ["clientProfileName"])

    elif sub == "profile-create":
        semp.create_client_profile(args.name)
        _ok(f"Client profile '{args.name}' created")

    elif sub == "profile-delete":
        semp.delete_client_profile(args.name)
        _ok(f"Client profile '{args.name}' deleted")

    # ── acl profile ────────────────────────────────────────────────────────
    elif sub == "acl-list":
        _table(semp.list_acl_profiles(), ["aclProfileName"])

    elif sub == "acl-create":
        semp.create_acl_profile(
            name             = args.name,
            publish_default  = args.publish_default  or "disallow",
            subscribe_default = args.subscribe_default or "disallow",
        )
        _ok(f"ACL profile '{args.name}' created")

    elif sub == "acl-add-pub":
        semp.add_publish_exception(args.name, args.topic)
        _ok(f"Publish exception '{args.topic}' added to '{args.name}'")

    elif sub == "acl-add-sub":
        semp.add_subscribe_exception(args.name, args.topic)
        _ok(f"Subscribe exception '{args.topic}' added to '{args.name}'")

    elif sub == "acl-delete":
        semp.delete_acl_profile(args.name)
        _ok(f"ACL profile '{args.name}' deleted")

    # ── client username ────────────────────────────────────────────────────
    elif sub == "user-list":
        _table(semp.list_client_usernames(), ["clientUsername", "enabled", "clientProfileName"])

    elif sub == "user-create":
        semp.create_client_username(
            name           = args.name,
            password       = args.password,
            client_profile = args.client_profile,
            acl_profile    = args.acl_profile,
        )
        _ok(f"Client username '{args.name}' created")

    elif sub == "user-delete":
        semp.delete_client_username(args.name)
        _ok(f"Client username '{args.name}' deleted")

    # ── queues ─────────────────────────────────────────────────────────────
    elif sub == "queue-list":
        _table(semp.list_queues(), ["queueName", "accessType", "owner", "ingressEnabled"])

    elif sub == "queue-create":
        semp.create_queue(
            name        = args.name,
            owner       = args.owner,
            access_type = args.access_type or "non-exclusive",
        )
        _ok(f"Queue '{args.name}' created")

    elif sub == "queue-subscribe":
        semp.add_queue_subscription(args.queue, args.topic)
        _ok(f"Topic '{args.topic}' subscribed on queue '{args.queue}'")

    elif sub == "queue-unsubscribe":
        semp.remove_queue_subscription(args.queue, args.topic)
        _ok(f"Topic '{args.topic}' removed from queue '{args.queue}'")

    elif sub == "queue-subs-list":
        _table(semp.list_queue_subscriptions(args.queue), ["subscriptionTopic"])

    elif sub == "queue-delete":
        semp.delete_queue(args.name)
        _ok(f"Queue '{args.name}' deleted")

    # ── RDP ────────────────────────────────────────────────────────────────
    elif sub == "rdp-list":
        _table(semp.list_rdps(), ["restDeliveryPointName", "enabled"])

    elif sub == "rdp-create":
        semp.create_rdp(args.name, client_profile=args.client_profile or "default")
        _ok(f"RDP '{args.name}' created")

    elif sub == "rdp-add-consumer":
        semp.create_rest_consumer(
            rdp  = args.rdp,
            name = args.name,
            host = args.host,
            port = int(args.port or 443),
            tls  = not args.no_tls,
        )
        _ok(f"REST consumer '{args.name}' added to RDP '{args.rdp}'")

    elif sub == "rdp-bind-queue":
        semp.bind_queue_to_rdp(
            rdp         = args.rdp,
            queue       = args.queue,
            post_target = args.path or "/",
        )
        _ok(f"Queue '{args.queue}' bound to RDP '{args.rdp}'")

    elif sub == "rdp-consumer-list":
        _table(semp.list_rest_consumers(args.rdp),
               ["restConsumerName", "remoteHost", "remotePort", "tlsEnabled"])

    elif sub == "rdp-delete":
        semp.delete_rdp(args.name)
        _ok(f"RDP '{args.name}' deleted")

    # ── full status dump ───────────────────────────────────────────────────
    elif sub == "status":
        print("\n── Cluster Status ────────────────────────────────────")
        print(f"  VPN: {semp.vpn}\n")
        print("  Client Profiles:")
        for p in semp.list_client_profiles():
            if not p["clientProfileName"].startswith("#"):
                print(f"    {p['clientProfileName']}")
        print("  ACL Profiles:")
        for p in semp.list_acl_profiles():
            if not p["aclProfileName"].startswith("#"):
                print(f"    {p['aclProfileName']}")
        print("  Client Usernames:")
        for u in semp.list_client_usernames():
            if not u["clientUsername"].startswith("#"):
                print(f"    {u['clientUsername']}  enabled={u['enabled']}")
        print("  Queues:")
        for q in semp.list_queues():
            print(f"    {q['queueName']}  type={q['accessType']}")
        print("  REST Delivery Points:")
        for r in semp.list_rdps():
            print(f"    {r['restDeliveryPointName']}  enabled={r['enabled']}")
        print()


# ══════════════════════════════════════════════════════════════════════════════
# WIZARD
# ══════════════════════════════════════════════════════════════════════════════
def cmd_wizard(args, ctx: Context, _):
    w = InteractiveWizard(ctx)
    w.run(force_flow=getattr(args, "flow", None))


# ══════════════════════════════════════════════════════════════════════════════
# PROVISION
# ══════════════════════════════════════════════════════════════════════════════
def cmd_provision(args, ctx: Context, client: SolaceClient):
    sub = args.prov_cmd

    if sub == "run":
        p = Provisioner(ctx, dry_run=args.dry_run)
        p.run(
            config_path  = args.config,
            skip_ep      = args.skip_ep,
            skip_cluster = args.skip_cluster,
        )

    # ── clone ─────────────────────────────────────────────────────────────
    elif sub == "clone":
        import json
        source = json.loads(open(args.config).read())
        c      = Cloner()

        print("\n── Clone Preview ─────────────────────────────────────")
        # Show diff before applying
        preview = c.clone(
            source_config      = source,
            target_country     = args.to_country,
            datacenter         = args.datacenter,
            service_name       = args.service_name,
            service_id         = args.service_id,
            generate_passwords = not args.no_passwords,
        )
        print(Cloner.diff_summary(source, preview))

        out = args.out or f"config/{args.to_country.lower()}/service.json"
        from pathlib import Path
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(preview, indent=2))
        _ok(f"Clone written → {out}")

        if not args.dry_run:
            print(f"  → Run to provision:  python3 solace.py provision run --config {out}\n")

    # ── replicate (export + clone + provision in one shot) ────────────────
    elif sub == "replicate":
        import json
        cloud = CloudServiceAPI(client)

        # Step 1 — export source service
        print(f"\n── Step 1/4  Export source service ({args.from_service}) ──────")
        exp      = Exporter(ctx)
        src_data = exp.export(
            service_id   = args.from_service,
            country_code = args.from_country,
        )

        # Step 2 — clone config to target country
        print(f"\n── Step 2/4  Clone {args.from_country} → {args.to_country} ───────────")
        c       = Cloner()
        cloned  = c.clone(
            source_config  = src_data,
            target_country = args.to_country,
            datacenter     = args.datacenter,
            service_name   = args.service_name or None,   # None → derived from source by substitution
        )

        print("\n── Clone Diff ─────────────────────────────────────────")
        print(Cloner.diff_summary(src_data, cloned))

        # Optionally write clone to file
        out = args.out or f"config/{args.to_country.lower()}/service.json"
        from pathlib import Path
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(cloned, indent=2))
        logger.info("Clone config saved → %s", out)

        if args.dry_run:
            _ok(f"Dry-run complete — clone config written to {out}")
            return

        # Step 3 — create new messaging service (unless --skip-create-service)
        if not args.skip_create_service:
            print(f"\n── Step 3/4  Create new messaging service ───────────────")
            svc_info = cloned.get("service", {})
            svc = cloud.create_service(
                name          = svc_info["name"],
                service_type  = svc_info.get("serviceTypeId")  or None,
                service_class = svc_info.get("serviceClassId") or None,
                datacenter    = svc_info["datacenterId"],
            )
            new_sid = svc.get("serviceId")
            print(f"  serviceId: {new_sid}  state: {svc.get('creationState')}")
            print("  Waiting for service to be ready ...")
            svc = cloud.wait_for_service(new_sid)
            creds = cloud.extract_semp_creds(svc)

            # Inject SEMP creds into context for provisioner
            ctx.set_service(
                service_id = new_sid,
                vpn_name   = creds["vpnName"],
                semp_base  = creds["sempBaseUrl"],
                semp_user  = creds["sempUsername"],
                semp_pass  = creds["sempPassword"],
            )
            ctx.save()

            # Inject real VPN name into cloned config
            cloned["service"]["serviceId"] = new_sid
            cloned["clusterManagement"]["vpnName"] = creds["vpnName"]
            # Refresh file with resolved VPN
            Path(out).write_text(json.dumps(cloned, indent=2))
            logger.info("Updated clone config with new serviceId + vpnName → %s", out)
        else:
            print("\n── Step 3/4  Skipped (--skip-create-service) ────────────")

        # Step 4 — provision
        print(f"\n── Step 4/4  Provision {args.to_country} ──────────────────────")
        p = Provisioner(ctx, dry_run=False)
        p.provision_event_portal(cloned)
        p.provision_cluster(cloned)
        _ok(f"Replication complete: {args.from_country} → {args.to_country}")


# ══════════════════════════════════════════════════════════════════════════════
# ARGUMENT PARSER
# ══════════════════════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="solace.py",
        description="Solace Cloud Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    root.add_argument("--debug", action="store_true", help="Enable debug logging")
    subs = root.add_subparsers(dest="group", required=True)

    # ── wizard ─────────────────────────────────────────────────────────────
    g = subs.add_parser("wizard",
                        help="Interactive guided wizard — no flags needed")
    g.add_argument("--flow", type=int, choices=[1,2,3,4],
                   help="Jump to a specific flow: 1=scratch 2=clone 3=EP-only 4=cluster-only")

    # ── context ────────────────────────────────────────────────────────────
    g = subs.add_parser("context", help="Manage active context")
    cs = g.add_subparsers(dest="context_cmd", required=True)
    cs.add_parser("show", help="Show current context")
    p = cs.add_parser("set-token", help="Set API token")
    p.add_argument("--token", required=True)
    cs.add_parser("clear", help="Clear context file")

    # ── dc ─────────────────────────────────────────────────────────────────
    g = subs.add_parser("dc", help="Datacenters & service types")
    ds = g.add_subparsers(dest="dc_cmd", required=True)
    p = ds.add_parser("list", help="List available datacenters")
    p.add_argument("--service-class", help="Filter by service class (e.g. developer)")
    ds.add_parser("types", help="List service types and classes")

    # ── service ────────────────────────────────────────────────────────────
    g = subs.add_parser("service", help="Solace Cloud messaging services")
    ss = g.add_subparsers(dest="svc_cmd", required=True)
    ss.add_parser("list", help="List all services")
    p = ss.add_parser("info", help="Get service details")
    p.add_argument("--id", help="Service ID (defaults to active service)")
    p = ss.add_parser("create", help="Create a new messaging service")
    p.add_argument("--name",       required=True,  help="Service name")
    p.add_argument("--datacenter", required=True,  help="Datacenter id — run 'python3 solace.py service datacenters' to list")
    p.add_argument("--type",       required=True,  help="Service type id (e.g. developer)")
    p.add_argument("--class",      dest="class_",  required=True, help="Service class id (e.g. developer)")
    p = ss.add_parser("wait", help="Wait for service to be ready")
    p.add_argument("--id", help="Service ID (defaults to active)")
    p = ss.add_parser("use", help="Set active service (auto-discovers SEMP creds)")
    p.add_argument("id", help="Service ID")
    p = ss.add_parser("delete", help="Delete a service")
    p.add_argument("--id", required=True)

    p = ss.add_parser("export", help="Export full service config to JSON (cluster + EP)")
    p.add_argument("--id",      help="Service ID (defaults to active service)")
    p.add_argument("--country", required=True, help="Country code to tag the export (e.g. AU, DE)")
    p.add_argument("--domain",  help="EP domain name to export (auto-detected from country code if omitted)")
    p.add_argument("--out",     help="Output file path (default: config/<country>/service.json)")

    # ── domain ─────────────────────────────────────────────────────────────
    g = subs.add_parser("domain", help="Event Portal application domains")
    ds = g.add_subparsers(dest="domain_cmd", required=True)
    ds.add_parser("list", help="List all domains")
    p = ds.add_parser("get", help="Get domain by ID")
    p.add_argument("--id", required=True)
    p = ds.add_parser("create", help="Create a new domain")
    p.add_argument("--name",        required=True)
    p.add_argument("--description", default="")
    p = ds.add_parser("update", help="Update a domain")
    p.add_argument("--id",          required=True)
    p.add_argument("--name")
    p.add_argument("--description")
    p = ds.add_parser("delete", help="Delete a domain")
    p.add_argument("--id", required=True)

    # ── schema ─────────────────────────────────────────────────────────────
    g = subs.add_parser("schema", help="Event Portal schemas")
    sch = g.add_subparsers(dest="schema_cmd", required=True)
    p = sch.add_parser("list", help="List schemas")
    p.add_argument("--domain-id")
    p = sch.add_parser("get", help="Get schema")
    p.add_argument("--id", required=True)
    p = sch.add_parser("create", help="Create schema + version")
    p.add_argument("--name",        required=True)
    p.add_argument("--domain-id",   required=True)
    p.add_argument("--type",        default="jsonSchema", help="jsonSchema|avro|protobuf|xmlSchema")
    p.add_argument("--version",     default="1.0.0")
    p.add_argument("--file",        help="Path to schema file (JSON/Avro/etc.)")
    p.add_argument("--content",     help="Schema content inline (JSON string)")
    p.add_argument("--description", default="")
    p = sch.add_parser("delete", help="Delete schema")
    p.add_argument("--id", required=True)
    p = sch.add_parser("versions", help="List schema versions")
    p.add_argument("--schema-id", required=True)
    p = sch.add_parser("promote", help="Promote schema version state")
    p.add_argument("--id",    required=True)
    p.add_argument("--state", default="released",
                   choices=["draft","released","deprecated","retired"])

    # ── event ──────────────────────────────────────────────────────────────
    g = subs.add_parser("event", help="Event Portal events")
    ev = g.add_subparsers(dest="event_cmd", required=True)
    p = ev.add_parser("list", help="List events")
    p.add_argument("--domain-id")
    p = ev.add_parser("get", help="Get event")
    p.add_argument("--id", required=True)
    p = ev.add_parser("create", help="Create event + version")
    p.add_argument("--name",              required=True)
    p.add_argument("--domain-id",         required=True)
    p.add_argument("--topic",             required=True, help="e.g. mars/orders/{orderId}/created")
    p.add_argument("--schema-version-id", help="Schema version ID to link")
    p.add_argument("--version",           default="1.0.0")
    p.add_argument("--description",       default="")
    p = ev.add_parser("delete", help="Delete event")
    p.add_argument("--id", required=True)
    p = ev.add_parser("versions", help="List event versions")
    p.add_argument("--event-id", required=True)
    p = ev.add_parser("promote", help="Promote event version")
    p.add_argument("--id",    required=True)
    p.add_argument("--state", default="released",
                   choices=["draft","released","deprecated","retired"])

    # ── app ────────────────────────────────────────────────────────────────
    g = subs.add_parser("app", help="Event Portal applications")
    ap = g.add_subparsers(dest="app_cmd", required=True)
    p = ap.add_parser("list", help="List applications")
    p.add_argument("--domain-id")
    p = ap.add_parser("get", help="Get application")
    p.add_argument("--id", required=True)
    p = ap.add_parser("create", help="Create application + version")
    p.add_argument("--name",        required=True)
    p.add_argument("--domain-id",   required=True)
    p.add_argument("--type",        default="standard", choices=["standard","connector"])
    p.add_argument("--version",     default="1.0.0")
    p.add_argument("--produces",    nargs="*", metavar="EVENT_VERSION_ID",
                   help="Event version IDs this app publishes")
    p.add_argument("--consumes",    nargs="*", metavar="EVENT_VERSION_ID",
                   help="Event version IDs this app subscribes to")
    p.add_argument("--description", default="")
    p = ap.add_parser("delete", help="Delete application")
    p.add_argument("--id", required=True)
    p = ap.add_parser("versions", help="List app versions")
    p.add_argument("--app-id", required=True)
    p = ap.add_parser("asyncapi", help="Export AsyncAPI spec")
    p.add_argument("--version-id", required=True)
    p.add_argument("--format", default="json", choices=["json","yaml"])
    p = ap.add_parser("promote", help="Promote app version")
    p.add_argument("--id",    required=True)
    p.add_argument("--state", default="released",
                   choices=["draft","released","deprecated","retired"])

    # ── cluster ────────────────────────────────────────────────────────────
    g = subs.add_parser("cluster", help="Broker cluster objects (credentials, queues, RDP)")
    cl = g.add_subparsers(dest="cluster_cmd", required=True)

    cl.add_parser("status", help="Show all cluster objects")

    # client profiles
    cl.add_parser("profile-list", help="List client profiles")
    p = cl.add_parser("profile-create", help="Create client profile")
    p.add_argument("--name", required=True)
    p = cl.add_parser("profile-delete", help="Delete client profile")
    p.add_argument("--name", required=True)

    # acl
    cl.add_parser("acl-list", help="List ACL profiles")
    p = cl.add_parser("acl-create", help="Create ACL profile")
    p.add_argument("--name",              required=True)
    p.add_argument("--publish-default",   default="disallow", choices=["allow","disallow"])
    p.add_argument("--subscribe-default", default="disallow", choices=["allow","disallow"])
    p = cl.add_parser("acl-add-pub",  help="Add publish topic exception")
    p.add_argument("--name",  required=True)
    p.add_argument("--topic", required=True)
    p = cl.add_parser("acl-add-sub",  help="Add subscribe topic exception")
    p.add_argument("--name",  required=True)
    p.add_argument("--topic", required=True)
    p = cl.add_parser("acl-delete", help="Delete ACL profile")
    p.add_argument("--name", required=True)

    # usernames
    cl.add_parser("user-list", help="List client usernames")
    p = cl.add_parser("user-create", help="Create client username")
    p.add_argument("--name",           required=True)
    p.add_argument("--password",       required=True)
    p.add_argument("--client-profile", required=True)
    p.add_argument("--acl-profile",    required=True)
    p = cl.add_parser("user-delete", help="Delete client username")
    p.add_argument("--name", required=True)

    # queues
    cl.add_parser("queue-list", help="List queues")
    p = cl.add_parser("queue-create", help="Create queue")
    p.add_argument("--name",        required=True)
    p.add_argument("--owner",       help="Client username owner")
    p.add_argument("--access-type", default="non-exclusive", choices=["exclusive","non-exclusive"])
    p = cl.add_parser("queue-subscribe", help="Add topic subscription to queue")
    p.add_argument("--queue", required=True)
    p.add_argument("--topic", required=True)
    p = cl.add_parser("queue-unsubscribe", help="Remove topic subscription from queue")
    p.add_argument("--queue", required=True)
    p.add_argument("--topic", required=True)
    p = cl.add_parser("queue-subs-list", help="List queue subscriptions")
    p.add_argument("--queue", required=True)
    p = cl.add_parser("queue-delete", help="Delete queue")
    p.add_argument("--name", required=True)

    # rdp
    cl.add_parser("rdp-list", help="List REST Delivery Points")
    p = cl.add_parser("rdp-create", help="Create REST Delivery Point")
    p.add_argument("--name",           required=True)
    p.add_argument("--client-profile", default="default")
    p = cl.add_parser("rdp-add-consumer", help="Add REST consumer to RDP")
    p.add_argument("--rdp",    required=True)
    p.add_argument("--name",   required=True)
    p.add_argument("--host",   required=True)
    p.add_argument("--port",   default="443")
    p.add_argument("--no-tls", action="store_true")
    p = cl.add_parser("rdp-bind-queue", help="Bind queue to RDP")
    p.add_argument("--rdp",   required=True)
    p.add_argument("--queue", required=True)
    p.add_argument("--path",  default="/", help="HTTP POST target path")
    p = cl.add_parser("rdp-consumer-list", help="List REST consumers of an RDP")
    p.add_argument("--rdp", required=True)
    p = cl.add_parser("rdp-delete", help="Delete RDP")
    p.add_argument("--name", required=True)

    # ── provision ──────────────────────────────────────────────────────────
    g = subs.add_parser("provision", help="Full orchestration from a config file")
    ps = g.add_subparsers(dest="prov_cmd", required=True)

    # provision run
    p = ps.add_parser("run", help="Run full provisioning from config file")
    p.add_argument("--config",       required=True, help="Path to service JSON config")
    p.add_argument("--dry-run",      action="store_true")
    p.add_argument("--skip-ep",      action="store_true")
    p.add_argument("--skip-cluster", action="store_true")

    # provision clone  — substitute country code, produce a new config
    p = ps.add_parser("clone",
                      help="Clone a config to a new country (substitutes country code in all names/topics)")
    p.add_argument("--config",       required=True,
                   help="Source config file (must have sourceCountry set, i.e. exported with --country)")
    p.add_argument("--to-country",   required=True,
                   help="Target country code (e.g. SG, DE, AU)")
    p.add_argument("--datacenter",   help="Target datacenter ID (e.g. aks-australiaeast)")
    p.add_argument("--service-name", help="Override service name in clone")
    p.add_argument("--service-id",   help="Use an existing service ID (skips service creation)")
    p.add_argument("--out",          help="Output file path (default: config/<country>/service.json)")
    p.add_argument("--dry-run",      action="store_true",
                   help="Show diff without writing file")
    p.add_argument("--no-passwords", action="store_true",
                   help="Do not auto-generate passwords (leave blank for manual fill)")

    # provision replicate — full automation: export → clone → create service → provision
    p = ps.add_parser("replicate",
                      help="Full end-to-end: export source country → clone → create new service → provision")
    p.add_argument("--from-service", required=True,
                   help="Source service ID to export from")
    p.add_argument("--from-country", required=True,
                   help="Source country code (e.g. AU)")
    p.add_argument("--to-country",   required=True,
                   help="Target country code (e.g. SG)")
    p.add_argument("--datacenter",   required=True,
                   help="Datacenter for new service (e.g. aks-australiaeast)")
    p.add_argument("--service-name", help="Name for the new messaging service")
    p.add_argument("--out",          help="Where to save the cloned config (default: config/<country>/service.json)")
    p.add_argument("--dry-run",      action="store_true",
                   help="Export + clone only, do not create service or provision")
    p.add_argument("--skip-create-service", action="store_true",
                   help="Skip creating a new service (use active context's service)")

    return root


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    ctx = Context.load()
    if not ctx.token:
        _fail("No API token. Set SOLACE_API_TOKEN env var or run:\n  python3 solace.py context set-token --token <token>")

    client = SolaceClient.from_context(ctx.as_dict())
    cloud  = CloudServiceAPI(client)
    ep     = EventPortalAPI(client)
    semp   = SempAPI(client, ctx.vpn_name) if ctx.vpn_name else None

    try:
        if args.group == "wizard":
            cmd_wizard(args, ctx, client)

        elif args.group == "context":
            cmd_context(args, ctx, None)

        elif args.group == "dc":
            cmd_dc(args, ctx, cloud)

        elif args.group == "service":
            # fix argparse 'class' keyword conflict
            if hasattr(args, "class_"):
                setattr(args, "class", args.class_)
            cmd_service(args, ctx, cloud)

        elif args.group == "domain":
            cmd_domain(args, ctx, ep)

        elif args.group == "schema":
            cmd_schema(args, ctx, ep)

        elif args.group == "event":
            cmd_event(args, ctx, ep)

        elif args.group == "app":
            cmd_app(args, ctx, ep)

        elif args.group == "cluster":
            if not semp:
                ctx.require_semp()
            cmd_cluster(args, ctx, semp)

        elif args.group == "provision":
            cmd_provision(args, ctx, client)

    except SolaceError as e:
        _fail(str(e))
    except KeyboardInterrupt:
        print("\nAborted.")


if __name__ == "__main__":
    main()
