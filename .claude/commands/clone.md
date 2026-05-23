Clone a Solace service config to a new country by substituting the country code throughout all object names, topics, descriptions, and host patterns.

Takes an exported config file and produces a new config ready to provision. Auto-generates secure passwords for all client usernames. Does NOT create a service or provision anything — use /provision or /replicate for that.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--config <path>`         Source config file (exported JSON)
- `--to-country <CODE>`     Target country/environment code (e.g. SG, DE, JP)
- `--datacenter <id>`       Target datacenter ID (run /datacenters to see options)
- `--service-name <name>`   Override target service name (auto-derived if omitted)
- `--out <path>`            Output path (default: config/<country>/service.json)
- `--no-passwords`          Skip password generation

If arguments are missing, ask the user for the required ones.

Then run:
```bash
python3 solace.py provision clone \
  --config <path> \
  --to-country <CODE> \
  --datacenter <dc-id> \
  --out <out-path>
```

After cloning, read both the source and output JSON files and display a diff table showing what changed:

| Object type | Source (FROM) | Target (TO) |
|---|---|---|
| Service name | ... | ... |
| EP domain | ... | ... |
| Topics | ... | ... |
| Profiles/ACLs/Users | ... | ... |
| Queues | ... | ... |

Then show the next step:
```
✅ Clone saved → <out-path>

Next steps:
  Provision now:  python3 solace.py provision run --config <out-path>
  Or use:         /provision --config <out-path>
  Or full flow:   /replicate (exports + clones + provisions in one shot)
```

Example usage:
```
/clone --config config/dev-export/service.json --to-country SG --datacenter aks-australiaeast
/clone --config config/dev-export/service.json --to-country DE --datacenter aks-germanywestcentral
```
