Provision a Solace environment via Azure Logic Apps — creates service, Event Portal objects, and cluster/broker config in a single orchestrated call. Logic App equivalent of /provision.

Reads config from a JSON file and calls the main-dispatcher → fullProvision flow.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--config <path>`   Config file to provision from (required, e.g. config/au/service.json)
- `--skip-ep`         Skip Event Portal phase
- `--skip-cluster`    Skip cluster phase
- `--dry-run`         Validate config only, do not call Logic App

If `--config` is missing, list available config files and ask the user to pick:
```powershell
Get-ChildItem -Path config -Recurse -Filter "service.json" | Select-Object FullName | Sort-Object
```

Load credentials and dispatcher URL:
```powershell
$ctx    = Get-Content .solace-context.json | ConvertFrom-Json
$params = Get-Content azure-logic-apps/parameters/parameters.json | ConvertFrom-Json
$url    = $params.mainDispatcherUrl.value
$config = Get-Content <path> | ConvertFrom-Json
```

Show preview before running:
```
Logic App Provision — via main-dispatcher → fullProvision
  Config     : <path>
  Service    : <name> (<serviceId or 'new'>)
  EP domain  : <domainName>
  Schemas    : <count>
  Events     : <count>
  Apps       : <count>
  Profiles   : <count>
  Queues     : <count>
  RDPs       : <count>
  Skip EP    : <true/false>
  Skip Cluster: <true/false>

Proceed? [Y/n]
```

If `--dry-run`, stop here and show:
```
Dry run complete — config is valid. No Logic App calls made.
```

Otherwise call the Logic App:
```powershell
$body = @{
  resource         = "fullProvision"
  action           = "provision"
  apiToken         = $ctx.token
  skipEventPortal  = $skipEp
  skipCluster      = $skipCluster
  payload          = $config
} | ConvertTo-Json -Depth 20

Write-Host "Calling Logic App... (service creation takes 5-10 min)" -ForegroundColor Yellow

$response = Invoke-RestMethod `
  -Uri $url `
  -Method POST `
  -Body $body `
  -ContentType "application/json" `
  -TimeoutSec 900
```

Show progress during long runs (service creation):
```
Calling Logic App dispatcher...
  → Routing to main-orchestrator-fixed
  → Scope: Service Provisioning
     Creating service... (polling every 15s)
  → Scope: Event Portal Provisioning
  → Scope: Cluster Provisioning
Done.
```

Display final result:
```
Provision Complete
  Service ID : abc123def
  VPN Name   : msgvpn-abc123def
  Domain ID  : dom-xyz789
  Duration   : 8m 42s

Run /la-status to verify all workflows are healthy.
```

Example usage:
```
/la-provision --config config/au/service.json
/la-provision --config config/sg/service.json --skip-ep
/la-provision --config config/nz/service.json --dry-run
```
