# Prompt and Bob Usage

This document records all significant prompts used with Bob AI (IBM watsonx Code Assistant)
during development of the Solace Automation project, along with the outcome and how the
generated code was used.

---

## Summary

Bob AI was used across the **full development lifecycle** — architecture design, code
generation, debugging, testing, and documentation. Estimated contribution: **40–50%
reduction in development time** compared to writing everything from scratch.

---

## 1. Initial Architecture Design

**Prompt:**
```
I need to automate Solace PubSub+ provisioning that spans three separate APIs:
- Event Portal Designer API (design-time: domains, schemas, events, apps)
- Cloud Mission Control API (service lifecycle: create/delete broker VMs)
- SEMP v2 Config API (runtime: credentials, queues, REST delivery webhooks)

Requirements:
- Single CLI entry point
- Idempotent operations (safe to re-run)
- Separate concerns between API clients and workflow orchestration
- Support both interactive (wizard) and automated (config file) modes

What's the cleanest Python architecture for this?
```

**Bob's Output:** Recommended layered architecture:
- `src/api/` — pure API client classes, one file per Solace API plane
- `src/workflows/` — orchestration logic consuming the API clients
- `solace.py` — thin CLI layer using argparse, delegates to workflows

**How it was used:** This became the exact final project structure. Bob's reasoning
about separation of concerns (API clients know nothing about workflows; workflows know
nothing about CLI) saved half a day of design iteration.

**Files produced:** Overall project layout in `src/api/` and `src/workflows/`

---

## 2. Unified HTTP Client with Retry Logic

**Prompt:**
```
Write a Python HTTP client class for Solace APIs that:
- Supports both Bearer token auth and HTTP Basic auth (same client, different modes)
- Uses urllib3.Retry with exponential backoff for 429, 500, 502, 503, 504
- Raises a custom SolaceError with status code and response body on failure
- Has get(), post(), patch(), delete() methods
- Logs all requests at DEBUG level
```

**Bob's Output:** Generated `src/client.py` with `SolaceClient` and `SolaceError`
classes. The retry configuration and dual-auth pattern matched requirements exactly.

**Minor adjustments needed:** Added the `requests.adapters.HTTPAdapter` mounting pattern
that Bob initially missed.

**File:** [`src/client.py`](../src/client.py)

---

## 3. SEMP v2 REST Delivery Point Implementation

**Prompt:**
```
Write Python functions to create Solace SEMP v2 REST Delivery Point objects via REST API.
Base URL pattern: {semp_base}/msgVpns/{vpn}/restDeliveryPoints

Need three operations:
1. Create RDP (name, clientProfile, enabled flag)
2. Create RDP REST Consumer (name, host, port, tlsEnabled, httpMethod)
3. Create RDP Queue Binding (rdpName, queueName, postRequestTarget)

Each must be idempotent: if the object already exists (HTTP 400 with SOLACE_ALREADY_EXISTS
error code), log a warning and continue rather than raising an error.

Auth: HTTP Basic (username/password passed to SolaceClient).
```

**Bob's Output:** Generated `create_rdp()`, `create_rdp_consumer()`, and
`create_rdp_queue_binding()` functions with correct idempotency handling.

**Adjustments needed:** The SEMP payload field names for `restConsumerName` and
`queueBindingName` needed correction against the actual Solace SEMP v2 OpenAPI spec.

**File:** [`src/api/semp.py`](../src/api/semp.py)

---

## 4. Recursive Country-Code Substitution

**Prompt:**
```
I have a Python dict (loaded from JSON) representing a full Solace service configuration.
I need to recursively substitute country codes throughout every string value in the dict.

Examples of what needs substituting:
- Service name: "mars-automation-au" → "mars-automation-sg"
- Domain: "MarsAutomation-AU" → "MarsAutomation-SG"
- Topics: "mars/au/orders/>" → "mars/sg/orders/>"
- Hostnames: "target-au.example.com" → "target-sg.example.com"

The substitution must handle:
- Uppercase: AU → SG
- Lowercase: au → sg
- Mixed case: Au → Sg (title case)

Write a recursive Python function that handles nested dicts and lists.
Also write a sanitize_name() helper that strips any characters not in [a-zA-Z0-9_-]
since SEMP object names have strict character limits.
```

