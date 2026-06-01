Show all available Solace automation skills (slash commands) with descriptions and usage examples.

Display the following reference table:

```
╔══════════════════════════════════════════════════════════════════════╗
║          Solace Cloud Automation — Available Skills                  ║
╚══════════════════════════════════════════════════════════════════════╝

PYTHON CLI (direct API)
────────────────────────────────────────────────────────────────────────
  /wizard              Interactive guided wizard (all flows)
                         /wizard 1  → create from scratch
                         /wizard 2  → clone country
                         /wizard 3  → EP design only
                         /wizard 4  → cluster objects only

  /provision           Provision a config file to Solace Cloud (Python)
                         /provision --config config/dev/service.json
                         /provision --config config/sg/service.json --dry-run

  /replicate           One-shot: export + clone + create service + provision (Python)
                         /replicate --from-service <id> --from-country DEV
                                    --to-country SG --datacenter aks-australiaeast

  /export              Export a live service config to JSON
                         /export --id <service-id> --country DEV

  /clone               Clone a config to a new country (no provisioning)
                         /clone --config config/dev-export/service.json
                                --to-country SG --datacenter aks-australiaeast

  /status              Full status of the active service (EP + cluster)
  /services            List all messaging services / set active
  /domains             List / create / inspect Event Portal domains
  /queue               Manage queues and subscriptions
  /config-show         Read and display a config file in human-readable form
  /context             Show / set token / set active service / clear

AZURE LOGIC APPS (no-code / low-code)
────────────────────────────────────────────────────────────────────────
  /la-deploy           Deploy all 8 workflows to Azure Logic Apps
                         /la-deploy --logic-app wf-solace-automation
                                    --resource-group rg-marsis-np-eu2-02

  /la-urls             Fetch all trigger URLs → update parameters.json + Postman env
                         /la-urls
                         /la-urls --logic-app wf-solace-automation

  /la-status           Check health of all deployed workflows + last run results
                         /la-status
                         /la-status --logic-app wf-solace-automation

  /la-provision        Full E2E provision via Logic App (service + EP + cluster)
                         /la-provision --config config/au/service.json
                         /la-provision --config config/sg/service.json --skip-ep
                         /la-provision --config config/nz/service.json --dry-run

  /la-replicate        Export + clone + provision via Logic App (end-to-end)
                         /la-replicate --from-service 5yv0da6tr85
                                       --from-country DEV --to-country SG
                                       --datacenter aks-australiaeast

  /la-call             Call any single Logic App operation interactively
                         /la-call --resource service --action list
                         /la-call --resource cluster --sub-resource queue --action list
                         /la-call --resource eventPortal --sub-resource domain --action create
                                  --payload '{"name":"MyDomain","description":"..."}'

LOGIC APP WORKFLOW REFERENCE
────────────────────────────────────────────────────────────────────────
  Dispatcher:     main-dispatcher          (single entry point for all operations)
  Orchestrator:   main-orchestrator-fixed  (E2E: service + EP + cluster)
  Service CRUD:   service-management       (list/get/create/update/delete)
  Service Create: service-provisioning-fixed (create + poll until ready)
  EP CRUD:        event-portal-management  (domain/schema/event/app CRUD)
  EP Bulk:        event-portal-provisioning (bulk create all EP objects)
  Cluster CRUD:   cluster-management       (all SEMP objects CRUD + provision)
  Clone:          export-clone             (export service + substitute country)

QUICK START — LOGIC APPS
────────────────────────────────────────────────────────────────────────
  First time setup:
    1. /la-deploy   → deploy all workflows to Azure
    2. /la-urls     → fetch all trigger URLs
    3. /la-status   → verify all workflows are healthy

  New country rollout:
    /la-replicate --from-service <id> --from-country AU --to-country NZ
                  --datacenter aws-ap-southeast-2a

  Individual operations:
    /la-call --resource service --action list
    /la-call --resource cluster --sub-resource queue --action create
             --payload '{"name":"MY.QUEUE","owner":"user","accessType":"exclusive"}'

QUICK START — PYTHON CLI
────────────────────────────────────────────────────────────────────────
  New integration:   /wizard 1
  Clone to country:  /wizard 2   (or /replicate for non-interactive)
  Check status:      /status
  See your configs:  /config-show
```

Also run `python3 solace.py context show` to display the current active token and service.
