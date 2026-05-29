# Complete Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                  ICA (Agent Chat)                       │
│                                                         │
│   User types: "Clone AU Solace setup for Singapore"     │
└─────────────────────────┬───────────────────────────────┘
                          │  Natural Language Intent
                          ▼
┌─────────────────────────────────────────────────────────┐
│   Custom Workflows in IBM Langflow & Agent Orchestration│
│                                                         │
│   Exposes Tools / Workflows (built with IBM BOB)        │
│                                                         │
│   → Supervisor pattern  Model: GPT                      │
│   → Coordinator agent                                   │
│   → Specialized workers:                                │
│       • Intent Parser   (extracts action/params)        │
│       • Workflow Planner(selects provisioning flow)     │
│       • Executor        (calls CLI tools via MCP)       │
│                                                         │
│   Langflow file: langflow/solace-cloud-orchestrated-    │
│                  workflow.json                          │
└─────────────────────────┬───────────────────────────────┘
                          │  MCP Tool Calls / CLI Commands
                          ▼
┌─────────────────────────────────────────────────────────┐
│           Solace Automation CLI  (solace.py)            │
│                                                         │
│   ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│   │  Event Portal│  │ Cloud Mission│  │  SEMP v2    │  │
│   │  Designer API│  │ Control API  │  │  Config API │  │
│   │              │  │              │  │             │  │
│   │ Domains      │  │ Services     │  │ Profiles    │  │
│   │ Schemas      │  │ Datacenters  │  │ ACLs        │  │
│   │ Events       │  │ Lifecycle    │  │ Credentials │  │
│   │ Applications │  │              │  │ Queues      │  │
│   │ Versions     │  │              │  │ RDP/Webhooks│  │
│   └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  │
│          │                 │                  │         │
│   ┌──────▼─────────────────▼──────────────────▼──────┐  │
│   │               Workflow Orchestration              │  │
│   │  • provision run    – full two-phase deploy       │  │
│   │  • provision clone  – country substitution        │  │
│   │  • provision replicate – one-shot export+deploy   │  │
│   │  • service export   – snapshot live config        │  │
│   │  • wizard           – interactive guided setup    │  │
│   └───────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────┘
                          │  Solace REST API / SEMP / SMF
                          ▼
┌─────────────────────────────────────────────────────────┐
│              SOLACE PUBSUB+ BROKER                      │
│         (Cloud / Local / Solace Cloud Trial)            │
│                                                         │
│   Queues / Topics / Events / Messages                   │
│   REST Delivery Points (outbound webhooks)              │
│   VPN-scoped multi-tenant isolation                     │
└─────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. ICA Agent Chat (Entry Point)

- IBM's conversational AI interface
- Accepts natural language provisioning requests
- Routes to the Langflow workflow via API

**Example inputs:**
- "Create a new Solace integration for the DE country"
- "Clone our AU setup to SG on the APAC datacenter"
- "Show me all services in the dev environment"
- "Provision the Mars project queues for production"

---

### 2. IBM Langflow — Supervisor Orchestration

**Pattern:** Supervisor with specialized worker agents

```
ChatInput
    │
    ▼
Coordinator Agent  (gpt model)
    ├──► Intent Parser Worker
    │        Extracts: action, source country, target country,
    │                  datacenter, environment, project name
    │
    ├──► Workflow Planner Worker
    │        Maps intent → CLI workflow:
    │        • "clone" → provision replicate
    │        • "create" → wizard flow 1
    │        • "EP only" → wizard flow 3
    │        • "broker only" → wizard flow 4
    │
    └──► Executor Worker
             Calls MCP tools in sequence:
             1. service export (if cloning)
             2. provision clone (country substitution)
             3. service create (new broker VM)
             4. provision run (deploy config)
             5. cluster status (verify)
```

**Workflow file:** [`langflow/solace-cloud-orchestrated-workflow.json`](../langflow/solace-cloud-orchestrated-workflow.json)

**Langflow nodes used:**
- `ChatInput` — user message ingress
- `Agent` (coordinator) — top-level supervisor
- `Agent` × 3 (workers) — intent parser, planner, executor
- `MCPTools` — bound to Solace Automation CLI commands
- `ChatOutput` — result display

---

### 3. Solace Automation CLI

**Entry point:** [`solace.py`](../solace.py)

**Source layout:**

