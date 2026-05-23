Show the full status of the active Solace service — all cluster objects and Event Portal objects in one view.

Arguments: $ARGUMENTS
- `--service-id <id>`   Check a specific service (uses active context if omitted)
- `--ep`                Show Event Portal objects only
- `--cluster`           Show cluster/broker objects only

Run the relevant commands and present a unified status report:

**Cluster objects** (SEMP v2):
```bash
python3 solace.py cluster status
```

**Event Portal domains**:
```bash
python3 solace.py domain list
```

**Active context**:
```bash
python3 solace.py context show
```

Format the output as a clean status report:

```
═══════════════════════════════════════════
  Solace Service Status
═══════════════════════════════════════════

  Context
  ───────────────────────────────────────
  Service ID : <id>
  VPN        : <vpn>
  Token      : set ✅

  Event Portal
  ───────────────────────────────────────
  Domains    : <list of domain names>
  Schemas    : <count>
  Events     : <count>
  Apps       : <count>

  Cluster (VPN: <vpn>)
  ───────────────────────────────────────
  Client Profiles : <names>
  ACL Profiles    : <names>
  Client Usernames: <names>
  Queues          : <names + subscription counts>
  RDPs            : <names>

═══════════════════════════════════════════
```

If no active service is set, show:
```
❌ No active service. Run: python3 solace.py service use <service-id>
   Or use /services to list available services.
```
