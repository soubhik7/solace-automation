# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
pip3 install requests

# Required — set Solace Cloud Bearer token
export SOLACE_API_TOKEN="eyJ..."
# Or persist it:
python3 solace.py context set-token --token <token>

# After creating/selecting a service, save SEMP credentials to context:
python3 solace.py service use <service-id>
```

Context is persisted to `.solace-context.json` (gitignored). Every command loads it automatically — no flags needed after initial setup.

## Running Commands

All commands go through the single entry point:

```bash
python3 solace.py <command-group> <subcommand> [flags]
```

Key command groups: `context`, `service`, `domain`, `schema`, `event`, `app`, `cluster`, `provision`, `wizard`

Run the interactive wizard:
```bash
python3 solace.py wizard           # menu
python3 solace.py wizard --flow 1  # create from scratch
python3 solace.py wizard --flow 2  # clone country
python3 solace.py wizard --flow 3  # EP objects only
python3 solace.py wizard --flow 4  # cluster/broker objects only
```

Provision from a config file:
```bash
python3 solace.py provision run --config config/<env>/service.json
python3 solace.py provision run --config config/<env>/service.json --dry-run
python3 solace.py provision run --config config/<env>/service.json --skip-ep      # cluster only
python3 solace.py provision run --config config/<env>/service.json --skip-cluster # EP only
```

There are no automated tests — validate changes by running `--dry-run` against a config file.

## Architecture

### Three APIs, two auth modes

| Layer | Module | Auth | Endpoint |
|-------|--------|------|----------|
| Event Portal Designer | `src/api/event_portal.py` | Bearer token | `https://api.solace.cloud/api/v2/architecture` |
| Cloud Mission Control | `src/api/cloud_svc.py` | Bearer token | `https://api.solace.cloud/api/v0` |
| Broker SEMP v2 | `src/api/semp.py` | HTTP Basic | `https://<broker>:943/SEMP/v2/config` |

`src/client.py` (`SolaceClient`) is a single object that holds both a Bearer session and a Basic session, exposing `ep_*`, `cloud_*`, and `semp_*` method prefixes. All API modules take a `SolaceClient` instance — they never construct HTTP sessions themselves.

### Context flow

`src/context.py` (`Context`) loads `.solace-context.json` and exposes `token`, `service_id`, `vpn_name`, `semp_base/user/pass`. `SolaceClient.from_context(ctx.as_dict())` is the standard way to build a client in CLI handlers.

### Workflows

- `src/workflows/provision.py` (`Provisioner`) — reads a config JSON and drives Phase 1 (Event Portal) then Phase 2 (cluster). Handles both legacy single-object and extended multi-object config formats transparently.
- `src/workflows/cloner.py` (`Cloner`) — substitutes country codes across all string values in a config (names, topics, hosts, descriptions). Uses case-aware replacement: `AU`→`SG`, `au`→`sg`, `Au`→`Sg`. VPN name is never substituted.
- `src/workflows/exporter.py` — reads a live service via APIs and writes the canonical multi-object config JSON format.
- `src/workflows/wizard.py` — interactive terminal wizard; delegates to the other workflows.

### Config file format

All exported/cloned configs use a single schema with these top-level keys:
- `sourceCountry`, `targetCountry`, `environment`
- `service` — serviceId, name, datacenterId, serviceTypeId, serviceClassId
- `eventPortal` — domainName, schemas[], events[], applications[]
- `clusterManagement` — vpnName, clientProfiles[], aclProfiles[], clientUsernames[], queues[], restDeliveryPoints[]

**Name-based resolution:** `schemaRef` in events and `produces`/`consumes` in applications use object names, not IDs. The `Provisioner` resolves names → IDs at runtime, so configs are portable across environments.

Passwords are never exported. The `Cloner` auto-generates them on clone.

### CLI entry point (`solace.py`)

A ~1500-line file containing all `argparse` command definitions and their handler functions. Handlers construct `Context` + `SolaceClient`, then call the relevant API class or workflow. The `SempAPI` always needs an explicit `vpn_name` (taken from context).

## CI/CD

Three GitHub Actions workflows in `.github/workflows/`:
- `deploy-dev.yml` — triggers on push to `main` when `config/dev/**`, `src/**`, or `solace.py` changes. Runs dry-run first, then provisions EP and cluster in separate steps.
- `deploy-test.yml` — manual dispatch with environment approval gate.
- `deploy-prod.yml` — manual dispatch with approval + confirmation gate.

Required secrets per environment: `SOLACE_API_TOKEN_<ENV>` and `SOLACE_SERVICE_ID_<ENV>`.

## Config Directory Layout

```
config/
  template/country-template.json   # {{COUNTRY}} / {{COUNTRY_LOWER}} placeholders
  dev-export/service.json           # live export from DEV (source for cloning)
  dev/service.json                  # provisioned DEV config
  test/service.json
  prod/service.json
  <country>/service.json            # per-country clone outputs
```
