# solace-automation

Python CLI for **full Solace Cloud provisioning automation** — covering the Event Portal Designer API, Cloud Mission Control API, and SEMP v2 Config API.  
No MCP, no AI — pure Python scripts + REST APIs.

---

## Two Ways to Provision

| | Approach 1 — Interactive Wizard | Approach 2 — Export → Clone → Provision |
|---|---|---|
| **Best for** | Net-new integrations with no existing template | Rolling out an existing country's config to a new country |
| **How it works** | Wizard prompts for every value; live API pickers for datacenters + service types | Export live config from source → substitute country code → provision to new service |
| **Command** | `python3 solace.py wizard` | `python3 solace.py service export` + `provision replicate` |
| **Config saved?** | No (objects created directly) | Yes — `config/<country>/service.json` |

---

## Prerequisites

```bash
# Python 3.9+, one dependency
pip3 install requests

# Set your Solace Cloud API token
export SOLACE_API_TOKEN="eyJhbGci..."      # or use: python3 solace.py context set-token --token <token>

# Confirm token is loaded
python3 solace.py context show
```

---

## Project Structure

```
solace-automation/
├── solace.py                        ← Main CLI entry point  (all commands)
├── src/
│   ├── client.py                    ← Dual-auth HTTP client (Bearer + Basic)
│   ├── context.py                   ← Persisted context  (.solace-context.json)
│   ├── api/
│   │   ├── cloud_svc.py             ← Cloud Mission Control API  (services, datacenters)
│   │   ├── event_portal.py          ← Event Portal Designer API  (domains, schemas, events, apps)
│   │   └── semp.py                  ← SEMP v2 Config API  (credentials, queues, RDP)
│   └── workflows/
│       ├── wizard.py                ← Interactive guided wizard  (Flows 1–4)
│       ├── exporter.py              ← Live config export from a service
│       ├── cloner.py                ← Country-code substitution + password generation
│       └── provision.py             ← Full orchestration  (EP + Cluster)
├── config/
│   ├── template/
│   │   └── country-template.json    ← Reusable template with {{COUNTRY}} placeholders
│   ├── dev-export/
│   │   └── service.json             ← Live export from DEV service
│   └── <country>/
│       └── service.json             ← Per-country config (export or clone output)
├── .github/workflows/
│   ├── deploy-dev.yml               ← Auto-deploy on push to main
│   ├── deploy-test.yml              ← Deploy with environment approval gate
│   └── deploy-prod.yml              ← Manual trigger + approval gate
└── .gitignore                       ← Excludes .solace-context.json, .env, __pycache__
```

---

## Approach 1 — Interactive Wizard

The wizard prompts for every value, fetches live options from the API (datacenters, service types), and creates everything interactively in one session.

### Start the wizard

```bash
python3 solace.py wizard
```

You will see a menu:

```
  ╔══════════════════════════════════════════════════╗
  ║    Solace Cloud Automation — Interactive Wizard  ║
  ╚══════════════════════════════════════════════════╝

  Active service : (none)
  VPN            : (none)
  Token          : set ✅

What would you like to do?

  [1] Create new integration from scratch
       Guided: service → EP design → cluster objects — no flags needed
  [2] Clone existing country → new country
       Export live config, substitute country, customise, provision
  [3] Event Portal design objects only
       Add domain / schema / event / application
  [4] Cluster / broker objects only
       Add profile / ACL / username / queue / RDP

  ? Enter choice [1-4]:
```

You can also jump directly to a flow:

```bash
python3 solace.py wizard --flow 1     # Create from scratch
python3 solace.py wizard --flow 2     # Clone country
python3 solace.py wizard --flow 3     # EP objects only
python3 solace.py wizard --flow 4     # Cluster objects only
```

---

### Flow 1 — Create New Integration From Scratch

**What it does:** Walks you through every step — messaging service, Event Portal domain, schemas, events, applications, client profile, ACL, queue, and REST delivery point.

**Step-by-step walkthrough:**

