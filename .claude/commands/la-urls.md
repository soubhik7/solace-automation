Fetch HTTP trigger callback URLs for all deployed Solace Logic App workflows and write them into parameters.json and the Postman environment file.

Run this once after deploying the Logic App to Azure. All workflow parameters and the Postman dispatcher URL are auto-populated.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--logic-app <name>`     Logic App name (default: read from parameters.json or ask)
- `--resource-group <rg>`  Resource group (default: rg-marsis-np-eu2-02)
- `--subscription <id>`    Subscription ID (default: read from connections.json)

If arguments are missing, read defaults:
```powershell
$connections = Get-Content azure-logic-apps/connections/connections.json | ConvertFrom-Json
$subscriptionId = "2d2ae2ca-7228-4391-af4a-793ebcf81657"
```

Run the helper script:
```powershell
.\azure-logic-apps\scripts\get-trigger-urls.ps1 `
  -LogicAppName <logic-app> `
  -ResourceGroup <resource-group> `
  -SubscriptionId <subscription-id>
```

The script fetches URLs for all 8 workflows:
- main-dispatcher
- main-orchestrator-fixed
- service-management
- service-provisioning-fixed
- event-portal-management
- event-portal-provisioning
- cluster-management
- export-clone

After the script completes, read `azure-logic-apps/parameters/parameters.json` and display the updated values:

```
Trigger URLs updated
  solace-mainOrchestratorUrl      : https://<app>.azurewebsites.net/api/main-orchestrator-fixed/...
  serviceManagementUrl     : https://<app>.azurewebsites.net/api/service-management/...
  serviceProvisioningUrl   : https://<app>.azurewebsites.net/api/service-provisioning-fixed/...
  eventPortalManagementUrl : https://<app>.azurewebsites.net/api/event-portal-management/...
  eventPortalUrl           : https://<app>.azurewebsites.net/api/event-portal-provisioning/...
  clusterManagementUrl     : https://<app>.azurewebsites.net/api/cluster-management/...
  exportCloneUrl           : https://<app>.azurewebsites.net/api/export-clone/...

Files updated:
  azure-logic-apps/parameters/parameters.json
  azure-logic-apps/Solace-Automation.postman_environment.json
```

Example usage:
```
/la-urls
/la-urls --logic-app wf-solace-automation --resource-group rg-marsis-np-eu2-02
```
