# Azure Logic Apps Deployment Script for Solace Automation
# This script deploys all Logic App workflows, connections, and supporting resources

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$Location,
    
    [Parameter(Mandatory=$true)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev"
)

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Solace Automation - Azure Logic Apps Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set Azure subscription context
Write-Host "Setting Azure subscription context..." -ForegroundColor Yellow
az account set --subscription $SubscriptionId

# Create resource group if it doesn't exist
Write-Host "Ensuring resource group exists..." -ForegroundColor Yellow
az group create --name $ResourceGroupName --location $Location

# Deploy Storage Account
Write-Host ""
Write-Host "Deploying Storage Account..." -ForegroundColor Yellow
$storageAccountName = "solaceconfigs$Environment"
az storage account create `
    --name $storageAccountName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2

# Create blob container
Write-Host "Creating blob container..." -ForegroundColor Yellow
az storage container create `
    --name "solace-configs" `
    --account-name $storageAccountName `
    --auth-mode login

# Deploy Key Vault
Write-Host ""
Write-Host "Deploying Key Vault..." -ForegroundColor Yellow
$keyVaultName = "solace-kv-$Environment"
az keyvault create `
    --name $keyVaultName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --enable-rbac-authorization false

# Deploy Application Insights
Write-Host ""
Write-Host "Deploying Application Insights..." -ForegroundColor Yellow
$appInsightsName = "solace-insights-$Environment"
az monitor app-insights component create `
    --app $appInsightsName `
    --location $Location `
    --resource-group $ResourceGroupName `
    --application-type web

# Deploy API Connections
Write-Host ""
Write-Host "Deploying API Connections..." -ForegroundColor Yellow
az deployment group create `
    --resource-group $ResourceGroupName `
    --template-file "../connections/connections.json" `
    --parameters location=$Location `
                 storageAccountName=$storageAccountName `
                 keyVaultName=$keyVaultName

# Get connection IDs
$blobConnectionId = az deployment group show `
    --resource-group $ResourceGroupName `
    --name "connections" `
    --query "properties.outputs.blobConnectionId.value" `
    --output tsv

$keyVaultConnectionId = az deployment group show `
    --resource-group $ResourceGroupName `
    --name "connections" `
    --query "properties.outputs.keyVaultConnectionId.value" `
    --output tsv

# Deploy Logic App (Standard)
Write-Host ""
Write-Host "Deploying Logic App (Standard)..." -ForegroundColor Yellow
$logicAppName = "solace-automation-$Environment"
$appServicePlanName = "solace-asp-$Environment"

# Create App Service Plan
az appservice plan create `
    --name $appServicePlanName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --sku WS1 `
    --is-linux

# Create Logic App
az logicapp create `
    --resource-group $ResourceGroupName `
    --name $logicAppName `
    --storage-account $storageAccountName `
    --plan $appServicePlanName

# Configure Logic App settings
Write-Host "Configuring Logic App settings..." -ForegroundColor Yellow
az logicapp config appsettings set `
    --name $logicAppName `
    --resource-group $ResourceGroupName `
    --settings `
        "APPINSIGHTS_INSTRUMENTATIONKEY=$(az monitor app-insights component show --app $appInsightsName --resource-group $ResourceGroupName --query instrumentationKey -o tsv)" `
        "WORKFLOWS_SUBSCRIPTION_ID=$SubscriptionId" `
        "WORKFLOWS_RESOURCE_GROUP_NAME=$ResourceGroupName" `
        "WORKFLOWS_LOCATION_NAME=$Location"

# Deploy workflows
Write-Host ""
Write-Host "Deploying workflows..." -ForegroundColor Yellow

$workflows = @(
    "main-orchestrator",
    "service-provisioning",
    "event-portal-provisioning",
    "cluster-management",
    "export-clone"
)

foreach ($workflow in $workflows) {
    Write-Host "  - Deploying $workflow..." -ForegroundColor Gray
    
    # Read workflow definition
    $workflowPath = "../workflows/$workflow.json"
    $workflowContent = Get-Content $workflowPath -Raw | ConvertFrom-Json
    
    # Update connection references
    if ($workflowContent.definition.parameters.'$connections') {
        $workflowContent.definition.parameters.'$connections'.defaultValue = @{
            azureblob = @{
                connectionId = $blobConnectionId
                connectionName = "azureblob-connection"
                id = "/subscriptions/$SubscriptionId/providers/Microsoft.Web/locations/$Location/managedApis/azureblob"
            }
            keyvault = @{
                connectionId = $keyVaultConnectionId
                connectionName = "keyvault-connection"
                id = "/subscriptions/$SubscriptionId/providers/Microsoft.Web/locations/$Location/managedApis/keyvault"
            }
        }
    }
    
    # Save updated workflow
    $workflowContent | ConvertTo-Json -Depth 100 | Set-Content $workflowPath
    
    # Deploy workflow using Azure CLI
    az logicapp workflow create `
        --resource-group $ResourceGroupName `
        --name $logicAppName `
        --workflow-name $workflow `
        --definition $workflowPath
}

# Set up Key Vault secrets
Write-Host ""
Write-Host "Setting up Key Vault secrets..." -ForegroundColor Yellow
Write-Host "  Please add the following secrets to Key Vault manually:" -ForegroundColor Yellow
Write-Host "    - solace-api-token-dev" -ForegroundColor Gray
Write-Host "    - solace-api-token-test" -ForegroundColor Gray
Write-Host "    - solace-api-token-prod" -ForegroundColor Gray

# Grant Logic App access to Key Vault
Write-Host ""
Write-Host "Granting Logic App access to Key Vault..." -ForegroundColor Yellow
$logicAppPrincipalId = az logicapp show `
    --name $logicAppName `
    --resource-group $ResourceGroupName `
    --query identity.principalId `
    --output tsv

az keyvault set-policy `
    --name $keyVaultName `
    --object-id $logicAppPrincipalId `
    --secret-permissions get list

# Output deployment information
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Cyan
Write-Host "Logic App Name: $logicAppName" -ForegroundColor Cyan
Write-Host "Storage Account: $storageAccountName" -ForegroundColor Cyan
Write-Host "Key Vault: $keyVaultName" -ForegroundColor Cyan
Write-Host "Application Insights: $appInsightsName" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Add Solace API tokens to Key Vault" -ForegroundColor Gray
Write-Host "2. Upload configuration files to blob storage (container: solace-configs)" -ForegroundColor Gray
Write-Host "3. Test workflows using the Azure Portal or REST API" -ForegroundColor Gray
Write-Host ""
Write-Host "Main Orchestrator Endpoint:" -ForegroundColor Yellow
Write-Host "  https://$logicAppName.azurewebsites.net/api/main-orchestrator/triggers/manual/invoke" -ForegroundColor Gray
Write-Host ""

# Made with Bob
