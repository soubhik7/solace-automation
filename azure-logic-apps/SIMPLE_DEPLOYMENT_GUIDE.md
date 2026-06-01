# Simplified Azure Logic Apps Deployment Guide

## Overview
This guide provides step-by-step instructions for deploying the Solace automation Logic Apps with simplified configuration using connection strings and hardcoded values (no Managed Identity or Key Vault required).

## Prerequisites
- Azure subscription
- Azure Storage Account
- Solace Cloud API token
- PowerShell or Azure CLI installed

## Step 1: Prepare Azure Storage Account

### 1.1 Create Storage Account (if not exists)
```powershell
# Using Azure CLI
az storage account create `
  --name <your-storage-account-name> `
  --resource-group <your-resource-group> `
  --location <location> `
  --sku Standard_LRS

# Or using Azure Portal:
# Navigate to Storage Accounts > Create > Fill in details
```

### 1.2 Create Container
```powershell
# Get storage account key
$storageKey = az storage account keys list `
  --account-name <your-storage-account-name> `
  --resource-group <your-resource-group> `
  --query "[0].value" -o tsv

# Create container
az storage container create `
  --name solace-configs `
  --account-name <your-storage-account-name> `
  --account-key $storageKey
```

### 1.3 Get Connection String
```powershell
az storage account show-connection-string `
  --name <your-storage-account-name> `
  --resource-group <your-resource-group> `
  --query connectionString -o tsv
```

Copy this connection string - you'll need it for the parameters file.

## Step 2: Update Configuration Files

### 2.1 Update parameters.json
Edit `azure-logic-apps/parameters/parameters.json`:

```json
{
    "solaceCloudApiUrl": {
        "type": "String",
        "value": "https://api.solace.cloud/api/v2"
    },
    "solaceEventPortalApiUrl": {
        "type": "String",
        "value": "https://api.solace.cloud/api/v2/architecture"
    },
    "solaceSempApiBaseUrl": {
        "type": "String",
        "value": "https://{msgVpnName}.messaging.solace.cloud:943/SEMP/v2/config"
    },
    "solaceApiToken": {
        "type": "String",
        "value": "YOUR_ACTUAL_SOLACE_API_TOKEN"
    },
    "storageAccountName": {
        "type": "String",
        "value": "YOUR_STORAGE_ACCOUNT_NAME"
    },
    "configContainerName": {
        "type": "String",
        "value": "solace-configs"
    },
    "AzureBlobStorage_connectionString": {
        "type": "String",
        "value": "YOUR_STORAGE_CONNECTION_STRING_FROM_STEP_1.3"
    }
}
```

**Replace:**
- `YOUR_ACTUAL_SOLACE_API_TOKEN` with your Solace Cloud API token
- `YOUR_STORAGE_ACCOUNT_NAME` with your storage account name
- `YOUR_STORAGE_CONNECTION_STRING_FROM_STEP_1.3` with the connection string from Step 1.3

### 2.2 Update connections.json
Edit `azure-logic-apps/connections/connections.json` and replace placeholders:

```json
{
  "managedApiConnections": {
    "azureblob": {
      "api": {
        "id": "/subscriptions/{subscription-id}/providers/Microsoft.Web/locations/{location}/managedApis/azureblob"
      },
      "authentication": {
        "type": "Raw",
        "scheme": "Key",
        "parameter": "@appsetting('AzureBlobStorage_connectionString')"
      },
      "connection": {
        "id": "/subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.Web/connections/azureblob-connection"
      },
      "connectionRuntimeUrl": "https://{connection-runtime-url}.azure-apihub.net/apim/azureblob/{connection-id}"
    }
  }
}
```

**Replace:**
- `{subscription-id}` with your Azure subscription ID
- `{location}` with your Azure region (e.g., eastus2)
- `{resource-group}` with your resource group name
- `{connection-runtime-url}` and `{connection-id}` will be populated after creating the connection

## Step 3: Create API Connection

### 3.1 Create Blob Storage Connection
```powershell
# Get your subscription ID
$subscriptionId = az account show --query id -o tsv

# Get storage connection string
$connectionString = az storage account show-connection-string `
  --name <your-storage-account-name> `
  --resource-group <your-resource-group> `
  --query connectionString -o tsv

# Create the API connection
az resource create `
  --resource-group <your-resource-group> `
  --resource-type Microsoft.Web/connections `
  --name azureblob-connection `
  --location <location> `
  --properties "{
    \"api\": {
      \"id\": \"/subscriptions/$subscriptionId/providers/Microsoft.Web/locations/<location>/managedApis/azureblob\"
    },
    \"displayName\": \"Azure Blob Storage Connection\",
    \"parameterValues\": {
      \"accountName\": \"<your-storage-account-name>\",
      \"accessKey\": \"<your-storage-account-key>\"
    }
  }"
```

### 3.2 Get Connection Runtime URL
```powershell
az resource show `
  --resource-group <your-resource-group> `
  --resource-type Microsoft.Web/connections `
  --name azureblob-connection `
  --query properties.connectionRuntimeUrl -o tsv