```
Step 1 / 6  —  Project Identity
────────────────────────────────
  The prefix is used to generate all object names (queues, profiles, etc.)
  ? Project / application prefix: acme
  ? Environment / country label (e.g. AU, US, DEV, PROD): AU

Step 2 / 6  —  Messaging Service
────────────────────────────────
  ? Use the service already active in context? [y/N]: n
  ? Service name [acme-AU]: acme-automation-au

  Available datacenters: (fetching from API…)
    [ 1]  aks-australiaeast          azure  Australia East
    [ 2]  aks-eastus                 azure  East US
    [ 3]  aks-germanywestcentral     azure  Germany West Central
    ...
  ? Enter number or datacenter ID: 1
  ✓ Datacenter: aks-australiaeast

  Available service types: (fetching from API…)
    [ 1]  Enterprise / Enterprise-250-Nano
    [ 2]  Enterprise / Enterprise-1K
    [ 3]  Developer  / Developer
    ...
  ? Enter number: 3
  ✓ Service type: Developer / Developer

  Creating service …
  serviceId=abc123  state=pending
  Waiting for service to be ready (~1 min) …
  ✓ Service ready  VPN=msgvpn-abc123

Step 3 / 6  —  Event Portal Domain
────────────────────────────────
  ? Application domain name [AcmeAU]: AcmeAU
  ? Description: Acme AU integration domain
  ✓ Domain 'AcmeAU'  id=d-xxx

Step 4 / 6  —  Schemas
────────────────────────────────
  ? Add a schema? [Y/n]: y
    ? Schema name: OrderPayloadSchema
    ? Schema type [jsonSchema / avro / protobuf / xmlSchema]: jsonSchema
    ? Version [1.0.0]:
    ? Schema content file path (Enter = empty schema): schemas/order.json
  ✓ Schema 'OrderPayloadSchema'  version_id=sv-xxx

  ? Add a schema? [Y/n]: n

Step 4 / 6  —  Events
────────────────────────────────
  ? Add an event? [Y/n]: y
    ? Event name: OrderCreated
    ? Topic string (e.g. acme/au/orders/{orderId}/created): acme/au/orders/{orderId}/created
    ? Version [1.0.0]:
    ? Link to a schema? (available: ['OrderPayloadSchema']) [Y/n]: y
      [1] OrderPayloadSchema
    ? Which schema?: 1
  ✓ Event 'OrderCreated'  topic=acme/au/orders/{orderId}/created

  ? Add an event? [Y/n]: n

Step 5 / 6  —  Applications
────────────────────────────────
  ? Add an application? [Y/n]: y
    ? Application name: AcmeSourceSystem-AU
    ? Does this app PRODUCE (publish) events? [y/N]: y
      Produces: OrderCreated? [y/N]: y
    ? Does this app CONSUME (subscribe) events? [y/N]: n
  ✓ App 'AcmeSourceSystem-AU'  produces=['OrderCreated']

  ? Add an application? [Y/n]: y
    ? Application name: AcmeTargetSystem-AU
    ? Does this app PRODUCE (publish) events? [y/N]: n
    ? Does this app CONSUME (subscribe) events? [y/N]: y
      Consumes: OrderCreated? [y/N]: y
  ✓ App 'AcmeTargetSystem-AU'  consumes=['OrderCreated']

  ? Add an application? [Y/n]: n

Step 6 / 6  —  Cluster / Broker Objects
────────────────────────────────
  ? Create a Client Profile? [Y/n]: y
    ? Profile name [acme-au-profile]:
  ✓ Client profile 'acme-au-profile'

  ? Create an ACL Profile? [Y/n]: y
    ? ACL name [acme-au-acl]:
    ? Publish default action [disallow / allow]: disallow
    ? Subscribe default action [disallow / allow]: disallow
    ? Add publish topic exception? [Y/n]: y
        ? Topic (e.g. acme/au/>): acme/au/>
    ? Add subscribe topic exception? [Y/n]: y
        ? Topic: acme/au/>
    ? Add subscribe topic exception? [Y/n]: n
  ✓ ACL profile 'acme-au-acl'

  ? Create a Client Username? [Y/n]: y
    ? Username [acme-au-user]:
    ? Password (Enter = auto-generate):
      Auto-generated: Xk7$mP9qLr2!nJvW3cTy
  ✓ Client username 'acme-au-user'

  ? Add a Queue? [Y/n]: y
    ? Queue name [acme-au-q]: acme-au-orders-q
    ? Access type [non-exclusive / exclusive]: non-exclusive
    ? Add topic subscription? [Y/n]: y
        ? Topic (e.g. acme/au/>): acme/au/orders/>
    ? Add topic subscription? [Y/n]: n
  ✓ Queue 'acme-au-orders-q'

  ? Add a Queue? [Y/n]: n

  ? Add a REST Delivery Point (RDP)? [y/N]: y
    ? RDP name [acme-au-rdp]:
    ? Client profile [acme-au-profile]:
    ? REST consumer name [acme-au-consumer]:
    ? Target host (FQDN): target-system-au.internal.example.com
    ? Port [443]:
    ? TLS? [Y/n]: y
    ? Bind a queue to this RDP? [Y/n]: y
        ? Queue name: acme-au-orders-q
        ? POST target path [/]: /api/v1/events
  ✓ RDP 'acme-au-rdp'

──────────────────────────────────────────────────────────────
🎉  Integration created successfully!
  Service : abc123  VPN=msgvpn-abc123
  Domain  : AcmeAU  id=d-xxx

  python3 solace.py cluster status
  python3 solace.py domain list
```

