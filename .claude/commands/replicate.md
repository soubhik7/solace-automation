Full one-shot pipeline: export a live service → clone to new country → create new messaging service → provision everything.

This is the fastest way to roll out an existing country's integration to a new country. Combines /export + /clone + service creation + /provision in a single command.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--from-service <id>`     Source service ID to export from (required)
- `--from-country <CODE>`   Country code in the source (e.g. DEV, AU) (required)
- `--to-country <CODE>`     New country to create (e.g. SG, DE, JP) (required)
- `--datacenter <id>`       Target datacenter ID (required — use /datacenters to list)
- `--service-name <name>`   Override target service name (auto-derived if omitted)
- `--out <path>`            Save clone config to this path
- `--dry-run`               Export + clone only, do not create service or provision
- `--skip-create-service`   Provision into an already-existing service

If any required argument is missing, ask the user before running.

Show the pipeline steps before executing:
```
Replication pipeline:
  Step 1/4  Export  <from-service>  [<from-country>]
  Step 2/4  Clone   <from-country> → <to-country>
  Step 3/4  Create  new messaging service in <datacenter>
  Step 4/4  Provision EP + cluster objects
```

Run:
```bash
python3 solace.py provision replicate \
  --from-service <id> \
  --from-country <FROM> \
  --to-country <TO> \
  --datacenter <dc-id> \
  [--service-name <name>] \
  [--out <path>] \
  [--dry-run]
```

After completion, display:
- New service ID and VPN name
- Config file saved path
- Quick verification commands:
  ```
  python3 solace.py cluster status
  python3 solace.py domain list
  ```

Example usage:
```
/replicate --from-service 5yv0da6tr85 --from-country DEV --to-country SG --datacenter aks-australiaeast
/replicate --from-service 5yv0da6tr85 --from-country DEV --to-country DE --datacenter aks-germanywestcentral --dry-run
```
