# High Level Design — Solace Automation Logic App Orchestration

**Version:** 1.0  
**Date:** 2026-06-01  
**Platform:** Azure Logic Apps Standard (Stateful)  
**Architecture:** No-code / Low-code, HTTP-invoke based  

---

## 1. Executive Summary

The Solace Automation platform migrates the full Python-based Solace service lifecycle into Azure Logic App workflows. A single **main-dispatcher** workflow acts as the unified entry point for all operations. Callers — whether Postman, a parent Logic App, or any HTTP client — send one request with `resource` + `action` fields. The dispatcher routes to the correct child workflow via HTTP invoke, and each child handles its domain independently.

There is **no code**, **no Azure Functions**, **no Key Vault**, **no MSI**. Credentials flow as HTTP body fields.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL CALLERS                                 │
│                                                                          │
│   Postman  │  Parent Logic App  │  API Management  │  Any HTTP Client    │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │  POST { resource, action, apiToken, payload }
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        MAIN DISPATCHER                                  │
│                    (wf: main-dispatcher)                                │
│                                                                         │
│   Switch on "resource" field                                            │
│   ┌──────────┬────────────────┬─────────────┬────────────┬────────────┐ │
│   │ service  │  eventPortal   │   cluster   │fullProvision│exportClone│ │
│   └────┬─────┴───────┬────────┴──────┬──────┴──────┬─────┴──────┬─────┘ │
└────────│─────────────│───────────────│─────────────│────────────│───────┘
         │             │               │             │            │
         ▼             ▼               ▼             ▼            ▼
  ┌─────────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────┐ ┌────────────┐
  │  service-   │ │event-portal- │ │ cluster-  │ │  main-   │ │  export-   │
  │ management  │ │ management   │ │management │ │orchestrat│ │   clone    │
  │             │ │              │ │           │ │  or-fixed│ │            │
  │ list        │ │ domain CRUD  │ │ provision │ │          │ │ fetch src  │
  │ get         │ │ schema CRUD  │ │ CP CRUD   │ │          │ │ substitute │
  │ create+poll │ │ schemaVer    │ │ ACL CRUD  │ │          │ │ country    │
  │ update      │ │ event CRUD   │ │ CU CRUD   │ │          │ │ return cfg │
  │ delete      │ │ eventVer     │ │ queue CRUD│ │          │ │            │
  └─────────────┘ │ app CRUD     │ │ RDP CRUD  │ └────┬─────┘ └────────────┘
                  │ appVer       │ │ RC CRUD   │      │
                  └──────────────┘ │ QB CRUD   │      │ calls 3 children
                                   └───────────┘      ▼
                                                ┌─────────────────────────┐
                                                │ service-provisioning    │
                                                │ -fixed (create + poll)  │
                                                ├─────────────────────────┤
                                                │ event-portal-           │
                                                │ provisioning (bulk EP)  │
                                                ├─────────────────────────┤
                                                │ cluster-management      │
                                                │ (provision case)        │
                                                └─────────────────────────┘
```

---

## 3. Workflow Catalogue

| Workflow File | Role | Trigger | Called By |
|---|---|---|---|
| `main-dispatcher` | Router — single entry point | HTTP | External caller |
| `main-orchestrator-fixed` | Full E2E provision coordinator | HTTP | dispatcher (fullProvision) |
| `service-management` | Solace Cloud service CRUD | HTTP | dispatcher, direct |
| `service-provisioning-fixed` | Create service + poll until ready | HTTP | main-orchestrator |
| `event-portal-management` | Event Portal individual CRUD | HTTP | dispatcher, direct |
| `event-portal-provisioning` | Bulk EP create (domain+schemas+events+apps) | HTTP | main-orchestrator |
| `cluster-management` | SEMP broker CRUD + bulk provision | HTTP | dispatcher, main-orchestrator, direct |
| `export-clone` | Export service config + country substitution | HTTP | dispatcher, direct |

---

## 4. Orchestration Patterns

### Pattern A — Single Resource CRUD (most common)

One request → dispatcher → one child workflow → Solace API → response back.

```
Caller
  │
  │ POST { resource, subResource, action, apiToken, payload }
  │
  ▼