### Verify what was created

```bash
# Check all cluster objects in the active VPN
python3 solace.py cluster status

# List Event Portal domains
python3 solace.py domain list

# List schemas in the domain
python3 solace.py schema list --domain-id <domain-id>

# List events
python3 solace.py event list --domain-id <domain-id>

# List applications
python3 solace.py app list --domain-id <domain-id>

# List queues
python3 solace.py cluster queue-list

# Check queue subscriptions
python3 solace.py cluster queue-subs-list --queue acme-au-orders-q
```

---

### Flow 3 — Event Portal Design Only

Use this when the messaging service already exists but you only need to add EP objects.

```bash
python3 solace.py wizard --flow 3
```

Walks through: prefix → env → domain → schemas → events → applications.  
No cluster objects are created, no service is provisioned.

---

### Flow 4 — Cluster / Broker Objects Only

Use this when the EP design already exists and you only need broker runtime objects.

```bash
python3 solace.py wizard --flow 4
```

Walks through: prefix → env → client profile → ACL profile → username → queues → RDP.  
Uses the VPN already in context; prompts if none is set.

---

## Approach 2 — Export → Clone → Provision

**What it does:** Reads everything from a live service, replaces the country code throughout all object names / topics / descriptions, generates new passwords, then creates and provisions a new service.

No hardcoded values — names come from what's already in the source service.

---

### Step A — Export the source service

```bash
python3 solace.py service export \
  --id   <source-service-id> \
  --country DEV \
  --out  config/dev-export/service.json
```

This writes a complete snapshot of the service to `config/dev-export/service.json`:

```json
{
  "sourceCountry": "DEV",
  "service": {
    "serviceId":     "5yv0da6tr85",
    "name":          "acme-automation-dev",
    "datacenterId":  "aks-eastus",
    "serviceTypeId": "developer",
    "serviceClassId":"developer"
  },
  "eventPortal": {
    "domainName": "AcmeDev",
    "schemas": [
      { "name": "OrderPayloadSchema", "type": "jsonSchema", "version": "1.0.0", "content": {...} }
    ],
    "events": [
      { "name": "OrderCreated", "version": "1.0.0", "topic": "acme/dev/orders/{orderId}/created", "schemaRef": "OrderPayloadSchema" }
    ],
    "applications": [
      { "name": "AcmeSourceSystem-DEV", "version": "1.0.0", "produces": ["OrderCreated"], "consumes": [] },
      { "name": "AcmeTargetSystem-DEV", "version": "1.0.0", "produces": [],              "consumes": ["OrderCreated"] }
    ]
  },
  "clusterManagement": {
    "vpnName": "msgvpn-5yv0da6tr85",
    "clientProfiles": [ { "name": "acme-dev-profile" } ],
    "aclProfiles": [
      {
        "name":               "acme-dev-acl",
        "publishDefault":     "disallow",
        "subscribeDefault":   "disallow",
        "publishExceptions":  ["acme/dev/orders/>"],
        "subscribeExceptions":["acme/dev/orders/>"]
      }
    ],
    "clientUsernames": [
      { "name": "acme-dev-user", "password": "", "clientProfile": "acme-dev-profile", "aclProfile": "acme-dev-acl", "enabled": true }
    ],
    "queues": [
      { "name": "acme-dev-orders-q", "accessType": "non-exclusive", "subscriptions": ["acme/dev/orders/>"] }
    ],
    "restDeliveryPoints": [
      {
        "name": "acme-dev-rdp",
        "consumers": [
          { "name": "acme-dev-rest-consumer", "host": "target-dev.example.com", "port": 443, "tlsEnabled": true }
        ],
        "queueBindings": ["acme-dev-orders-q"]
      }
    ]
  }
}
```