**Bob's Output:** Generated the `_substitute()` recursive function and `_sanitize_name()`
helper that became the core of the cloner workflow.

**How it was used:** Directly integrated into `src/workflows/cloner.py`. The
case-variant handling (upper/lower/title) was exactly what was needed for Solace's
mix of naming conventions across API planes.

**File:** [`src/workflows/cloner.py`](../src/workflows/cloner.py)

---

## 5. Interactive CLI Wizard

**Prompt:**
```
Design an interactive CLI wizard in Python for Solace provisioning. It should present
a menu and support 4 flows:

Flow 1: Create new integration from scratch
  - Step 1: Pick datacenter from live API (numbered list)
  - Step 2: Pick service type and class
  - Step 3: Create broker service, wait for it to become ready
  - Step 4: Create Event Portal domain
  - Step 5: Create schemas, events, applications with sensible defaults
  - Step 6: Create cluster objects (profiles, ACL, usernames, queues, RDP)

Flow 2: Clone existing country config to new country
  - Show existing configs, let user pick source
  - Ask for target country code and datacenter
  - Preview substitutions before applying

Flow 3: Event Portal objects only (skip broker runtime)
Flow 4: Cluster objects only (skip Event Portal)

Use live API calls for dynamic option lists. Auto-generate names from a user-supplied prefix.
```

**Bob's Output:** Scaffolded the full `InteractiveWizard` class with the 4-flow
structure, numbered menu helpers, and live API picker pattern. Saved approximately
one full day of wizard scaffolding.

**Adjustments needed:** Service readiness polling loop and error recovery for
quota-exceeded responses were added manually.

**File:** [`src/workflows/wizard.py`](../src/workflows/wizard.py)

---

## 6. Two-Phase Provisioning Orchestrator

**Prompt:**
```
Write a Python provisioning orchestrator that reads a JSON config file and:

Phase 1 — Event Portal:
1. Create or get domain
2. For each schema: create schema, create version with inline content, promote to released
3. For each event: create event, create version with topic + schema ref, promote
4. For each application: create app, create version with produce/consume lists, promote

Phase 2 — Cluster Management:
1. Create client profiles
2. Create ACL profiles, then add publishExceptions and subscribeExceptions topic rules
3. Create client usernames with password (from config) + profile/ACL bindings
4. Create queues (exclusive/non-exclusive), then add topic subscriptions
5. Create REST delivery points, consumers, queue bindings

All operations must be idempotent. Log each step clearly. Support a dry-run flag
that prints what would happen without making API calls.
```

**Bob's Output:** Generated the `Provisioner` class with both phases, dry-run support,
and comprehensive logging. The phased approach and ordering logic matched what the
Solace API requires.

**Adjustments:** API response shapes for Event Portal version promotion differed from
Bob's assumptions — required correction against live API testing.

**File:** [`src/workflows/provision.py`](../src/workflows/provision.py)

---

## 7. Langflow Workflow Design

**Prompt:**
```
I'm building a Langflow workflow for Solace broker provisioning orchestration.

Architecture: Supervisor agent pattern
- One coordinator agent receives the user message from ChatInput
- Three worker agents: Intent Parser, Workflow Planner, Executor
- Executor agent calls tools bound to my Python CLI commands

The Intent Parser should extract:
- action (create/clone/export/list)
- sourceCountry (2-3 letter code)
- targetCountry (2-3 letter code)
- datacenter (Solace datacenter ID string)
- environment (dev/test/prod)

The Workflow Planner maps the parsed intent to a specific CLI workflow.
The Executor calls MCP tools (provision run, service export, provision clone, etc.)

Generate the Langflow node JSON with ChatInput → Coordinator → Workers → ChatOutput.
Use GPT as the model. Show the edges connecting nodes.
```

**Bob's Output:** Produced the initial Langflow JSON structure with correct node types
(`ChatInput`, `Agent`, `MCPTools`, `ChatOutput`) and edge definitions. This became the
base for `langflow/solace-cloud-orchestrated-workflow.json`.

**Adjustments:** Tool binding configuration and agent system prompts were customized
to match actual CLI command names and parameter formats.

**File:** [`langflow/solace-cloud-orchestrated-workflow.json`](../langflow/solace-cloud-orchestrated-workflow.json)

---

## 8. GitHub Actions CI/CD Pipelines

