# Problem Statement and Solution

## The Problem

Deploying a Solace PubSub+ event-driven integration across multiple geographies requires
orchestrating **three completely separate Solace API planes**:

| API Plane | Purpose | Typical Operations |
|---|---|---|
| **Event Portal Designer API** | Design-time schema/event catalog | Create domains, schemas, events, applications, promote versions |
| **Cloud Mission Control API** | Broker service lifecycle | Create/delete/wait for broker VMs, list datacenters |
| **SEMP v2 Config API** | Runtime broker configuration | Profiles, ACLs, credentials, queues, REST delivery webhooks |

Done manually, a single country rollout involves **40–60 sequential API calls** with:
- Strict ordering requirements (domain before events, profiles before usernames)
- No built-in idempotency (re-running fails with conflicts)
- Manual copy-paste of config values across three API surfaces
- No safe path for replicating an existing country to a new one
- Zero visibility into drift between environments

For an enterprise running event-driven architectures across 10+ countries, this is a
**multi-day engineering effort per rollout**, error-prone and not repeatable.

### Pain Points by Stakeholder

**Integration Engineers**
- Must read three separate API docs and manage three sets of credentials
- No single workflow that covers the full provisioning lifecycle
- Manual JSON editing with no validation before API calls

**Platform/DevOps Teams**
- No CI/CD story for Solace configuration changes
- No environment promotion path (dev → test → prod)
- No audit trail of what changed and when

**Business / Project Managers**
- New country onboarding takes days instead of hours
- High error rate means frequent re-work and rollback
- No self-service capability for teams without Solace expertise

---

## Why It Matters

Event-driven architecture is a **critical enterprise backbone**. Solace PubSub+ brokers carry
order events, payment notifications, and operational data between systems. Misconfiguration
or delay in provisioning has cascading downstream impact — blocked integrations, missed SLAs,
and manual fallback processes.

The cost of the status quo:
- **Engineer time**: 1–2 days per country rollout × N countries × M environments
- **Error cost**: Misconfigured ACLs or topics cause silent message loss, hard to diagnose
- **Opportunity cost**: Teams delay new country launches due to infrastructure lead time

---

## The Solution

**Solace Automation** is an AI-orchestrated provisioning platform that reduces a full
country onboarding from days to minutes through three integrated layers:

### Layer 1 — Conversational AI Interface (ICA Agent Chat)
Users express intent in plain English:
> *"Clone our AU broker setup for Singapore and deploy to the APAC datacenter"*

IBM ICA Agent Chat receives this and routes it to the Langflow orchestration layer.

### Layer 2 — AI Workflow Orchestration (IBM Langflow)
A **supervisor agent pattern** built in Langflow (powered by GPT) decomposes the request:

```
Coordinator Agent
├── Intent Parser Worker    → extracts: action=clone, source=AU, target=SG, dc=APAC
├── Workflow Planner Worker → selects: provision replicate flow
└── Executor Worker         → calls Solace Automation CLI tools in sequence
```

The executor invokes the Solace Automation CLI via MCP (Model Context Protocol) tool
bindings — each CLI command is exposed as a named tool callable by the agent.

### Layer 3 — Solace Automation CLI (Execution Engine)
A Python CLI (`solace.py`) that wraps all three Solace API planes in a single,
idempotent, ordered orchestration:

- **Export**: snapshot any live service to portable JSON
- **Clone**: country-code substitution across all names, topics, and hostnames
- **Provision**: two-phase deployment (Event Portal design → Broker runtime)
- **Wizard**: interactive guided setup for new integrations
- **CI/CD**: GitHub Actions workflows for dev/test/prod promotion

---

## Target Users

| User | How They Use the Solution |
|---|---|
| Integration Engineers | CLI directly (`provision run`, `wizard`) for hands-on control |
| Platform Teams | GitHub Actions CI/CD workflows for automated environment promotion |
| Non-technical stakeholders | ICA Agent Chat with natural language requests |
| New team members | Interactive wizard guides through every step with live API pickers |

---

## Business Value

| Metric | Before | After |
|---|---|---|
| Country rollout time | 1–2 days | < 10 minutes |
| API calls managed manually | 40–60 per rollout | 0 (fully automated) |
| Re-run safety | Error on conflict | Idempotent — safe to re-run |
| Environment promotion | Manual copy-paste | `provision replicate` one command |
| CI/CD integration | None | GitHub Actions with approval gates |
| Expertise required | Deep Solace API knowledge | Natural language via Agent Chat |

---

## Potential Impact

- **Immediate**: Any team running Solace PubSub+ across multiple regions can adopt this
  tool to eliminate manual provisioning entirely.
- **Scale**: The config-as-code approach means topology is version-controlled, reviewable,
  and auditable — enabling governance at scale.
- **Extensibility**: The MCP server layer means any AI agent (not just ICA) can orchestrate
  Solace provisioning through standard tool-calling interfaces.
- **Template ecosystem**: Country templates let teams publish reusable integration patterns
  that others can clone with a single command.
