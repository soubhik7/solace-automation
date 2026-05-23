Show all available Solace automation skills (slash commands) with descriptions and usage examples.

Display the following reference table:

```
╔══════════════════════════════════════════════════════════════════════╗
║          Solace Cloud Automation — Available Skills                  ║
╚══════════════════════════════════════════════════════════════════════╝

PROVISIONING
────────────────────────────────────────────────────────────────────────
  /wizard              Interactive guided wizard (all flows)
                         /wizard 1  → create from scratch
                         /wizard 2  → clone country
                         /wizard 3  → EP design only
                         /wizard 4  → cluster objects only

  /provision           Provision a config file to Solace Cloud
                         /provision --config config/dev/service.json
                         /provision --config config/sg/service.json --dry-run

  /replicate           One-shot: export + clone + create service + provision
                         /replicate --from-service <id> --from-country DEV
                                    --to-country SG --datacenter aks-australiaeast

EXPORT & CLONE
────────────────────────────────────────────────────────────────────────
  /export              Export a live service config to JSON
                         /export --id <service-id> --country DEV

  /clone               Clone a config to a new country (no provisioning)
                         /clone --config config/dev-export/service.json
                                --to-country SG --datacenter aks-australiaeast

INSPECTION
────────────────────────────────────────────────────────────────────────
  /status              Full status of the active service (EP + cluster)
  /services            List all messaging services / set active
  /domains             List / create / inspect Event Portal domains
  /queue               Manage queues and subscriptions
  /config-show         Read and display a config file in human-readable form

CONTEXT
────────────────────────────────────────────────────────────────────────
  /context             Show / set token / set active service / clear
                         /context set-token eyJhbGci...
                         /context use <service-id>

  /help                Show this help

QUICK START
────────────────────────────────────────────────────────────────────────
  New integration:   /wizard 1
  Clone to country:  /wizard 2   (or /replicate for non-interactive)
  Check status:      /status
  See your configs:  /config-show
```

Also run `python3 solace.py context show` to display the current active token and service.
