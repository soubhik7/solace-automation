Manage Event Portal Application Domains — list, inspect, create, or delete.

Arguments: $ARGUMENTS
- (empty)                   List all domains
- `list`                    List all domains
- `get <domain-id>`         Show full domain details
- `create <name>`           Create a new domain
- `delete <domain-id>`      Delete a domain
- `schemas <domain-id>`     List schemas in a domain
- `events <domain-id>`      List events in a domain
- `apps <domain-id>`        List applications in a domain

Run the appropriate command:

```bash
# List
python3 solace.py domain list

# Get details
python3 solace.py domain get --id <domain-id>

# Create
python3 solace.py domain create --name <name> [--description <desc>]

# Delete
python3 solace.py domain delete --id <domain-id>

# List schemas in domain
python3 solace.py schema list --domain-id <domain-id>

# List events in domain
python3 solace.py event list --domain-id <domain-id>

# List apps in domain
python3 solace.py app list --domain-id <domain-id>
```

When listing domains, show a table with: id | name | description | createdTime

If the user asks for schemas/events/apps within a domain but doesn't provide an ID, list the domains first and ask which one.

Example usage:
```
/domains
/domains create MyNewDomain
/domains schemas d-abc123
/domains events d-abc123
/domains apps d-abc123
```
