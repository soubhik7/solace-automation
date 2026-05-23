List all Solace Cloud messaging services in the organisation, and optionally set one as active.

Arguments: $ARGUMENTS
- (empty)               List all services in a table
- `use <service-id>`    Set a service as active and save its SEMP credentials to context
- `info <service-id>`   Show full details + SEMP credentials for a specific service
- `datacenters`         List all available datacenters and service types

Run the appropriate command:

**List all services:**
```bash
python3 solace.py service list
```
Show as a table: serviceId | name | datacenterId | serviceClassId | creationState | adminState

**Set active service:**
```bash
python3 solace.py service use <service-id>
```

**Show service info:**
```bash
python3 solace.py service info --id <service-id>
```

**List datacenters:**
```bash
python3 solace.py service datacenters
python3 solace.py service types
```

After listing services, if there is more than one, ask:
"Would you like to set one of these as your active service? (Enter service ID or press Enter to skip)"

If the user provides a service ID, run `python3 solace.py service use <id>` and confirm.

Example usage:
```
/services
/services use 5yv0da6tr85
/services info 5yv0da6tr85
/services datacenters
```