```

Update the `connectionRuntimeUrl` in connections.json with this value.

## Step 4: Create Logic App

### 4.1 Create Logic App (Standard)
```powershell
# Create App Service Plan (if not exists)
az appservice plan create `
  --name <plan-name> `
  --resource-group <your-resource-group> `
  --location <location> `
  --sku WS1 `
  --is-linux

# Create Logic App
az logicapp create `
  --name <logic-app-name> `
  --resource-group <your-resource-group> `
  --plan <plan-name> `
  --storage-account <your-storage-account-name>
```

### 4.2 Configure App Settings
```powershell
# Set the blob storage connection string
az logicapp config appsettings set `
  --name <logic-app-name> `
  --resource-group <your-resource-group> `
  --settings AzureBlobStorage_connectionString="$connectionString"
```

## Step 5: Deploy Workflows

### 5.1 Using Azure CLI
```powershell
# Navigate to the azure-logic-apps directory
cd azure-logic-apps

# Deploy each workflow
az logicapp deployment source config-zip `
  --name <logic-app-name> `
  --resource-group <your-resource-group> `
  --src workflows.zip
```

### 5.2 Using VS Code
1. Install "Azure Logic Apps (Standard)" extension
2. Open the azure-logic-apps folder in VS Code
3. Right-click on the Logic App in Azure view
4. Select "Deploy to Logic App"
5. Choose your Logic App

### 5.3 Manual Deployment via Portal
1. Go to Azure Portal
2. Navigate to your Logic App
3. Go to "Workflows" blade
4. Click "Add"
5. Copy/paste the workflow JSON from each file in `workflows/` folder
6. Save each workflow

## Step 6: Upload Configuration Files

### 6.1 Upload Sample Config
```powershell
# Upload a sample configuration file
az storage blob upload `
  --account-name <your-storage-account-name> `
  --container-name solace-configs `
  --name config/dev/service.json `
  --file config/dev/service.json `
  --account-key <your-storage-account-key>
```

## Step 7: Test the Workflows

### 7.1 Get Workflow Callback URL
```powershell
# Get the main orchestrator workflow URL
az rest --method post `
  --uri "/subscriptions/$subscriptionId/resourceGroups/<your-resource-group>/providers/Microsoft.Web/sites/<logic-app-name>/hostruntime/runtime/webhooks/workflow/api/management/workflows/main-orchestrator/triggers/manual/listCallbackUrl?api-version=2020-05-01-preview"
```

### 7.2 Test with Postman or cURL
```bash
curl -X POST "https://<logic-app-name>.azurewebsites.net:443/api/main-orchestrator/triggers/manual/invoke?api-version=2020-05-01-preview&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=<signature>" \
  -H "Content-Type: application/json" \
  -d '{
    "configPath": "config/dev/service.json",
    "environment": "dev",
    "skipEventPortal": false,
    "skipCluster": false
  }'
```

## Step 8: Monitor Execution

### 8.1 View Run History
```powershell
# List workflow runs
az logicapp show `
  --name <logic-app-name> `
  --resource-group <your-resource-group>
```

### 8.2 Using Azure Portal
1. Go to your Logic App in Azure Portal
2. Click on "Workflows"
3. Select "main-orchestrator"
4. View "Run History"
5. Click on a run to see detailed execution

## Troubleshooting

### Issue: "Connection not found"
**Solution:** Ensure the connection was created successfully and the connection ID in connections.json matches the actual resource ID.

### Issue: "Cannot read from blob storage"
**Solution:** 
- Verify the connection string is correct
- Check that the container name is "solace-configs"
- Ensure the blob path in the request matches the uploaded file

### Issue: "Unauthorized" when calling Solace APIs
**Solution:**
- Verify your Solace API token is correct in parameters.json
- Check that the token has the required permissions
- Ensure the token hasn't expired

### Issue: "Workflow validation failed"
**Solution:**
- Use the fixed workflow files (main-orchestrator-fixed.json, service-provisioning-fixed.json)
- Ensure all InitializeVariable actions have single variable definitions
- Check that no filter expressions with lambda syntax are used

## Security Considerations

⚠️ **Important:** This simplified approach uses hardcoded values for demonstration purposes.

**For Production:**
1. Store sensitive values in Azure Key Vault
2. Use Managed Identity for authentication
3. Enable Private Endpoints for storage and Key Vault
4. Implement proper access controls and RBAC
5. Enable diagnostic logging and monitoring
6. Use Azure DevOps or GitHub Actions for CI/CD deployment

## Next Steps

1. **Implement remaining workflows:** Apply the same validation fixes to event-portal-provisioning.json, cluster-management.json, and export-clone.json
2. **Add error handling:** Enhance workflows with proper error handling and retry logic
3. **Set up monitoring:** Configure Application Insights for detailed monitoring
4. **Automate deployment:** Create CI/CD pipeline for automated deployments
5. **Secure credentials:** Move to Key Vault and Managed Identity for production

## References
- [Azure Logic Apps Documentation](https://learn.microsoft.com/en-us/azure/logic-apps/)
- [Azure Blob Storage Connector](https://learn.microsoft.com/en-us/connectors/azureblob/)
- [Solace Cloud API Documentation](https://docs.solace.com/Cloud/ght_api_overview.htm)