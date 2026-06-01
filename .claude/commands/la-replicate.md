Full one-shot Logic App pipeline: export a source service → clone to new country → create new service → provision everything. Logic App equivalent of /replicate.

Chains export-clone → fullProvision via the main-dispatcher. No Python, no local scripts — entirely orchestrated through Azure Logic Apps.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--from-service <id>`    Source service ID to export from (required)
- `--from-country <CODE>`  Country code in the source service names (e.g. AU, DEV)
- `--to-country <CODE>`    New country code to roll out (e.g. NZ, SG, DE)
- `--datacenter <id>`      Target datacenter for the new service (required)
- `--service-name <name>`  Override target service name (auto-derived if omitted)
- `--skip-ep`              Skip Event Portal provisioning
- `--skip-cluster`         Skip cluster provisioning
- `--dry-run`              Run export-clone only, show cloned config, do not provision

If any required argument is missing, ask the user.

Load credentials and dispatcher URL:
```powershell
$ctx    = Get-Content .solace-context.json | ConvertFrom-Json
$params = Get-Content azure-logic-apps/parameters/parameters.json | ConvertFrom-Json
$url    = $params.mainDispatcherUrl.value
```

Show the pipeline before executing:
```
Logic App Replication Pipeline
  Step 1/2  Export + Clone   <from-service> [<from-country>] → [<to-country>]
  Step 2/2  Full Provision   create service + EP + cluster in <datacenter>
```

Step 1 — Export and clone via Logic App:
```powershell
$exportBody = @{
  resource = "exportClone"
  action   = "export"
  apiToken = $ctx.token
  payload  = @{
    sourceServiceId  = "<from-service>"
    sourceCountry    = "<from-country>"
    targetCountry    = "<to-country>"
    targetDatacenter = "<datacenter>"
    targetServiceName = "<service-name or null>"
  }
} | ConvertTo-Json -Depth 10

Write-Host "Step 1/2 — Calling export-clone workflow..." -ForegroundColor Yellow
$exportResult = Invoke-RestMethod -Uri $url -Method POST -Body $exportBody -ContentType "application/json" -TimeoutSec 60
$clonedConfig = $exportResult.clonedConfig
```

Show cloned config summary:
```
Export + Clone complete
  Source    : <from-service> [<from-country>]
  Target    : <to-country> | <datacenter>
  Service   : <cloned service name>
  EP domain : <cloned domain name>
```

If `--dry-run`, save clonedConfig to `config/<to-country>/service.json` and stop:
```
Dry run — cloned config saved to config/<TO>/service.json
No provisioning performed.
```

Step 2 — Full provision with cloned config:
```powershell
$provisionBody = @{
  resource        = "fullProvision"
  action          = "provision"
  apiToken        = $ctx.token
  skipEventPortal = $skipEp
  skipCluster     = $skipCluster
  payload         = $clonedConfig
} | ConvertTo-Json -Depth 20

Write-Host "Step 2/2 — Calling fullProvision workflow... (5-10 min)" -ForegroundColor Yellow
$provisionResult = Invoke-RestMethod -Uri $url -Method POST -Body $provisionBody -ContentType "application/json" -TimeoutSec 900
```

Display final result:
```
Replication Complete
  Source     : <from-service> [<from-country>]
  New service: <serviceId> [<to-country>]
  VPN Name   : <vpnName>
  Domain ID  : <domainId>
  Duration   : ~10 min

Config auto-saved to: config/<to-country>/service.json
Run /la-status to verify all workflows are healthy.
```

Save the clonedConfig to `config/<to-country>/service.json` so it's available for future /la-provision calls.

Example usage:
```
/la-replicate --from-service 5yv0da6tr85 --from-country DEV --to-country SG --datacenter aks-australiaeast
/la-replicate --from-service 5yv0da6tr85 --from-country DEV --to-country DE --datacenter aks-germanywestcentral --dry-run
/la-replicate --from-service 5yv0da6tr85 --from-country AU  --to-country NZ --datacenter aws-ap-southeast-2a --skip-ep
```
