Deploy all Solace automation Logic App workflows to Azure and fetch their trigger URLs.

Reads deployment config from the user's arguments or prompts for missing values.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--logic-app <name>`     Logic App resource name (e.g. wf-solace-automation)
- `--resource-group <rg>`  Azure resource group (e.g. rg-marsis-np-eu2-02)
- `--subscription <id>`    Azure subscription ID

If any required argument is missing, read defaults from `azure-logic-apps/connections/connections.json` and ask the user to confirm or override.

Show the deployment plan before running:
```
Logic App Deployment Plan
  Logic App     : <name>
  Resource Group: <rg>
  Subscription  : <id>
  Workflows     : main-dispatcher, main-orchestrator-fixed, service-management,
                  service-provisioning-fixed, event-portal-management,
                  event-portal-provisioning, cluster-management, export-clone
```

Step 1 — Verify Azure login:
```powershell
az account show --query "{name:name, id:id}" -o json
```
If not logged in, run `az login`.

Step 2 — Set subscription:
```powershell
az account set --subscription <id>
```

Step 3 — Deploy each workflow JSON from `azure-logic-apps/workflows/`:

For Logic Apps Standard, upload each workflow file:
```powershell
az logicapp deployment source config-zip \
  --name <logic-app> \
  --resource-group <rg> \
  --src azure-logic-apps/workflows/<workflow>.json
```

Or use REST API to create/update each workflow:
```powershell
$workflowFiles = @(
  "main-dispatcher",
  "main-orchestrator-fixed",
  "service-management",
  "service-provisioning-fixed",
  "event-portal-management",
  "event-portal-provisioning",
  "cluster-management",
  "export-clone"
)
```

Step 4 — After deploying all workflows, automatically run `/la-urls` to fetch trigger URLs and populate `parameters.json`.

Show final summary:
```
Deployment complete
  Workflows deployed: 8
  parameters.json  : updated with trigger URLs
  Postman env      : updated

Next steps:
  1. Import updated Postman environment
  2. Run /la-status to verify all workflows are healthy
  3. Run /la-provision to test end-to-end
```

Example usage:
```
/la-deploy --logic-app wf-solace-automation --resource-group rg-marsis-np-eu2-02 --subscription 2d2ae2ca-7228-4391-af4a-793ebcf81657
/la-deploy
```