> **Note:** Passwords are never exported. They will be auto-generated during clone.

---

### Step B — Clone config to a new country

```bash
python3 solace.py provision clone \
  --config     config/dev-export/service.json \
  --to-country SG \
  --datacenter aks-australiaeast \
  --out        config/sg/service.json
```

The clone command:
- Replaces every occurrence of `DEV`/`dev`/`Dev` → `SG`/`sg`/`Sg` in **all string values** (names, topics, descriptions, hosts)
- Picks a new datacenter
- Auto-generates secure passwords for all client usernames
- Saves the result to `config/sg/service.json`

**Preview of what changes:**

```
SOURCE (DEV)                    →   TARGET (SG)
─────────────────────────────────────────────────────────────────
service.name: acme-automation-dev   →   acme-automation-sg
EP domain:    AcmeDev               →   AcmeSg
event topic:  acme/dev/orders/>     →   acme/sg/orders/>
profile:      acme-dev-profile      →   acme-sg-profile
acl:          acme-dev-acl          →   acme-sg-acl
user:         acme-dev-user         →   acme-sg-user
queue:        acme-dev-orders-q     →   acme-sg-orders-q
rdp:          acme-dev-rdp          →   acme-sg-rdp
consumer host:target-dev.example.com→   target-sg.example.com
```

---

### Step C — Provision the cloned config

```bash
python3 solace.py provision run --config config/sg/service.json
```

Or do steps B + C in one shot with the wizard:

```bash
python3 solace.py wizard --flow 2
```

The wizard flow:
1. Asks for source service ID and source country code
2. Asks for target country code + picks datacenter from live API list
3. Exports source config automatically
4. Shows clone diff preview
5. Lets you customise: EP domain name, topic prefix, REST consumer hosts, extra queues
6. Optionally set passwords manually (or keep auto-generated)
7. Confirms before creating new service
8. Creates service, waits for ready, provisions EP + cluster in one shot

---

### One-shot replicate (export + clone + provision)

```bash
python3 solace.py provision replicate \
  --from-service <source-service-id> \
  --from-country DEV \
  --to-country   SG \
  --datacenter   aks-australiaeast \
  --service-name acme-automation-sg \
  --out          config/sg/service.json
```

Flags:

| Flag | Required | Description |
|------|----------|-------------|
| `--from-service` | ✓ | Source service ID to export from |
| `--from-country` | ✓ | Country code that appears in source object names |
| `--to-country` | ✓ | Target country code to substitute |
| `--datacenter` | ✓ | Target datacenter ID (run `service datacenters` to list) |
| `--service-name` | — | Override target service name (default: derived from source) |
| `--out` | — | Output path for clone config (default: `config/<country>/service.json`) |
| `--dry-run` | — | Export + clone only; do not create service or provision |
| `--skip-create-service` | — | Provision into an already-created service |

---

### Verify the clone

```bash
# Set the new service as active
python3 solace.py service use <new-service-id>

# Confirm all cluster objects exist
python3 solace.py cluster status

# Confirm EP domain was created
python3 solace.py domain list

# Check events in the new domain
python3 solace.py event list --domain-id <domain-id>
```

