# Azure Logic Apps - Solace Automation

This directory contains Azure Logic App workflows that replicate the Python CLI Solace automation solution using **pure no-code Logic Apps** with direct API calls to Solace Cloud.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure Logic Apps                         │
│                                                             │
│  ┌──────────────────┐       ┌──────────────────┐            │
│  │ Main Orchestrator│─────▶│Service Provision │            │
│  └──────────────────┘       └──────────────────┘            │
│           │                                                 │
│           ├─────────────────┬──────────────────┐            │
│           ▼                 ▼                  ▼            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │Event Portal  │  │   Cluster    │  │Export/Clone  │       │
│  │ Provisioning │  │  Management  │  │              │       │ 
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │      Solace Cloud APIs              │
        ├─────────────────────────────────────┤
        │ • Cloud Service API                 │
        │ • Event Portal Designer API         │
        │ • SEMP v2 Config API                │
        └─────────────────────────────────────┘
```

## 📁 Directory Structure

```
azure-logic-apps/
├── workflows/                      # Logic App workflow definitions
│   ├── main-orchestrator.json      # Main orchestration workflow
│   ├── service-provisioning.json   # Service creation & polling
│   ├── event-portal-provisioning.json  # EP objects (domains, schemas, events, apps)
│   ├── cluster-management.json     # SEMP API (profiles, ACLs, queues, RDP)
│   └── export-clone.json           # Export & clone configurations
├── parameters/                     # Deployment parameters
│   └── parameters.json             # Environment-specific parameters
├── connections/                    # API connections
│   └── connections.json            # Blob Storage & Key Vault connections
├── scripts/                        # Deployment scripts
│   └── deploy.ps1                  # PowerShell deployment script
└── README.md                       # This file
```

## 🚀 Workflows

### 1. Main Orchestrator (`main-orchestrator.json`)
**Purpose:** Coordinates the entire provisioning process

**Trigger:** HTTP Request (Manual)

**Input Schema:**
```json
{
  "configPath": "config/au/service.json",
  "environment": "dev",
  "skipEventPortal": false,
  "skipCluster": false
}
```

**Flow:**
1. Load configuration from Blob Storage
2. Get API token from Key Vault
3. Call Service Provisioning workflow (if needed)
4. Call Event Portal Provisioning workflow
5. Call Cluster Management workflow
6. Return success response

### 2. Service Provisioning (`service-provisioning.json`)
**Purpose:** Create and configure Solace Cloud messaging service

**API Calls:**
- `POST /api/v0/services` - Create service
- `GET /api/v0/services/{id}` - Poll status (Until loop)

**Features:**
- Automatic polling until service is ready
- SEMP credentials extraction
- 15-second polling interval
- 10-minute timeout

### 3. Event Portal Provisioning (`event-portal-provisioning.json`)
**Purpose:** Create Event Portal design objects

**API Calls:**
- `POST /applicationDomains` - Create domain
- `POST /schemas` - Create schemas
- `POST /schemaVersions` - Create schema versions
- `POST /events` - Create events
- `POST /eventVersions` - Create event versions (with topic parsing)
- `POST /applications` - Create applications
- `POST /applicationVersions` - Create app versions

**Features:**
- Name-based schema/event references (portable across environments)
- Automatic topic-to-addressLevels conversion
- Schema-to-event linking
- Event-to-application linking

### 4. Cluster Management (`cluster-management.json`)
**Purpose:** Configure broker runtime objects via SEMP API

**API Calls (SEMP v2):**
- `POST /msgVpns/{vpn}/clientProfiles`
- `POST /msgVpns/{vpn}/aclProfiles`
- `POST /msgVpns/{vpn}/aclProfiles/{name}/publishTopicExceptions`
- `POST /msgVpns/{vpn}/aclProfiles/{name}/subscribeTopicExceptions`
- `POST /msgVpns/{vpn}/clientUsernames`
- `POST /msgVpns/{vpn}/queues`
- `POST /msgVpns/{vpn}/queues/{name}/subscriptions`
- `POST /msgVpns/{vpn}/restDeliveryPoints`
- `POST /msgVpns/{vpn}/restDeliveryPoints/{rdp}/restConsumers`
- `POST /msgVpns/{vpn}/restDeliveryPoints/{rdp}/queueBindings`

**Authentication:** HTTP Basic Auth (SEMP credentials)

### 5. Export/Clone (`export-clone.json`)
**Purpose:** Clone configuration from one country to another

**Features:**
- Country code substitution (upper, lower, title case)
- Service name transformation
- Datacenter replacement
- Save cloned config to Blob Storage

**String Replacement Logic:**
```
AU → SG
au → sg
Au → Sg
```

## 🔧 Deployment

### Prerequisites

1. **Azure CLI** installed and configured
2. **Azure Subscription** with appropriate permissions
3. **PowerShell 7+** (for deployment script)

### Step 1: Configure Parameters

Edit `parameters/parameters.json`:

```json
{
  "logicAppName": "solace-automation",
  "location": "eastus",
  "keyVaultName": "solace-keyvault",
  "storageAccountName": "solaceconfigs"
}
```

### Step 2: Run Deployment Script

```powershell
cd azure-logic-apps/scripts

