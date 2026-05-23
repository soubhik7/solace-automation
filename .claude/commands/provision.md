Provision a Solace service from a config JSON file — creates all Event Portal objects and all cluster/broker objects.

Runs in two phases:
  Phase 1 — Event Portal: domain → schemas → schema versions → events → event versions → applications → application versions
  Phase 2 — Cluster:      client profiles → ACL profiles → topic exceptions → client usernames → queues → subscriptions → RDPs → consumers → queue bindings

All operations are idempotent — safe to re-run on an existing service.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--config <path>`     Config file to provision from (required)
- `--skip-ep`           Skip Event Portal phase (cluster objects only)
- `--skip-cluster`      Skip cluster phase (EP objects only)
- `--dry-run`           Validate config without making any API calls

If `--config` is missing, list available config files:
```bash
find config -name "service.json" | sort
```
Then ask the user which one to use.

Build and run the command:
```bash
python3 solace.py provision run --config <path> [--skip-ep] [--skip-cluster] [--dry-run]
```

Before running, read the config file and show a preview:
```
Provisioning: <path>
  Service    : <name> (<serviceId or 'new'>)
  EP domain  : <domainName>
  Schemas    : <count>
  Events     : <count>
  Apps       : <count>
  Profiles   : <count>
  Queues     : <count>
  RDPs       : <count>
```

After provisioning, run `python3 solace.py cluster status` to show what was created.

Example usage:
```
/provision --config config/dev/service.json
/provision --config config/sg/service.json --skip-ep
/provision --config config/prod/service.json --dry-run
```