---

## CLI Reference

### context

```bash
python3 solace.py context show                         # show active token + service
python3 solace.py context set-token --token <token>    # save Bearer token
python3 solace.py context clear                        # reset context file
```

### service

```bash
python3 solace.py service list                         # list all services
python3 solace.py service datacenters                  # list available datacenters
python3 solace.py service types                        # list service types + class IDs
python3 solace.py service info [--id <id>]             # full service details + SEMP creds
python3 solace.py service create \
  --name NAME \
  --datacenter <dc-id> \
  --type <type-id> \
  --class <class-id>
python3 solace.py service wait [--id <id>]             # poll until ready
python3 solace.py service use <id>                     # set active, save SEMP creds to context
python3 solace.py service delete --id <id>             # delete service
python3 solace.py service export \
  --id <id> --country <CODE> \
  [--domain <domain-name>] \
  [--out config/<env>/service.json]                   # export live config to file
```

### domain

```bash
python3 solace.py domain list
python3 solace.py domain get --id <id>
python3 solace.py domain create --name NAME [--description TEXT]
python3 solace.py domain update --id <id> [--name NAME] [--description TEXT]
python3 solace.py domain delete --id <id>
```

### schema

```bash
python3 solace.py schema list [--domain-id <id>]
python3 solace.py schema get --id <id>
python3 solace.py schema create \
  --name NAME --domain-id <id> \
  [--type jsonSchema|avro|protobuf|xmlSchema] \
  [--version 1.0.0] \
  [--file schema.json | --content '{"type":"object"}']
python3 solace.py schema versions --schema-id <id>
python3 solace.py schema promote --id <version-id> --state released
python3 solace.py schema delete --id <id>
```

### event

```bash
python3 solace.py event list [--domain-id <id>]
python3 solace.py event get --id <id>
python3 solace.py event create \
  --name NAME --domain-id <id> \
  --topic "acme/{env}/orders/{orderId}/created" \
  [--schema-version-id <svid>] \
  [--version 1.0.0]
python3 solace.py event versions --event-id <id>
python3 solace.py event promote --id <version-id> --state released
python3 solace.py event delete --id <id>
```

### app

```bash
python3 solace.py app list [--domain-id <id>]
python3 solace.py app get --id <id>
python3 solace.py app create \
  --name NAME --domain-id <id> \
  [--produces <ev-version-id>...] \
  [--consumes <ev-version-id>...]
python3 solace.py app versions --app-id <id>
python3 solace.py app asyncapi --version-id <id> [--format json|yaml]
python3 solace.py app promote --id <version-id> --state released
python3 solace.py app delete --id <id>
```

### cluster (Broker Runtime — SEMP v2)

```bash
python3 solace.py cluster status                       # show all objects in active VPN

# Client Profiles
python3 solace.py cluster profile-list
python3 solace.py cluster profile-create --name PROFILE_NAME
python3 solace.py cluster profile-delete --name PROFILE_NAME

# ACL Profiles
python3 solace.py cluster acl-list
python3 solace.py cluster acl-create --name ACL_NAME \
  [--publish-default disallow|allow] \
  [--subscribe-default disallow|allow]
python3 solace.py cluster acl-add-pub  --name ACL_NAME --topic "acme/{env}/>"
python3 solace.py cluster acl-add-sub  --name ACL_NAME --topic "acme/{env}/>"
python3 solace.py cluster acl-delete   --name ACL_NAME

# Client Usernames
python3 solace.py cluster user-list
python3 solace.py cluster user-create \
  --name USERNAME --password PASSWORD \
  --client-profile PROFILE --acl-profile ACL
python3 solace.py cluster user-delete --name USERNAME

# Queues
python3 solace.py cluster queue-list
python3 solace.py cluster queue-create   --name QUEUE [--access-type non-exclusive|exclusive]
python3 solace.py cluster queue-subscribe   --queue QUEUE --topic "acme/{env}/>"
python3 solace.py cluster queue-unsubscribe --queue QUEUE --topic "acme/{env}/>"
python3 solace.py cluster queue-subs-list   --queue QUEUE
python3 solace.py cluster queue-delete   --name QUEUE

# REST Delivery Points
python3 solace.py cluster rdp-list
python3 solace.py cluster rdp-create        --name RDP_NAME [--client-profile PROFILE]
python3 solace.py cluster rdp-add-consumer  --rdp RDP_NAME --name CONSUMER_NAME \
  --host target.example.com [--port 443] [--no-tls]
python3 solace.py cluster rdp-bind-queue    --rdp RDP_NAME --queue QUEUE [--path /api/events]
python3 solace.py cluster rdp-consumer-list --rdp RDP_NAME
python3 solace.py cluster rdp-delete        --name RDP_NAME
```

