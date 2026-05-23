Export a live Solace service config to a portable JSON file.

Captures all Event Portal objects (domain, schemas, events, applications) and all cluster objects (client profiles, ACL profiles, usernames, queues, RDPs) from a running service. Passwords are never exported.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--id <service-id>`       Service ID to export (uses active context if omitted)
- `--country <CODE>`        Country/environment code that appears in object names (e.g. DEV, AU, SG)
- `--domain <name>`         EP domain name to export (auto-detected from country if omitted)
- `--out <path>`            Output file path (default: config/<country>/service.json)

If arguments are missing, ask the user for:
1. Service ID (or confirm using active context service)
2. Country/environment code (e.g. DEV, AU, US)

Then run:
```bash
python3 solace.py service export --id <id> --country <CODE> --out <path>
```

After the export completes, read the output JSON file and show a summary:
- Service name + datacenter
- EP domain name
- Count of schemas, events, applications
- Count of client profiles, ACL profiles, usernames, queues, RDPs
- Output file path

Example usage:
```
/export --id 5yv0da6tr85 --country DEV
/export --country AU --out config/au-backup/service.json
```