./deploy.ps1 `
  -ResourceGroupName "solace-automation-rg" `
  -Location "eastus" `
  -SubscriptionId "your-subscription-id" `
  -Environment "dev"
```

### Step 3: Configure Secrets

Add Solace API tokens to Key Vault:

```bash
az keyvault secret set \
  --vault-name solace-keyvault \
  --name solace-api-token-dev \
  --value "your-api-token"

az keyvault secret set \
  --vault-name solace-keyvault \
  --name solace-api-token-test \
  --value "your-api-token"

az keyvault secret set \
  --vault-name solace-keyvault \
  --name solace-api-token-prod \
  --value "your-api-token"
```

### Step 4: Upload Configuration Files

Upload your configuration files to Blob Storage:

```bash
az storage blob upload \
  --account-name solaceconfigs \
  --container-name solace-configs \
  --name config/au/service.json \
  --file config/au/service.json \
  --auth-mode login
```

## 📝 Configuration File Format

Configuration files follow the same schema as the Python CLI:

```json
{
  "sourceCountry": "AU",
  "targetCountry": "AU",
  "environment": "au",
  "service": {
    "serviceId": "",
    "name": "solace-automation-au",
    "datacenterId": "aks-australiaeast",
    "serviceTypeId": "developer",
    "serviceClassId": "developer"
  },
  "eventPortal": {
    "domainName": "AcmeAU",
    "domainDescription": "Acme AU integration domain",
    "schemas": [
      {
        "name": "OrderPayloadSchema",
        "type": "jsonSchema",
        "version": "1.0.0",
        "content": { /* JSON Schema */ }
      }
    ],
    "events": [
      {
        "name": "OrderCreated",
        "version": "1.0.0",
        "topic": "acme/au/orders/{orderId}/created",
        "schemaRef": "OrderPayloadSchema"
      }
    ],
    "applications": [
      {
        "name": "AcmeSourceSystem-AU",
        "type": "standard",
        "version": "1.0.0",
        "produces": ["OrderCreated"],
        "consumes": []
      }
    ]
  },
  "clusterManagement": {
    "vpnName": "",
    "clientProfiles": [
      { "name": "acme-au-profile" }
    ],
    "aclProfiles": [
      {
        "name": "acme-au-acl",
        "publishDefault": "disallow",
        "subscribeDefault": "disallow",
        "publishExceptions": ["acme/au/>"],
        "subscribeExceptions": ["acme/au/>"]
      }
    ],
    "clientUsernames": [
      {
        "name": "acme-au-user",
        "password": "SecurePassword123!",
        "clientProfile": "acme-au-profile",
        "aclProfile": "acme-au-acl",
        "enabled": true
      }
    ],
    "queues": [
      {
        "name": "acme-au-orders-q",
        "accessType": "non-exclusive",
        "subscriptions": ["acme/au/orders/>"]
      }
    ],
    "restDeliveryPoints": [
      {
        "name": "acme-au-rdp",
        "clientProfile": "acme-au-profile",
        "enabled": true,
        "postRequestTarget": "/api/v1/events",
        "consumers": [
          {
            "name": "acme-au-consumer",
            "host": "target-au.example.com",
            "port": 443,
            "tlsEnabled": true,
            "httpMethod": "post"
          }
        ],
        "queueBindings": ["acme-au-orders-q"]
      }
    ]
  }
}
```

## 🔄 Usage Examples

### Example 1: Provision New Service

```bash
# Trigger via HTTP POST
curl -X POST \
  "https://solace-automation-dev.azurewebsites.net/api/main-orchestrator/triggers/manual/invoke?api-version=2022-05-01&sp=/triggers/manual/run&sv=1.0&sig=<signature>" \
  -H "Content-Type: application/json" \
  -d '{
    "configPath": "config/au/service.json",
    "environment": "dev",
    "skipEventPortal": false,
    "skipCluster": false
  }'
