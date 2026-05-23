Read and display a Solace service config file in a human-readable format — showing all objects, their names, topics, and relationships.

Arguments: $ARGUMENTS
- (empty)           List all available config files and ask which to show
- `<path>`          Show the config at the given path
- `dev`             Show config/dev/service.json
- `test`            Show config/test/service.json
- `prod`            Show config/prod/service.json
- `export`          Show config/dev-export/service.json
- `<country>`       Show config/<country>/service.json (e.g. `sg`, `de`, `au`)

First, find available configs:
```bash
find config -name "service.json" | sort
```

Then read the requested JSON file and display it as a structured summary:

```
Config: config/<env>/service.json
════════════════════════════════════════════════

  Service
  ────────────────────────────────────────────
  Name        : <name>
  ID          : <serviceId or 'not set'>
  Datacenter  : <datacenterId>
  Type/Class  : <serviceTypeId> / <serviceClassId>
  Environment : <environment>

  Event Portal — <domainName>
  ────────────────────────────────────────────
  Schemas (<count>):
    • <name>  [<type>  v<version>]

  Events (<count>):
    • <name>  →  topic: <topic>
               schema: <schemaRef>

  Applications (<count>):
    • <name>  produces: [<events>]
               consumes: [<events>]

  Cluster Management
  ────────────────────────────────────────────
  Client Profiles (<count>):
    • <name>

  ACL Profiles (<count>):
    • <name>
      publish : <publishDefault>  exceptions: <count>
      subscribe: <subscribeDefault> exceptions: <count>

  Client Usernames (<count>):
    • <name>  profile: <clientProfile>  acl: <aclProfile>

  Queues (<count>):
    • <name>  [<accessType>]
      subscriptions: <list>

  REST Delivery Points (<count>):
    • <name>
      consumers: <host>:<port>
      bindings : <queue>
════════════════════════════════════════════════
```

Also show a diff summary if the config has both `sourceCountry` and `targetCountry` set:
```
  Clone: <sourceCountry> → <targetCountry>
```

Example usage:
```
/config-show
/config-show dev
/config-show config/sg/service.json
/config-show export
```
