# Working Code — Setup Guide

## Repository

Source code is hosted on GitHub. The project is fully functional and runnable
by judges with a Solace Cloud account.

**Branch for submission:** `feature/bob-a-thon`

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.9+ | Any 3.9–3.13 release |
| pip | latest | Bundled with Python |
| Solace Cloud account | — | Free trial at solace.com/products/event-broker/cloud/trial |
| Solace Cloud API token | — | Generate in Solace Cloud console → API Tokens |

**No other dependencies required.** The only external Python package is `requests`.

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd solace-automation

# 2. Install dependencies (only one package)
pip install -r requirements.txt

# 3. Set your Solace Cloud API token
export SOLACE_API_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

# Windows PowerShell
$env:SOLACE_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

# 4. Verify connectivity
python3 solace.py context show
```

---

## Quick Start — 5-Minute Demo

### Option A: Interactive Wizard (recommended for first run)

```bash
python3 solace.py wizard
```

Follow the prompts:
1. Select flow: `1` (Create new integration from scratch)
2. Enter a prefix: `demo`
3. Enter environment: `dev`
4. Pick a datacenter from the live list
5. Pick service type and class
6. The wizard creates everything automatically

### Option B: Clone an Existing Country Config

```bash
# Step 1: Export a live service to JSON
python3 solace.py service list
python3 solace.py service use <service-id>
python3 solace.py service export --output config/dev-export/service.json

# Step 2: Clone AU config → SG config
python3 solace.py provision clone \
    --input config/dev-export/service.json \
    --source-country AU \
    --target-country SG \
    --output config/prod/sg.json

# Step 3: Review the generated config
cat config/prod/sg.json

# Step 4: Provision (dry-run first)
python3 solace.py provision run --config config/prod/sg.json --dry-run

# Step 5: Provision for real
python3 solace.py provision run --config config/prod/sg.json
```

### Option C: One-Shot Replicate

```bash
# Export + clone + create service + provision — all in one command
python3 solace.py provision replicate \
    --from-service <source-service-id> \
    --from-country AU \
    --to-country SG \
    --datacenter aks-australiaeast
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SOLACE_API_TOKEN` | Yes | Solace Cloud bearer token (Event Portal + Mission Control) |
| `SEMP_BASE_URL` | Auto | Set by `service use` — SEMP broker base URL |
| `SEMP_USERNAME` | Auto | Set by `service use` — SEMP admin username |
| `SEMP_PASSWORD` | Auto | Set by `service use` — SEMP admin password |

The `SEMP_*` variables are automatically populated when you run `python3 solace.py service use <id>`.

---

## All Available Commands

### Context Management
```bash
python3 solace.py context show            # Show active token and service
python3 solace.py context set-token       # Update API token
python3 solace.py context clear           # Clear all saved context
```

### Datacenters
```bash
python3 solace.py dc list                 # List available datacenters
python3 solace.py dc types                # List service types and classes
```

### Broker Services
```bash
python3 solace.py service list            # List all services
python3 solace.py service create \
    --name my-svc \
    --datacenter aks-australiaeast \
    --type developer \
    --class developer
python3 solace.py service use <id>        # Set active service (populates SEMP_* vars)
python3 solace.py service wait <id>       # Wait until service is ready
python3 solace.py service info <id>       # Show service details
python3 solace.py service export \
    --output config/dev-export/service.json
python3 solace.py service delete <id>
```

### Event Portal — Domains
```bash
python3 solace.py domain list
python3 solace.py domain get <id>
python3 solace.py domain create --name MyDomain --description "..."
python3 solace.py domain update <id> --description "..."
python3 solace.py domain delete <id>
```

### Event Portal — Schemas
```bash
python3 solace.py schema list --domain-id <id>
python3 solace.py schema create --domain-id <id> --name OrderSchema --type jsonSchema
python3 solace.py schema versions <schema-id>
python3 solace.py schema promote <version-id>    # released state
python3 solace.py schema delete <schema-id>
```

### Event Portal — Events
```bash
python3 solace.py event list --domain-id <id>
python3 solace.py event create \
    --domain-id <id> \
    --name OrderCreated \
    --topic "orders/{orderId}/created" \
    --schema-id <schema-id>
python3 solace.py event versions <event-id>
python3 solace.py event promote <version-id>
python3 solace.py event delete <event-id>
```

### Event Portal — Applications
```bash
python3 solace.py app list --domain-id <id>
python3 solace.py app create --domain-id <id> --name MyApp --type standard
python3 solace.py app versions <app-id>
python3 solace.py app asyncapi <version-id>      # Export AsyncAPI spec
python3 solace.py app promote <version-id>
python3 solace.py app delete <app-id>
```

### Broker Cluster Objects (SEMP v2)
```bash
# Profiles
python3 solace.py cluster profile create --name my-profile
python3 solace.py cluster profile list
python3 solace.py cluster profile delete --name my-profile