```

### Example 2: Clone Configuration

```bash
# Trigger Export/Clone workflow
curl -X POST \
  "https://solace-automation-dev.azurewebsites.net/api/export-clone/triggers/manual/invoke?api-version=2022-05-01&sp=/triggers/manual/run&sv=1.0&sig=<signature>" \
  -H "Content-Type: application/json" \
  -d '{
    "sourceServiceId": "abc123",
    "sourceCountry": "AU",
    "targetCountry": "SG",
    "targetDatacenter": "aks-australiaeast",
    "targetServiceName": "solace-automation-sg",
    "apiToken": "Bearer eyJ..."
  }'
```

### Example 3: Event Portal Only

```bash
curl -X POST \
  "https://solace-automation-dev.azurewebsites.net/api/main-orchestrator/triggers/manual/invoke?..." \
  -H "Content-Type: application/json" \
  -d '{
    "configPath": "config/au/service.json",
    "environment": "dev",
    "skipEventPortal": false,
    "skipCluster": true
  }'
```

## 📊 Monitoring

### Application Insights

All workflows are instrumented with Application Insights:

```bash
# View workflow runs
az monitor app-insights query \
  --app solace-insights-dev \
  --analytics-query "requests | where name contains 'main-orchestrator' | top 10 by timestamp desc"
```

### Logic App Monitoring

View workflow runs in Azure Portal:
1. Navigate to Logic App resource
2. Click "Workflows" → Select workflow
3. View "Run History"

## 🔐 Security

### Key Vault Integration

- API tokens stored in Key Vault
- Logic App uses Managed Identity
- Secrets retrieved at runtime

### RBAC Permissions

Required permissions:
- Logic App: `Key Vault Secrets User`
- Storage Account: `Storage Blob Data Contributor`

## 🆚 Comparison: Python CLI vs Logic Apps

| Feature | Python CLI | Logic Apps |
|---------|-----------|------------|
| **Deployment** | Manual execution | Automated, scheduled, or triggered |
| **Monitoring** | Custom logging | Built-in Azure Monitor |
| **Scalability** | Single-threaded | Auto-scales |
| **Cost** | Compute time only | Per-execution pricing |
| **Maintenance** | Code updates | Visual designer updates |
| **Integration** | Manual | 400+ connectors |
| **Error Handling** | Custom try-catch | Built-in retry policies |
| **State Management** | File-based | Stateful workflows |

## 🐛 Troubleshooting

### Common Issues

**Issue:** Workflow fails with "Connection not found"
**Solution:** Ensure API connections are deployed and authorized

**Issue:** SEMP API returns 401 Unauthorized
**Solution:** Verify SEMP credentials are correctly extracted from service details

**Issue:** Event Portal API returns 400 Bad Request
**Solution:** Check topic format and addressLevels structure

### Debug Mode

Enable detailed logging:

```bash
az logicapp config appsettings set \
  --name solace-automation-dev \
  --resource-group solace-automation-rg \
  --settings "WORKFLOWS_RUNTIME_LOGGING_LEVEL=Verbose"
```

## 📚 Additional Resources

- [Azure Logic Apps Documentation](https://docs.microsoft.com/azure/logic-apps/)
- [Solace Cloud API Reference](https://docs.solace.com/Cloud/ght_api_reference.htm)
- [SEMP v2 Config API](https://docs.solace.com/API-Developer-Online-Ref-Documentation/swagger-ui/config/index.html)
- [Event Portal Designer API](https://docs.solace.com/Cloud/Event-Portal/event-portal-api-reference.htm)

## 🤝 Contributing

To add new workflows:

1. Create workflow JSON in `workflows/` directory
2. Update `deploy.ps1` to include new workflow
3. Update this README with workflow documentation
4. Test deployment in dev environment

## 📄 License

Same license as the parent Solace automation project.

---

**Note:** This is a **pure no-code solution** - all logic is implemented using Logic Apps expressions and HTTP actions. No Azure Functions or custom code required.