```
src/
├── client.py          — Unified HTTP client (Bearer + Basic auth, retry logic)
├── context.py         — Persisted session (.solace-context.json)
├── api/
│   ├── cloud_svc.py   — Cloud Mission Control API
│   ├── event_portal.py— Event Portal Designer API
│   └── semp.py        — SEMP v2 Broker Config API
└── workflows/
    ├── wizard.py      — Interactive 4-flow guided setup
    ├── exporter.py    — Snapshot live service → portable JSON
    ├── cloner.py      — Country substitution + password generation
    └── provision.py   — Two-phase orchestration engine
```

**MCP server layer:** `mcp_server/tools/` exposes CLI operations as named tools
callable by any MCP-compatible agent (Langflow, Claude, etc.)

---

### 4. Provisioning Flows

#### Flow A: Clone & Replicate (most common)
```
Source Service (AU)
    │
    ▼ service export
Portable JSON snapshot
    │
    ▼ provision clone --to-country SG
SG config (substituted names, topics, hosts + new passwords)
    │
    ├──► service create (new broker VM in target datacenter)
    │
    ▼ provision run
Phase 1: Event Portal
  └─ domain → schemas → events → apps → promote versions

Phase 2: Cluster
  └─ client profiles → ACL profiles → client usernames
     → queues + subscriptions → REST delivery points
```

#### Flow B: Wizard (interactive)
```
User input (prefix, environment, datacenter)
    │
    ▼ wizard --flow 1
Step 1: Pick datacenter (live API list)
Step 2: Pick service type/class
Step 3: Create broker service (wait for ready)
Step 4: Create Event Portal domain
Step 5: Create schemas, events, applications
Step 6: Create cluster objects (profiles, queues, RDP)
```

#### Flow C: CI/CD Promotion
```
config/dev/service.json  ──► GitHub Actions deploy-dev.yml   (auto on push)
config/test/service.json ──► GitHub Actions deploy-test.yml  (manual + approval)
config/prod/service.json ──► GitHub Actions deploy-prod.yml  (manual + confirm)
```

---

### 5. Solace PubSub+ Broker Objects Created

| Object Type | Example Name | Purpose |
|---|---|---|
| Message VPN | `msgvpn-xxxxx` | Tenant isolation |
| Client Profile | `mars-sg-profile` | Connection permissions |
| ACL Profile | `mars-sg-acl` | Topic publish/subscribe rules |
| Client Username | `mars-sg-user` | Application credentials |
| Queue | `mars-sg-orders-q` | Guaranteed message storage |
| Queue Subscription | `mars/sg/orders/>` | Topic routing to queue |
| REST Delivery Point | `mars-sg-rdp` | Outbound webhook delivery |
| RDP Consumer | `mars-sg-rest-consumer` | Target HTTP endpoint |
| RDP Queue Binding | → `mars-sg-orders-q` | Which queue feeds the webhook |

---

### 6. Configuration File Format

All provisioning is driven by a single JSON config file:

```json
{
  "sourceCountry": "AU",
  "targetCountry": "SG",
  "environment": "sg",

  "service": {
    "name": "mars-automation-sg",
    "datacenterId": "aks-australiaeast",
    "serviceTypeId": "developer",
    "serviceClassId": "developer"
  },

  "eventPortal": {
    "domainName": "MarsAutomation-SG",
    "schemas": [...],
    "events": [...],
    "applications": [...]
  },

  "clusterManagement": {
    "vpnName": "msgvpn-xxx",
    "clientProfiles": [...],
    "aclProfiles": [...],
    "clientUsernames": [...],
    "queues": [...],
    "restDeliveryPoints": [...]
  }
}
```

Template: [`config/template/country-template.json`](../config/template/country-template.json)

---

### 7. CI/CD Architecture

```
GitHub Repository
├── config/dev/service.json   ─── push to main ───► deploy-dev.yml
│                                                     dry-run → EP phase → cluster phase
│
├── config/test/service.json  ─── manual trigger ──► deploy-test.yml
│                                                     GitHub Environments approval
│
└── config/prod/service.json  ─── manual trigger ──► deploy-prod.yml
                                                      approval + manual confirmation
```

Workflows: [`.github/workflows/`](../.github/workflows/)

---

### 8. Security Model

- **API tokens** stored as GitHub Secrets / environment variables (never committed)
- **SEMP passwords** auto-generated per clone, never exported from live services
- **VPN-scoped** isolation: all broker objects are contained within a specific msgVpn
- **ACL-default-deny**: topic publish/subscribe defaults to `disallow`; only explicit
  exception topics are permitted
- **Idempotent operations**: re-running never overwrites existing credentials
