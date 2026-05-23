Manage queues on the active Solace broker (SEMP v2) — list, create, delete, and manage subscriptions.

Arguments: $ARGUMENTS
- (empty) or `list`                         List all queues in the active VPN
- `create <name>`                           Create a queue
- `create <name> exclusive`                 Create an exclusive queue
- `subscribe <queue-name> <topic>`          Add a topic subscription to a queue
- `unsubscribe <queue-name> <topic>`        Remove a topic subscription
- `subs <queue-name>`                       List subscriptions on a queue
- `delete <queue-name>`                     Delete a queue

Run the appropriate command:

```bash
# List all queues
python3 solace.py cluster queue-list

# Create queue
python3 solace.py cluster queue-create --name <name> [--access-type non-exclusive|exclusive]

# Add subscription
python3 solace.py cluster queue-subscribe --queue <name> --topic "<topic>"

# Remove subscription
python3 solace.py cluster queue-unsubscribe --queue <name> --topic "<topic>"

# List subscriptions
python3 solace.py cluster queue-subs-list --queue <name>

# Delete queue
python3 solace.py cluster queue-delete --name <name>
```

When listing queues, show: name | accessType | subscriptionCount

After creating a queue, ask: "Add topic subscriptions now? (e.g. acme/dev/orders/>)"
Keep prompting until the user says no or presses Enter with no input.

Example usage:
```
/queue
/queue list
/queue create acme-dev-orders-q
/queue create acme-dev-alerts-q exclusive
/queue subscribe acme-dev-orders-q acme/dev/orders/>
/queue subs acme-dev-orders-q
/queue delete acme-dev-orders-q
```