main-dispatcher
  │
  │ Switch on resource
  │
  ├─► service-management      (resource = "service")
  │       │ Switch on action
  │       ├─► GET  /api/v0/services          (list / get)
  │       ├─► POST /api/v0/services          (create + poll)
  │       ├─► PATCH /api/v0/services/{id}   (update)
  │       └─► DELETE /api/v0/services/{id}  (delete)
  │
  ├─► event-portal-management (resource = "eventPortal")
  │       │ Switch on subResource → Switch on action
  │       └─► GET/POST/PATCH/DELETE /api/v2/architecture/{subResource}
  │
  └─► cluster-management      (resource = "cluster")
          │ Switch on subResource → Switch on action
          └─► GET/POST/PATCH/DELETE {sempBaseUrl}/msgVpns/{vpn}/{subResource}
```

**Latency:** Single HTTP hop. Sub-second for list/get/delete. 5–10 min for service create (poll loop).

---

### Pattern B — Full End-to-End Provision

Creates a complete Solace environment: service + Event Portal objects + cluster config.

```
Caller
  │
  │ POST { resource:"fullProvision", apiToken, skipEventPortal, skipCluster, payload:{config} }
  │
  ▼
main-dispatcher
  │
  │ Invoke solace-mainOrchestratorUrl (HTTP POST)
  │
  ▼
main-orchestrator-fixed
  │
  │ 1. Init variables (serviceId, vpnName, sempBaseUrl, sempUsername, sempPassword, domainId)
  │
  │ 2. SCOPE: Service Provisioning
  │     │
  │     ├─ IF config.service.serviceId not empty
  │     │   └─► Use existing service (set serviceId variable)
  │     │
  │     └─ ELSE
  │         │ Invoke serviceProvisioningUrl (HTTP POST)
  │         ▼
  │         service-provisioning-fixed
  │           │ POST /api/v0/services   ← create
  │           │ GET  /api/v0/services/{id}  ← poll every 15s until "completed"
  │           │ GET  /api/v0/services/{id}  ← fetch final details
  │           └─► Returns: { serviceId, vpnName, sempBaseUrl, sempUsername, sempPassword }
  │         │
  │         └─ Set variables from response
  │
  │ 3. SCOPE: Event Portal Provisioning (skipped if skipEventPortal=true)
  │     │ Invoke eventPortalUrl (HTTP POST)
  │     ▼
  │     event-portal-provisioning
  │       │ POST /api/v2/architecture/applicationDomains
  │       │ For each schema:
  │       │   POST /api/v2/architecture/schemas
  │       │   POST /api/v2/architecture/schemaVersions
  │       │ For each event:
  │       │   POST /api/v2/architecture/events
  │       │   POST /api/v2/architecture/eventVersions
  │       │ For each application:
  │       │   POST /api/v2/architecture/applications
  │       │   POST /api/v2/architecture/applicationVersions
  │       └─► Returns: { domainId, schemasCreated, eventsCreated, applicationsCreated }
  │     │
  │     └─ Set domainId variable from response
  │
  │ 4. SCOPE: Cluster Provisioning (skipped if skipCluster=true)
  │     │ Invoke clusterManagementUrl (HTTP POST)
  │     │ Body: { action:"provision", sempCredentials:{...}, payload:{clusterConfig:{...}} }
  │     ▼
  │     cluster-management (provision case)
  │       │ For each clientProfile:  POST {sempBase}/clientProfiles
  │       │ For each aclProfile:     POST {sempBase}/aclProfiles
  │       │   For each pubException: POST {sempBase}/aclProfiles/{n}/publishTopicExceptions
  │       │   For each subException: POST {sempBase}/aclProfiles/{n}/subscribeTopicExceptions
  │       │ For each clientUsername: POST {sempBase}/clientUsernames
  │       │ For each queue:          POST {sempBase}/queues
  │       │   For each subscription: POST {sempBase}/queues/{n}/subscriptions
  │       │ For each RDP:            POST {sempBase}/restDeliveryPoints
  │       │   For each consumer:     POST {sempBase}/restDeliveryPoints/{n}/restConsumers
  │       │   For each queueBinding: POST {sempBase}/restDeliveryPoints/{n}/queueBindings
  │       └─► Returns: { status:"success", vpnName }
  │
  └─► Returns: { status:"success", serviceId, vpnName, domainId }
