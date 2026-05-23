# solace-automation

Python CLI for full Solace Cloud provisioning automation — covering the **Event Portal Designer API**, **Solace Cloud Mission Control API**, and **SEMP v2 Config API**.

---

## Architecture

```
Source System  ──publish──▶  SOLACE Queue/Topic  ──subscribe──▶  Target System (Consumer)
                                     │
                              REST DELIVERY POINT  ──────────────▶  Target System (REST)
                                     │
                         Protocols: AMQP · TCP/WebSocket
                                    SolacePubSub+ · JMS · HTTP
```

### Provisioning Pipeline
```
config/dev/service.json  ─┐
config/test/service.json  ├──▶  solace.py provision run  ──▶  Solace Cloud
config/prod/service.json  ─┘            │
                                         ├── Phase 1: Event Portal Design
                                         │   (Domain → Schema → Event → Application)
                                         └── Phase 2: Cluster Management
                                             (Client Profile · ACL Profile · Client Username
                                              Queue · Subscriptions · REST Delivery Point)
```

---

## Project Structure

```
solace-automation/
├── solace.py                    # ← Main CLI entry point (all commands)
├── src/
│   ├── client.py                # Dual-auth HTTP client (Bearer + Basic)
│   ├── context.py               # Persisted context (.solace-context.json)
│   ├── api/
│   │   ├── cloud_svc.py         # Cloud Mission Control API (services, datacenters)
│   │   ├── event_portal.py      # Event Portal Designer API (domains, schemas, events, apps)
│   │   └── semp.py              # SEMP v2 Config API (credentials, queues, RDP)
│   └── workflows/
│       └── provision.py         # Full orchestration workflow (Phases 1 + 2)
├── config/
│   ├── dev/service.json         # Dev environment config
│   ├── test/service.json        # Test environment config
│   └── prod/service.json        # Prod environment config
├── .github/workflows/
│   ├── deploy-dev.yml           # Auto-deploy on push to main
│   ├── deploy-test.yml          # Deploy with approval gate
│   └── deploy-prod.yml          # Manual trigger + approval gate
├── .env.example                 # Environment variable template
└── .claude/settings.json        # MCP server (solace-event-portal-designer)
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install requests

# 2. Set API token
export SOLACE_API_TOKEN="eyJ..."

# 3. Show context
python solace.py context show

# 4. List available datacenters & service types
python solace.py dc list
python solace.py dc types

# 5. Create a new messaging service
python solace.py service create \
  --name my-service \
  --datacenter aks-centralus \
  --type developer \
  --class developer

# 6. Wait for service to be ready, then activate it
python solace.py service wait --id <service-id>
python solace.py service use <service-id>

# 7. Full provisioning from config (both phases)
python solace.py provision run --config config/dev/service.json

# 8. Dry-run (validate config, no API calls)
python solace.py provision run --config config/dev/service.json --dry-run
```

---

## CLI Reference

### context
```bash
python solace.py context show                        # show active token + service
python solace.py context set-token --token <token>   # save token to context file
python solace.py context clear                       # reset context file
```

### dc (Datacenters)
```bash
python solace.py dc list                             # list all datacenters
python solace.py dc list --service-class developer   # filter by service class
python solace.py dc types                            # list service types + class IDs
```

### service (Messaging Services)
```bash
python solace.py service list                        # list all services
python solace.py service info [--id <id>]            # full service details + SEMP creds
python solace.py service create \
  --name NAME --datacenter aks-centralus \
  --type developer --class developer                 # create service
python solace.py service wait [--id <id>]            # poll until creationState=completed
python solace.py service use <id>                    # set active service, save SEMP creds
python solace.py service delete --id <id>            # delete service
```

### domain (Event Portal Domains)
```bash
python solace.py domain list
python solace.py domain get --id <id>
python solace.py domain create --name NAME [--description TEXT]
python solace.py domain update --id <id> [--name NAME] [--description TEXT]
python solace.py domain delete --id <id>
```

### schema (Event Portal Schemas)
```bash
python solace.py schema list [--domain-id <id>]
python solace.py schema get --id <id>
python solace.py schema create \
  --name NAME --domain-id <id> \
  [--type jsonSchema|avro|protobuf|xmlSchema] \
  [--version 1.0.0] \
  [--file schema.json | --content '{"type":"object",...}']
python solace.py schema versions --schema-id <id>
python solace.py schema promote --id <version-id> --state released
python solace.py schema delete --id <id>
```

### event (Event Portal Events)
```bash
python solace.py event list [--domain-id <id>]
python solace.py event get --id <id>
python solace.py event create \
  --name NAME --domain-id <id> \
  --topic "mars/orders/{orderId}/created" \
  [--schema-version-id <svid>] \
  [--version 1.0.0]
python solace.py event versions --event-id <id>
python solace.py event promote --id <version-id> --state released
python solace.py event delete --id <id>
```