### provision

```bash
# Run full provisioning from config file (EP + Cluster)
python3 solace.py provision run --config config/<env>/service.json
python3 solace.py provision run --config config/<env>/service.json --dry-run
python3 solace.py provision run --config config/<env>/service.json --skip-ep       # cluster only
python3 solace.py provision run --config config/<env>/service.json --skip-cluster  # EP only

# Clone a config to a new country
python3 solace.py provision clone \
  --config config/dev-export/service.json \
  --to-country SG \
  --datacenter <dc-id> \
  [--service-name NAME] \
  [--out config/sg/service.json] \
  [--dry-run] \
  [--no-passwords]

# All-in-one: export + clone + create service + provision
python3 solace.py provision replicate \
  --from-service <source-id> \
  --from-country DEV \
  --to-country   SG \
  --datacenter   <dc-id> \
  [--service-name NAME] \
  [--out config/sg/service.json] \
  [--dry-run] \
  [--skip-create-service]
```

### wizard

```bash
python3 solace.py wizard              # interactive menu
python3 solace.py wizard --flow 1    # create from scratch
python3 solace.py wizard --flow 2    # clone country
python3 solace.py wizard --flow 3    # EP objects only
python3 solace.py wizard --flow 4    # cluster objects only
```

---

## Config File Format

All exported and cloned configs use this multi-object schema:

```json
{
  "sourceCountry": "DEV",
  "targetCountry": "SG",
  "environment":   "sg",

  "service": {
    "serviceId":     "",
    "name":          "acme-automation-sg",
    "datacenterId":  "aks-australiaeast",
    "serviceTypeId": "developer",
    "serviceClassId":"developer"
  },

  "eventPortal": {
    "domainName":        "AcmeSg",
    "domainDescription": "Acme SG integration domain",

    "schemas": [
      {
        "name":        "OrderPayloadSchema",
        "type":        "jsonSchema",
        "version":     "1.0.0",
        "description": "JSON schema for order events",
        "content": {
          "$schema": "http://json-schema.org/draft-07/schema#",
          "type":    "object",
          "required": ["orderId", "eventType", "timestamp"],
          "properties": {
            "orderId":   { "type": "string" },
            "eventType": { "type": "string", "enum": ["CREATED","UPDATED","SHIPPED"] },
            "timestamp": { "type": "string", "format": "date-time" }
          }
        }
      }
    ],

    "events": [
      {
        "name":      "OrderCreated",
        "version":   "1.0.0",
        "topic":     "acme/sg/orders/{orderId}/created",
        "schemaRef": "OrderPayloadSchema"
      }
    ],

    "applications": [
      {
        "name":     "AcmeSourceSystem-SG",
        "type":     "standard",
        "version":  "1.0.0",
        "produces": ["OrderCreated"],
        "consumes": []
      },
      {
        "name":     "AcmeTargetSystem-SG",
        "type":     "standard",
        "version":  "1.0.0",
        "produces": [],
        "consumes": ["OrderCreated"]
      }
    ]
  },

  "clusterManagement": {
    "vpnName": "",

    "clientProfiles": [
      { "name": "acme-sg-profile" }
    ],

    "aclProfiles": [
      {
        "name":               "acme-sg-acl",
        "publishDefault":     "disallow",
        "subscribeDefault":   "disallow",
        "publishExceptions":  ["acme/sg/orders/>", "acme/sg/notifications/>"],
        "subscribeExceptions":["acme/sg/orders/>", "acme/sg/notifications/>"]
      }
    ],

    "clientUsernames": [
      {
        "name":          "acme-sg-user",
        "password":      "auto-generated-on-clone",
        "clientProfile": "acme-sg-profile",
        "aclProfile":    "acme-sg-acl",
        "enabled":       true
      }
    ],

    "queues": [
      {
        "name":        "acme-sg-orders-q",
        "accessType":  "non-exclusive",
        "subscriptions": ["acme/sg/orders/>", "acme/sg/orders/*/created"]
      }
    ],

    "restDeliveryPoints": [
      {
        "name":              "acme-sg-rdp",
        "clientProfile":     "acme-sg-profile",
        "enabled":           true,
        "postRequestTarget": "/api/v1/events",
        "consumers": [
          {
            "name":       "acme-sg-rest-consumer",
            "host":       "target-system-sg.internal.example.com",
            "port":       443,
            "tlsEnabled": true,
            "httpMethod": "post"
          }
        ],
        "queueBindings": ["acme-sg-orders-q"]
      }
    ]
  }
}
```