```

**Latency:** 10–15 minutes total (dominated by service creation poll).

---

### Pattern C — Export and Clone

Copies a source service config to a new country, substituting all country codes throughout.

```
Caller
  │
  │ POST { resource:"exportClone", apiToken, payload:{ sourceServiceId, sourceCountry,
  │         targetCountry, targetDatacenter, targetServiceName } }
  │
  ▼
main-dispatcher
  │
  │ Invoke exportCloneUrl (HTTP POST)
  │
  ▼
export-clone
  │
  │ 1. GET /api/v0/services/{sourceServiceId}
  │       └─► Fetch: name, datacenterId, serviceTypeId, serviceClassId
  │
  │ 2. Build base config object:
  │       { service: { name: replace(sourceName, srcCountry, tgtCountry) },
  │         eventPortal: { ... empty ... },
  │         clusterManagement: { ... empty ... } }
  │
  │ 3. JSON string replace (3 passes — uppercase, lowercase, title case):
  │       "AU" → "NZ"  |  "au" → "nz"  |  "Au" → "Nz"
  │
  │ 4. Parse final clonedConfig JSON
  │
  └─► Returns: { status:"success", sourceCountry, targetCountry, clonedConfig:{...} }

Caller then takes clonedConfig and calls fullProvision:

  │
  │ POST { resource:"fullProvision", apiToken, payload: <clonedConfig from above> }
  │
  ▼
  (follows Pattern B)
```

---

### Pattern D — Individual Cluster CRUD (without dispatcher)

For callers who already know the SEMP credentials and want to target a specific resource.

```
Caller
  │
  │ POST directly to cluster-management trigger URL
  │ Body: { action, subResource, sempCredentials:{...}, payload:{...} }
  │
  ▼
cluster-management
  │
  │ Outer Switch on: if(empty(subResource), action, subResource)
  │
  ├─► "clientProfile" → Inner Switch on action → create/get/list/update/delete
  ├─► "aclProfile"    → Inner Switch on action → create/get/list/delete
  ├─► "publishException" → Inner Switch on action → add/list/delete
  ├─► "subscribeException" → Inner Switch on action → add/list/delete
  ├─► "clientUsername" → Inner Switch on action → create/get/list/update/delete
  ├─► "queue"          → Inner Switch on action → create/get/list/update/delete
  ├─► "queueSubscription" → Inner Switch on action → add/list/delete
  ├─► "rdp"            → Inner Switch on action → create/get/list/delete
  ├─► "restConsumer"   → Inner Switch on action → create/list/update/delete
  ├─► "queueBinding"   → Inner Switch on action → add/list/delete
  └─► "provision"      → Bulk foreach provision (all resources)
```

---

## 5. Sequence Diagrams

### 5.1 Service Create (with poll)

```
Caller          Dispatcher      service-management     Solace Cloud API
  │                 │                  │                      │
  │──POST create──►│                  │                      │
  │                 │──HTTP invoke───►│                      │
  │                 │                  │──POST /services────►│
  │                 │                  │◄──{ serviceId,──────│
  │                 │                  │    state:pending }   │
  │                 │                  │                      │
  │                 │           ┌──────┘                      │
  │                 │           │  Until loop (every 15s)    │
  │                 │           │──GET /services/{id}────────►│
  │                 │           │◄── state: "pending" ────────│
  │                 │           │    (repeat...)              │
  │                 │           │──GET /services/{id}────────►│
  │                 │           │◄── state: "completed" ──────│
  │                 │           └──────►│                     │
  │                 │                  │──GET /services/{id}─►│
  │                 │                  │◄── full details ──────│
  │                 │◄──{ serviceId,───│                      │
  │                 │    vpnName,      │                      │
  │                 │    sempBaseUrl,  │                      │
  │                 │    sempUser,     │                      │
  │                 │    sempPass }    │                      │
  │◄── 200 ─────────│                  │                      │