### app (Event Portal Applications)
```bash
python solace.py app list [--domain-id <id>]
python solace.py app get --id <id>
python solace.py app create \
  --name NAME --domain-id <id> \
  [--produces <ev-version-id>...] \
  [--consumes <ev-version-id>...]
python solace.py app versions --app-id <id>
python solace.py app asyncapi --version-id <id> [--format json|yaml]
python solace.py app promote --id <version-id> --state released
python solace.py app delete --id <id>
```

### cluster (Broker Runtime — SEMP v2)
```bash
python solace.py cluster status                      # show all cluster objects in VPN

# Client Profiles
python solace.py cluster profile-list
python solace.py cluster profile-create --name PROFILE_NAME
python solace.py cluster profile-delete --name PROFILE_NAME

# ACL Profiles
python solace.py cluster acl-list
python solace.py cluster acl-create --name ACL_NAME \
  [--publish-default allow|disallow] \
  [--subscribe-default allow|disallow]
python solace.py cluster acl-add-pub --name ACL_NAME --topic "mars/orders/>"
python solace.py cluster acl-add-sub --name ACL_NAME --topic "mars/orders/>"
python solace.py cluster acl-delete --name ACL_NAME

# Client Usernames
python solace.py cluster user-list
python solace.py cluster user-create \
  --name USERNAME --password PASSWORD \
  --client-profile PROFILE --acl-profile ACL
python solace.py cluster user-delete --name USERNAME

# Queues
python solace.py cluster queue-list
python solace.py cluster queue-create --name QUEUE [--access-type exclusive|non-exclusive]
python solace.py cluster queue-subscribe --queue QUEUE --topic "mars/orders/>"
python solace.py cluster queue-unsubscribe --queue QUEUE --topic "mars/orders/>"
python solace.py cluster queue-subs-list --queue QUEUE
python solace.py cluster queue-delete --name QUEUE

# REST Delivery Points
python solace.py cluster rdp-list
python solace.py cluster rdp-create --name RDP_NAME [--client-profile default]
python solace.py cluster rdp-add-consumer --rdp RDP_NAME --name CONSUMER_NAME \
  --host target.example.com [--port 443] [--no-tls]
python solace.py cluster rdp-bind-queue --rdp RDP_NAME --queue QUEUE [--path /api/events]
python solace.py cluster rdp-consumer-list --rdp RDP_NAME
python solace.py cluster rdp-delete --name RDP_NAME
```

### provision (Full Orchestration)
```bash
python solace.py provision run --config config/dev/service.json
python solace.py provision run --config config/test/service.json --dry-run
python solace.py provision run --config config/prod/service.json --skip-ep      # cluster only
python solace.py provision run --config config/prod/service.json --skip-cluster # EP only
```

---

## Config File Schema (`config/<env>/service.json`)

```json
{
  "environment": "dev",
  "serviceId":   "<messaging-service-id>",
  "eventPortal": {
    "domainName":        "MarsAutomation-Dev",
    "domainDescription": "...",
    "schema": {
      "name":        "OrderPayloadSchema",
      "type":        "jsonSchema",
      "version":     "1.0.0",
      "description": "...",
      "content": { "$schema": "...", "type": "object", "properties": {} }
    },
    "event": {
      "name":        "OrderCreated",
      "version":     "1.0.0",
      "topic":       "mars/orders/{orderId}/created",
      "description": "..."
    },
    "sourceApplication": { "name": "MarsSourceSystem-Dev", "version": "1.0.0" },
    "targetApplication": { "name": "MarsTargetSystem-Dev", "version": "1.0.0" }
  },
  "clusterManagement": {
    "vpnName": "msgvpn-<id>",
    "clientProfile": { "name": "mars-dev-profile" },
    "aclProfile": {
      "name":               "mars-dev-acl",
      "publishDefault":     "disallow",
      "subscribeDefault":   "disallow",
      "publishExceptions":  ["mars/orders/>"],
      "subscribeExceptions":["mars/orders/>"]
    },
    "clientUsername": { "name": "mars-dev-user", "password": "Dev$ecret123" },
    "queues": [
      {
        "name":          "mars-dev-orders-q",
        "accessType":    "non-exclusive",
        "subscriptions": ["mars/orders/>", "mars/orders/*/created"]
      }
    ],
    "restDeliveryPoint": {
      "name":               "mars-dev-rdp",
      "postRequestTarget":  "/api/v1/events",
      "consumer": {
        "name":       "mars-dev-rest-consumer",
        "host":       "target-system-dev.internal.example.com",
        "port":       443,
        "tlsEnabled": true
      },
      "queueBindings": ["mars-dev-orders-q"]
    }
  }
}
```

---

## API Reference

### Three APIs used

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| **Event Portal Designer** | `https://api.solace.cloud/api/v2/architecture` | Bearer token | Design-time: domains, schemas, events, applications |
| **Cloud Mission Control** | `https://api.solace.cloud/api/v0` | Bearer token | Service provisioning: create/manage broker VMs |
| **SEMP v2 Config** | `https://<broker>:943/SEMP/v2/config` | HTTP Basic (`mission-control-manager`) | Runtime: queues, credentials, RDP |

