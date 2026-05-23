Show or manage the active Solace Cloud context — API token, active service, VPN, and SEMP credentials.

The context is persisted in `.solace-context.json` (gitignored) and loaded automatically by every command.

Arguments: $ARGUMENTS
- (empty) or `show`                 Show current context
- `set-token <token>`               Save a new API Bearer token
- `use <service-id>`                Set active service (fetches + saves SEMP creds)
- `clear`                           Reset all context (token, service, SEMP creds)

Run the appropriate command:

```bash
# Show
python3 solace.py context show

# Set token
python3 solace.py context set-token --token <token>

# Set active service
python3 solace.py service use <service-id>

# Clear
python3 solace.py context clear
```

When showing context, format it clearly:

```
Active Context
──────────────────────────────────────
Token      : set ✅  (or NOT SET ❌)
Service ID : <id>   (or none)
VPN Name   : <vpn>  (or none)
SEMP URL   : <url>  (or none)
SEMP User  : <user> (or none)
──────────────────────────────────────
```

If token is not set, advise:
```
Set your token with:
  export SOLACE_API_TOKEN="eyJ..."
  python3 solace.py context set-token --token <token>
```

If service is not set, advise:
```
Set active service with:
  python3 solace.py service list      ← find your service ID
  python3 solace.py service use <id>  ← activate it
```

Example usage:
```
/context
/context set-token eyJhbGci...
/context use 5yv0da6tr85
/context clear
```