```

### 5.2 Event Portal Domain Create

```
Caller      Dispatcher    event-portal-management    EP API (v2/architecture)
  │              │                 │                          │
  │─POST create─►│                 │                          │
  │              │──invoke────────►│                          │
  │              │                 │─POST /applicationDomains►│
  │              │                 │◄── { data: { id, name } }│
  │◄── 200 ──────│◄── { data } ────│                          │
```

### 5.3 Full End-to-End Provision

```
Caller    Dispatcher   Orchestrator  SvcProvision  EPProvision  ClusterMgmt
  │           │              │             │             │            │
  ├─POST─────►│              │             │             │            │
  │           │──invoke─────►│             │             │            │
  │           │              │──invoke────►│             │            │
  │           │              │             │─create svc──►            │
  │           │              │             │  (poll 15s×N)            │
  │           │              │◄──creds─────│             │            │
  │           │              │──invoke────────────────►  │            │
  │           │              │             │  create domain+schemas   │
  │           │              │             │    +events+apps ─────►   │
  │           │              │◄──domainId─────────────── │            │
  │           │              │──invoke──────────────────────────────►│
  │           │              │             │             │ bulk create│
  │           │              │◄─────────────────────────────────────│
  │           │◄──────────── │             │             │            │
  │◄──200─────│              │             │             │            │
```

### 5.4 Export Clone → Provision

```
Caller          Dispatcher        export-clone         main-orchestrator
  │                 │                  │                      │
  │──exportClone───►│                  │                      │
  │                 │──invoke─────────►│                      │
  │                 │                  │──GET sourceService──►(Solace API)
  │                 │                  │──build clonedConfig  │
  │                 │                  │──replace AU→NZ ×3    │
  │◄──clonedConfig──│◄─────────────────│                      │
  │                 │                  │                      │
  │──fullProvision──►│                 │                      │
  │   payload=clonedConfig             │                      │
  │                 │──invoke───────────────────────────────►│
  │                 │                  │             (Pattern B flow)
  │◄──200───────────│                  │                      │
```

---

## 6. Workflow Parameter Map

### main-orchestrator-fixed parameters (set in workflow designer)

| Parameter | Points To | Used In |
|---|---|---|
| `serviceProvisioningUrl` | `service-provisioning-fixed` trigger URL | Scope_Service_Provisioning |
| `eventPortalUrl` | `event-portal-provisioning` trigger URL | Scope_Event_Portal_Provisioning |
| `clusterManagementUrl` | `cluster-management` trigger URL | Scope_Cluster_Provisioning |

### main-dispatcher parameters

| Parameter | Points To |
|---|---|
| `serviceManagementUrl` | `service-management` trigger URL |
| `eventPortalManagementUrl` | `event-portal-management` trigger URL |
| `clusterManagementUrl` | `cluster-management` trigger URL |
| `solace-mainOrchestratorUrl` | `main-orchestrator-fixed` trigger URL |
| `exportCloneUrl` | `export-clone` trigger URL |

---

## 7. Input Payload Schema

### Dispatcher (all operations)

```json
{
  "resource":       "service | eventPortal | cluster | fullProvision | exportClone",
  "action":         "create | get | list | update | delete | provision | add",
  "subResource":    "domain | schema | schemaVersion | event | eventVersion | application | applicationVersion | clientProfile | aclProfile | publishException | subscribeException | clientUsername | queue | queueSubscription | rdp | restConsumer | queueBinding",
  "apiToken":       "Solace Cloud Bearer token",
  "sempCredentials": {
    "sempBaseUrl":  "https://<broker>:943/SEMP/v2/config",
    "sempUsername": "mission-control-manager",
    "sempPassword": "...",
    "vpnName":      "msgvpn-xxxxx"
  },
  "skipEventPortal": false,
  "skipCluster":     false,
  "payload":         {}
}
```

### Auto-chained data (between orchestrator and children)

```
service-provisioning-fixed response → orchestrator variables:
  serviceId, vpnName, sempBaseUrl, sempUsername, sempPassword