# ACL Profiles
python3 solace.py cluster acl create --name my-acl
python3 solace.py cluster acl list
python3 solace.py cluster acl delete --name my-acl

# Client Usernames
python3 solace.py cluster username create \
    --name my-user \
    --password s3cr3t \
    --client-profile my-profile \
    --acl-profile my-acl
python3 solace.py cluster username list
python3 solace.py cluster username delete --name my-user

# Queues
python3 solace.py cluster queue create --name my-queue --access-type non-exclusive
python3 solace.py cluster queue list
python3 solace.py cluster queue subscribe --name my-queue --topic "orders/>"
python3 solace.py cluster queue delete --name my-queue

# REST Delivery Points
python3 solace.py cluster rdp create --name my-rdp --client-profile my-profile
python3 solace.py cluster rdp list
python3 solace.py cluster consumer create \
    --rdp my-rdp \
    --name my-consumer \
    --host target.example.com \
    --port 443 \
    --tls
python3 solace.py cluster binding create --rdp my-rdp --queue my-queue
python3 solace.py cluster rdp delete --name my-rdp
```

### Provisioning Workflows
```bash
# Full provision from JSON config
python3 solace.py provision run --config config/dev/service.json
python3 solace.py provision run --config config/dev/service.json --dry-run
python3 solace.py provision run --config config/dev/service.json --skip-ep
python3 solace.py provision run --config config/dev/service.json --skip-cluster

# Clone an exported config to a new country
python3 solace.py provision clone \
    --input config/dev-export/service.json \
    --source-country AU \
    --target-country SG \
    --output config/sg/service.json

# One-shot: export + clone + create service + provision
python3 solace.py provision replicate \
    --from-service <service-id> \
    --from-country AU \
    --to-country SG \
    --datacenter aks-australiaeast
```

---

## Config File Format

Use the country template as your starting point:

```bash
cp config/template/country-template.json config/myenv/service.json
# Edit config/myenv/service.json — replace {{COUNTRY}} and {{COUNTRY_LOWER}}
python3 solace.py provision run --config config/myenv/service.json --dry-run
```

Template: [`config/template/country-template.json`](../config/template/country-template.json)

---

## CI/CD with GitHub Actions

Three workflows are pre-configured:

| Workflow | Trigger | Environment | Approval |
|---|---|---|---|
| `deploy-dev.yml` | Push to main (config/dev/** change) | dev | None |
| `deploy-test.yml` | Manual `workflow_dispatch` | test | GitHub Environments |
| `deploy-prod.yml` | Manual `workflow_dispatch` + confirm | prod | GitHub Environments + confirm |

**Required GitHub Secrets:**
- `SOLACE_API_TOKEN`
- `SEMP_BASE_URL`
- `SEMP_USERNAME`
- `SEMP_PASSWORD`

---

## Langflow Setup

1. Import `langflow/solace-cloud-orchestrated-workflow.json` into your Langflow instance
2. Configure the MCP tool bindings to point to your deployed Solace Automation CLI
3. Connect an ICA Agent Chat webhook to the Langflow API endpoint
4. Test with: "List my Solace services"

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Invalid or expired API token | Regenerate token in Solace Cloud console |
| `400 ALREADY_EXISTS` | Object already provisioned | Safe to ignore — idempotent by design |
| `400 SOLACE_CLIENT_USERNAME: invalid characters` | Name contains `/` or `.` | Check source config for non-alphanumeric chars in names |
| `503 Service Unavailable` | Broker VM still starting | Run `service wait <id>` before provisioning |
| `SEMP_BASE_URL not set` | No active service in context | Run `service use <id>` first |

---

## Project Structure

```
solace-automation/
├── solace.py                    Entry point CLI (40+ commands)
├── requirements.txt             Single dependency: requests>=2.31.0
├── src/
│   ├── client.py                HTTP client (Bearer + Basic, retry logic)
│   ├── context.py               Persisted session manager
│   ├── api/
│   │   ├── cloud_svc.py         Cloud Mission Control API
│   │   ├── event_portal.py      Event Portal Designer API
│   │   └── semp.py              SEMP v2 Config API
│   └── workflows/
│       ├── wizard.py            Interactive guided setup (4 flows)
│       ├── exporter.py          Export live service → JSON
│       ├── cloner.py            Country substitution + password gen
│       └── provision.py         Two-phase orchestration engine
├── config/
│   ├── template/country-template.json   Reusable config template
│   ├── dev/service.json                 Dev environment config
│   ├── test/service.json                Test environment config
│   └── prod/service.json                Production environment config
├── langflow/
│   └── solace-cloud-orchestrated-workflow.json   Langflow agent workflow
├── mcp_server/tools/            MCP tool wrappers for agent integration
├── .github/workflows/           GitHub Actions CI/CD (dev/test/prod)
└── doc/                         Bob-a-thon submission documentation
```
