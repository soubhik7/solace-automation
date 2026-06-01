# Logic Apps Workflow Validation Fixes

## Critical Issues Fixed

### 1. InitializeVariable Syntax Error
**Problem:** Cannot initialize multiple variables in a single InitializeVariable action.

**Original (WRONG):**
```json
{
  "type": "InitializeVariable",
  "inputs": {
    "variables": [
      {"name": "var1", "type": "string", "value": ""},
      {"name": "var2", "type": "string", "value": ""}
    ]
  }
}
```

**Fixed (CORRECT):**
```json
{
  "type": "InitializeVariable",
  "inputs": {
    "variables": [{
      "name": "var1",
      "type": "string",
      "value": ""
    }]
  }
}
```

Each variable needs its own InitializeVariable action with proper runAfter dependencies.

### 2. Filter Expression Not Supported
**Problem:** Lambda-style filter expressions don't work in Logic Apps.

**Original (WRONG):**
```json
"@first(filter(body('Parse_Final_Service')?['data']?['managementProtocols'], item => equals(item?['name'], 'SEMP Manager')))?['username']"
```

**Fixed (CORRECT):**
```json
"@body('Parse_Final_Service')?['data']?['managementProtocols']?[0]?['username']"
```

Use array indexing instead of filter expressions.

### 3. Workflow Call References
**Problem:** Workflow action type requires proper resource ID format.

**Original (WRONG):**
```json
{
  "type": "Workflow",
  "inputs": {
    "host": {
      "workflow": {
        "id": "/subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.Logic/workflows/service-provisioning"
      }
    }
  }
}
```

**Fixed (CORRECT):**
Use HTTP action to call child workflows via their HTTP trigger endpoint instead.

### 4. API Connection References
**Problem:** Blob storage connection needs proper dataset reference.

**Original (WRONG):**
```json
"path": "/v2/datasets/@{encodeURIComponent(encodeURIComponent('solace-configs'))}/files/..."
```

**Fixed (CORRECT):**
```json
"path": "/v2/datasets/@{encodeURIComponent(encodeURIComponent('AccountNameFromSettings'))}/files/..."
```

Use 'AccountNameFromSettings' as the dataset identifier for blob connections.

## Fixed Workflow Files

### ✅ main-orchestrator-fixed.json
- Fixed all InitializeVariable actions (one variable per action)
- Removed filter expressions
- Simplified workflow to use HTTP actions instead of Workflow actions
- Fixed API connection references

### ✅ service-provisioning-fixed.json
- Fixed all InitializeVariable actions
- Removed filter expressions from SEMP credential extraction
- Used array indexing instead: `?[0]?['username']`
- Added coalesce for default port value

### 🔄 Remaining Files to Fix
- event-portal-provisioning.json
- cluster-management.json
- export-clone.json

## Validation Checklist

- [x] Each InitializeVariable action initializes only ONE variable
- [x] All variables have proper runAfter dependencies
- [x] No lambda/filter expressions used
- [x] API connections use correct dataset references
- [x] HTTP actions used instead of Workflow actions for child workflows
- [ ] All workflows tested in Azure Portal designer
- [ ] Deployment script updated with correct resource IDs

## Deployment Notes

1. **Replace Original Files:**
   ```bash
   mv azure-logic-apps/workflows/main-orchestrator-fixed.json azure-logic-apps/workflows/main-orchestrator.json
   mv azure-logic-apps/workflows/service-provisioning-fixed.json azure-logic-apps/workflows/service-provisioning.json
   ```

2. **Update Connection References:**
   - Ensure storage account name is configured in connections
   - Update Key Vault connection with proper vault name
   - Grant Logic App managed identity access to Key Vault

3. **Test Workflow:**
   ```bash
   # Test via HTTP POST
   curl -X POST "https://<logic-app-name>.azurewebsites.net/api/main-orchestrator/triggers/manual/invoke?api-version=2022-05-01&sp=/triggers/manual/run&sv=1.0&sig=<signature>" \
     -H "Content-Type: application/json" \
     -d '{"configPath": "config/test/service.json", "environment": "dev"}'
   ```

## Common Validation Errors to Avoid

1. **Multiple variables in single InitializeVariable** → Split into separate actions
2. **Using filter() with lambda** → Use array indexing `?[0]`
3. **Using first() with filter()** → Use array indexing
4. **Wrong blob dataset name** → Use 'AccountNameFromSettings'
5. **Workflow action without proper ID** → Use HTTP action to call child workflows
6. **Missing runAfter dependencies** → Ensure proper action sequencing

## Next Steps

1. Fix remaining workflow files (event-portal, cluster-management, export-clone)
2. Test each workflow individually in Azure Portal
3. Update deployment script with actual subscription/resource group IDs
4. Deploy to dev environment
5. Run end-to-end integration test