event-portal-provisioning response → orchestrator variables:
  domainId

cluster-management does not return data to orchestrator (fire and complete)
```

---

## 8. Error Handling

| Scenario | Behaviour |
|---|---|
| Invalid `resource` | Dispatcher returns `400` with valid values list |
| Invalid `action` or `subResource` | Child workflow returns `400` from inner Switch default |
| Service creation failed / timed out | service-management returns `500` with `creationState` |
| SEMP call fails | HTTP action propagates the SEMP error response and status code |
| Child workflow unreachable (bad URL param) | HTTP invoke returns `502`/timeout; orchestrator scope fails |

---

## 9. Deployment Topology

```
┌─────────────────────────────────────────────────────────┐
│           Azure Logic Apps Standard App                  │
│           (e.g. wf-solace-automation)                   │
│                                                          │
│  Workflows (all Stateful):                               │
│  ┌────────────────────────┐                              │
│  │ main-dispatcher         │  ← public HTTP trigger      │
│  ├────────────────────────┤                              │
│  │ main-orchestrator-fixed │  ← public HTTP trigger      │
│  ├────────────────────────┤                              │
│  │ service-management      │  ← public HTTP trigger      │
│  ├────────────────────────┤                              │
│  │ service-provisioning-   │  ← public HTTP trigger      │
│  │ fixed                   │                              │
│  ├────────────────────────┤                              │
│  │ event-portal-management │  ← public HTTP trigger      │
│  ├────────────────────────┤                              │
│  │ event-portal-           │  ← public HTTP trigger      │
│  │ provisioning            │                              │
│  ├────────────────────────┤                              │
│  │ cluster-management      │  ← public HTTP trigger      │
│  ├────────────────────────┤                              │
│  │ export-clone            │  ← public HTTP trigger      │
│  └────────────────────────┘                              │
│                                                          │
│  Connections: SQL (optional), CosmosDB (optional)        │
│  No Key Vault. No MSI. No Blob Storage.                  │
│                                                          │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
 Solace Cloud API              Solace Broker (SEMP)
 api.solace.cloud              <broker>.messaging.solace.cloud:943
 /api/v0/services              /SEMP/v2/config/msgVpns/{vpn}/...
 /api/v2/architecture/...      Basic Auth (username + password)
 Bearer token auth
```

---

## 10. Recommended Call Sequence (New Country Rollout)

```
Step 1  ──  exportClone
              source: existing AU service
              target: NZ, new datacenter
              → returns clonedConfig JSON

Step 2  ──  fullProvision  (payload = clonedConfig from step 1)
              skipEventPortal: false
              skipCluster: false
              → creates NZ service, EP domain, cluster objects

Step 3  ──  cluster / queue / list
              verify queues exist

Step 4  ──  cluster / queueSubscription / add
              add any additional topic subscriptions

Step 5  ──  eventPortal / applicationVersion / create
              wire event version IDs into app version
```

---

## 11. Security Notes

| Item | Current Approach | Production Recommendation |
|---|---|---|
| Solace API Token | Passed in HTTP body | Store in Azure API Management policy or Logic App parameter |
| SEMP Password | Passed in HTTP body | Store in Logic App workflow parameters (encrypted at rest) |
| Trigger URL SAS | Per-workflow SAS in URL | Add IP restriction in Logic App access control |
| Auth between workflows | SAS token in URL | Add IP allowlist to restrict internal workflow-to-workflow calls |

---

*Generated by Claude Code — Solace Automation v1.0*