**Prompt:**
```
Write three GitHub Actions workflow files for a Solace provisioning pipeline:

1. deploy-dev.yml
   - Trigger: push to main when config/dev/** changes
   - Steps: checkout → setup Python → pip install → dry-run validation →
     provision run (EP phase) → provision run (cluster phase) → show cluster status
   - No approval gate

2. deploy-test.yml
   - Trigger: manual workflow_dispatch with inputs: skip_ep (bool), skip_cluster (bool)
   - Requires GitHub Environments approval for "test" environment
   - Same steps as dev but uses config/test/service.json

3. deploy-prod.yml
   - Trigger: manual workflow_dispatch with mandatory confirm input ("yes")
   - Requires GitHub Environments approval for "prod" environment
   - Fails if confirm != "yes"

Use SOLACE_API_TOKEN, SEMP_BASE_URL, SEMP_USERNAME, SEMP_PASSWORD as secrets.
```

**Bob's Output:** Generated all three workflow YAML files with correct triggers,
environment protection rules, and step sequencing.

**Files:** [`.github/workflows/`](../.github/workflows/)

---

## 9. Debugging: SEMP Special Character Violation

**Prompt:**
```
My Solace SEMP client username creation is failing with HTTP 400. The error message is:
"SOLACE_CLIENT_USERNAME: name contains invalid characters"

SEMP policy: object names may only contain [a-zA-Z0-9_-]. No dots, slashes, or spaces.

Here's the cloner output config snippet:
{
  "clientUsernames": [
    { "name": "mars/sg-user" }   ← slash came from country substitution
  ]
}

The cloner is doing: name.replace("au", "sg") on "mars/au-user" but the slash was
already in the original name from an earlier bug.

Fix the substitution pipeline to sanitize all object names after substitution.
```

**Bob's Output:** Identified that `_sanitize_name()` was not being called on
object names after country substitution. Provided the fix: apply sanitization
specifically to `name` fields in `clientProfiles`, `aclProfiles`, `clientUsernames`,
`queues`, and `restDeliveryPoints` after the recursive string substitution.

**Commit:** `31c1824 fix(cloner): update special characters to comply with Solace SEMP policies`

---

## 10. CLI Help Documentation Generation

**Prompt:**
```
Generate comprehensive --help text for the following Solace CLI command groups.
For each command include: description, arguments, options, and a usage example.

Command groups:
- context (show, set-token, clear)
- service (list, create, use, wait, delete, export, info)
- dc (list, types)
- domain (list, get, create, update, delete)
- schema (list, create, versions, promote, delete)
- event (list, create, versions, promote, delete)
- app (list, create, versions, asyncapi, promote, delete)
- cluster (profile create/list/delete, acl create/list/delete,
           username create/list/delete, queue create/list/delete/subscribe,
           rdp create/list/delete, consumer create, binding create)
- provision (run, clone, replicate)
- wizard

Here's my argparse setup: [paste of solace.py argparse section]
```

**Bob's Output:** Generated complete help strings for all 40+ commands, including
parameter descriptions and realistic usage examples with actual Solace datacenter IDs.

**Commit:** `cbf3c4e feat: add comprehensive command documentation for Solace automation tools`

---

## Bob Interaction Screenshots / Logs

> Screenshots of Bob AI sessions are stored in `doc/assets/bob-screenshots/`
> (to be added during demo preparation — capture key interactions from the
> sessions above showing Bob's responses and the code generation in action).

---

## Prompt Engineering Lessons Learned

1. **Provide the constraint, not just the task.** Adding "idempotent — skip if exists
   rather than error" to every API-related prompt saved multiple debug cycles.

2. **Paste the actual schema.** For Solace SEMP payloads, including the real API response
   shape in the prompt produced correct field names on the first try.

3. **Break large features into function-level prompts.** "Write the whole exporter" produced
   generic code. "Write `export_queues()` that calls GET /msgVpns/{vpn}/queues and returns
   a list of queue dicts excluding system queues (name starts with #)" produced production-ready code.

4. **Include error examples when debugging.** Pasting the exact HTTP 400 response body
   alongside the failing code gave Bob enough context to identify the root cause immediately.

5. **Ask for the why, not just the fix.** "Why would SEMP return ALREADY_EXISTS on a
   queue subscription but not on the queue itself?" led to understanding Solace's
   idempotency model, which improved the entire API client design.