### Event Portal Designer API

| Object | Method | Endpoint |
|--------|--------|----------|
| ApplicationDomain | GET/POST | `/applicationDomains` |
| ApplicationDomain | GET/PATCH/DELETE | `/applicationDomains/{id}` |
| Schema | GET/POST | `/schemas` |
| Schema | GET/PATCH/DELETE | `/schemas/{id}` |
| SchemaVersion | GET/POST | `/schemaVersions` |
| SchemaVersion | GET/PATCH/DELETE | `/schemaVersions/{id}` |
| SchemaVersion state | PATCH | `/schemaVersions/{id}/state` |
| Event | GET/POST | `/events` |
| Event | GET/PATCH/DELETE | `/events/{id}` |
| EventVersion | GET/POST | `/eventVersions` |
| EventVersion | GET/PATCH/DELETE | `/eventVersions/{id}` |
| EventVersion state | PATCH | `/eventVersions/{id}/state` |
| Application | GET/POST | `/applications` |
| Application | GET/PATCH/DELETE | `/applications/{id}` |
| ApplicationVersion | GET/POST | `/applicationVersions` |
| ApplicationVersion | GET/PATCH/DELETE | `/applicationVersions/{id}` |
| ApplicationVersion state | PATCH | `/applicationVersions/{id}/state` |
| AsyncAPI export | GET | `/applicationVersions/{id}/asyncApi` |

### Cloud Mission Control API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v0/datacenters` | List available datacenters |
| GET | `/api/v0/serviceTypes` | List service types + class IDs |
| GET | `/api/v0/services` | List all services |
| POST | `/api/v0/services` | Create a new messaging service |
| GET | `/api/v0/services/{id}` | Get service details + SEMP credentials |
| PATCH | `/api/v0/services/{id}` | Update service |
| DELETE | `/api/v0/services/{id}` | Delete service |

### SEMP v2 Config API

Base path: `/msgVpns/{vpnName}`

| Object | Method | Endpoint |
|--------|--------|----------|
| ClientProfile | GET/POST | `/clientProfiles` |
| ClientProfile | GET/PATCH/DELETE | `/clientProfiles/{name}` |
| AclProfile | GET/POST | `/aclProfiles` |
| AclProfile | GET/PATCH/DELETE | `/aclProfiles/{name}` |
| Publish Exception | POST/DELETE | `/aclProfiles/{name}/publishTopicExceptions[/{syntax},{topic}]` |
| Subscribe Exception | POST/DELETE | `/aclProfiles/{name}/subscribeTopicExceptions[/{syntax},{topic}]` |
| ClientUsername | GET/POST | `/clientUsernames` |
| ClientUsername | GET/PATCH/DELETE | `/clientUsernames/{name}` |
| Queue | GET/POST | `/queues` |
| Queue | GET/PATCH/DELETE | `/queues/{name}` |
| Queue Subscription | GET/POST | `/queues/{name}/subscriptions` |
| Queue Subscription | DELETE | `/queues/{name}/subscriptions/{topic}` |
| RestDeliveryPoint | GET/POST | `/restDeliveryPoints` |
| RestDeliveryPoint | GET/PATCH/DELETE | `/restDeliveryPoints/{name}` |
| RestConsumer | GET/POST | `/restDeliveryPoints/{rdp}/restConsumers` |
| RestConsumer | GET/PATCH/DELETE | `/restDeliveryPoints/{rdp}/restConsumers/{name}` |
| QueueBinding | GET/POST | `/restDeliveryPoints/{rdp}/queueBindings` |
| QueueBinding | DELETE | `/restDeliveryPoints/{rdp}/queueBindings/{queue}` |

---

## Environment Variables

```bash
# Required
export SOLACE_API_TOKEN="eyJ..."      # Solace Cloud API token

# Set automatically by: python solace.py service use <service-id>
export SEMP_BASE_URL=""               # e.g. https://mr-connection-xxx:943/SEMP/v2/config
export SEMP_USERNAME=""               # mission-control-manager
export SEMP_PASSWORD=""
```

All values are also persisted to `.solace-context.json` (gitignored) for reuse across commands.

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

### Pipeline flow

```
push to main (config/dev/**) → deploy-dev    (auto, no approval)
manual trigger               → deploy-test   (requires environment approval)
workflow_dispatch            → deploy-prod   (requires environment approval + manual confirm)
```

---

## MCP Server (Claude Code Integration)

`.claude/settings.json` configures the `solace-event-portal-designer` MCP server.  
In Claude Code you can use natural language:

```
"List all application domains"
"Create a new domain called MarsAutomation-Dev"
"Show me events in the MarsAutomation-Dev domain"
"Export AsyncAPI spec for application version <id>"
```
