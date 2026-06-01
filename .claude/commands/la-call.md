Call any Solace Logic App operation via the main-dispatcher — the no-code equivalent of any Python CLI command.

Reads the dispatcher URL from `azure-logic-apps/parameters/parameters.json` and the API token from `.solace-context.json`. Sends the request and shows the formatted response.

Arguments: $ARGUMENTS

Parse the arguments to extract:
- `--resource <r>`       Target resource: service | eventPortal | cluster | fullProvision | exportClone
- `--sub-resource <sr>`  Sub-resource for eventPortal/cluster (e.g. domain, queue, clientProfile)
- `--action <a>`         Operation: create | get | list | update | delete | provision | add
- `--payload <json>`     JSON payload string (use single quotes on Windows)
- `--payload-file <p>`   Path to a JSON file to use as payload (alternative to --payload)
- `--skip-ep`            For fullProvision: skip Event Portal phase
- `--skip-cluster`       For fullProvision: skip cluster phase

If `--resource` or `--action` is missing, show the interactive menu:
```
Available resources:
  1. service        (list, get, create, update, delete)
  2. eventPortal    (subResource required — domain, schema, event, application, ...)
  3. cluster        (subResource required — provision, queue, clientProfile, ...)
  4. fullProvision  (full E2E: service + EP + cluster)
  5. exportClone    (export source service and clone to new country)

Select resource [1-5]:
```

Load credentials:
```powershell
$ctx    = Get-Content .solace-context.json | ConvertFrom-Json
$params = Get-Content azure-logic-apps/parameters/parameters.json | ConvertFrom-Json
$url    = $params.mainDispatcherUrl.value

# If mainDispatcherUrl is missing, try to find it
if (-not $url) {
  Write-Host "ERROR: dispatcherUrl not set. Run /la-urls first." -ForegroundColor Red
  exit 1
}
```

Build request body:
```powershell
$body = @{
  resource    = "<resource>"
  action      = "<action>"
  apiToken    = $ctx.token
  sempCredentials = @{
    sempBaseUrl  = $ctx.sempBaseUrl
    sempUsername = $ctx.sempUsername
    sempPassword = $ctx.sempPassword
    vpnName      = $ctx.vpnName
  }
  payload = <parsed payload>
} | ConvertTo-Json -Depth 20
```

Send the request:
```powershell
$response = Invoke-RestMethod `
  -Uri $url `
  -Method POST `
  -Body $body `
  -ContentType "application/json" `
  -TimeoutSec 900
```

Display the response in a readable format. If the response contains data (e.g. list of services), format it as a table.

Show timing:
```
Request  : POST main-dispatcher → cluster / queue / list
Duration : 0.8s
Status   : 200 OK

Response:
  queues:
    ORDER.CREATED.Q   exclusive   app-user   1 subscription
    PAYMENT.Q         exclusive   pay-user   2 subscriptions
```

Example usage:
```
/la-call --resource service --action list
/la-call --resource service --action create --payload '{"serviceName":"svc-nz","datacenterId":"aws-ap-southeast-2a","serviceTypeId":"enterprise","serviceClassId":"enterprise-250-nano"}'
/la-call --resource cluster --sub-resource queue --action list
/la-call --resource cluster --sub-resource queue --action create --payload '{"name":"TEST.Q","owner":"app-user","accessType":"exclusive"}'
/la-call --resource eventPortal --sub-resource domain --action list
/la-call --resource cluster --sub-resource queueSubscription --action add --payload '{"queueName":"TEST.Q","topic":"test/>"}'
/la-call --resource cluster --action provision --payload-file config/au/service.json
```