> **Key design rule:** `schemaRef` in events and `produces`/`consumes` in applications use **names** (not IDs).  
> The provisioner resolves names → IDs at runtime, so configs are portable across environments.

---

## Three APIs

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| **Event Portal Designer** | `https://api.solace.cloud/api/v2/architecture` | Bearer token | Design-time: domains, schemas, events, applications |
| **Cloud Mission Control** | `https://api.solace.cloud/api/v0` | Bearer token | Service lifecycle: create/manage broker VMs |
| **SEMP v2 Config** | `https://<broker>:943/SEMP/v2/config` | HTTP Basic (`mission-control-manager`) | Runtime: queues, credentials, RDP |

---

## Environment / Context

Context is persisted to `.solace-context.json` (gitignored). It is loaded automatically by every command.

```bash
export SOLACE_API_TOKEN="eyJ..."         # required — Solace Cloud Bearer token

# Set automatically after: python3 solace.py service use <id>
export SEMP_BASE_URL="https://..."       # SEMP endpoint for the active service
export SEMP_USERNAME="mission-control-manager"
export SEMP_PASSWORD="..."
```

All values can also be stored via `context set-token` and `service use` — no need to set env vars manually after first run.

---

## GitHub Actions CI/CD

### Secrets required

| Secret | Workflow | Description |
|--------|----------|-------------|
| `SOLACE_API_TOKEN_DEV` | deploy-dev | Bearer token for Dev |
| `SOLACE_API_TOKEN_TEST` | deploy-test | Bearer token for Test |
| `SOLACE_API_TOKEN_PROD` | deploy-prod | Bearer token for Prod |
| `SOLACE_SERVICE_ID_DEV` | deploy-dev | Messaging service ID for Dev |
| `SOLACE_SERVICE_ID_TEST` | deploy-test | Messaging service ID for Test |
| `SOLACE_SERVICE_ID_PROD` | deploy-prod | Messaging service ID for Prod |

### Pipeline

```
git push (config/dev/**)   →  deploy-dev   (automatic)
workflow_dispatch          →  deploy-test  (requires environment approval)
workflow_dispatch          →  deploy-prod  (requires environment approval + manual "YES" confirm)
```

### What each workflow does

```yaml
# deploy-dev.yml (simplified)
- python3 solace.py context set-token --token $SOLACE_API_TOKEN
- python3 solace.py service use $SOLACE_SERVICE_ID
- python3 solace.py provision run --config config/dev/service.json
```

---

## Country Template

For manual clone-without-export, copy the template and fill in placeholders:

```bash
cp config/template/country-template.json config/sg/service.json
sed -i 's/{{COUNTRY}}/SG/g; s/{{COUNTRY_LOWER}}/sg/g' config/sg/service.json
```

Or use the automated approach:

```bash
python3 solace.py provision clone \
  --config config/dev-export/service.json \
  --to-country SG \
  --datacenter aks-australiaeast
```
