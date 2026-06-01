Check the status of all deployed Solace Logic App workflows — shows whether each workflow is enabled, its last run result, and the run history summary.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--logic-app <name>`     Logic App name (default: read from parameters.json or ask)
- `--resource-group <rg>`  Resource group (default: rg-marsis-np-eu2-02)
- `--subscription <id>`    Subscription ID

Read the Logic App name from context if not provided. Then for each of the 8 workflows, fetch status via Azure CLI:

```powershell
$workflows = @(
  "main-dispatcher",
  "main-orchestrator-fixed",
  "service-management",
  "service-provisioning-fixed",
  "event-portal-management",
  "event-portal-provisioning",
  "cluster-management",
  "export-clone"
)

foreach ($wf in $workflows) {
  az rest --method get `
    --uri "https://management.azure.com/subscriptions/$subId/resourceGroups/$rg/providers/Microsoft.Web/sites/$logicApp/hostruntime/runtime/webhooks/workflow/api/management/workflows/$wf?api-version=2018-11-01" `
    -o json
}
```

Also check the last 5 runs for main-dispatcher:
```powershell
az rest --method get `
  --uri "https://management.azure.com/subscriptions/$subId/resourceGroups/$rg/providers/Microsoft.Web/sites/$logicApp/hostruntime/runtime/webhooks/workflow/api/management/workflows/main-dispatcher/runs?api-version=2018-11-01&`$top=5" `
  -o json
```

Display a status table:
```
Solace Logic App Status — wf-solace-automation
────────────────────────────────────────────────────────────
Workflow                      State     Last Run      Result
─────────────────────────────────────────────────────────────
main-dispatcher               Enabled   2 min ago     Succeeded
main-orchestrator-fixed       Enabled   15 min ago    Succeeded
service-management            Enabled   5 min ago     Succeeded
service-provisioning-fixed    Enabled   15 min ago    Succeeded
event-portal-management       Enabled   3 min ago     Succeeded
event-portal-provisioning     Enabled   15 min ago    Succeeded
cluster-management            Enabled   14 min ago    Succeeded
export-clone                  Enabled   1 hr ago      Succeeded
─────────────────────────────────────────────────────────────

Recent Dispatcher Runs:
  2026-06-01 10:45:12  service / list        200  Succeeded  0.3s
  2026-06-01 10:30:01  fullProvision         200  Succeeded  8m 22s
  2026-06-01 10:15:44  cluster / provision   200  Succeeded  45s
```

If any workflow shows Failed or Disabled, highlight it and show the error details from the run history.

Also check whether `parameters.json` has all URLs populated:
```
URL Parameters
  solace-mainOrchestratorUrl      : OK
  serviceManagementUrl     : OK
  clusterManagementUrl     : OK
  eventPortalManagementUrl : OK
  eventPortalUrl           : OK
  serviceProvisioningUrl   : OK
  exportCloneUrl           : OK
```

Example usage:
```
/la-status
/la-status --logic-app wf-solace-automation --resource-group rg-marsis-np-eu2-02
```
