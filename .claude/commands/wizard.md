Run the Solace Cloud interactive wizard in the terminal.

The wizard guides through all provisioning flows without needing to remember any commands or config file structure.

Arguments (optional): $ARGUMENTS

Usage patterns:
- `/wizard`          → show the main menu (choose flow 1-4)
- `/wizard 1`        → jump straight to "Create new integration from scratch"
- `/wizard 2`        → jump straight to "Clone existing country → new country"
- `/wizard 3`        → jump straight to "Event Portal design objects only"
- `/wizard 4`        → jump straight to "Cluster / broker objects only"

Run the appropriate command based on the argument:
- If argument is empty or "menu": run `python3 solace.py wizard`
- If argument is "1" or "scratch": run `python3 solace.py wizard --flow 1`
- If argument is "2" or "clone": run `python3 solace.py wizard --flow 2`
- If argument is "3" or "ep": run `python3 solace.py wizard --flow 3`
- If argument is "4" or "cluster": run `python3 solace.py wizard --flow 4`

Before running, show the user:
```
Solace Wizard flows:
  1 — Create new integration from scratch  (service + EP + cluster)
  2 — Clone existing country → new country
  3 — Event Portal design only
  4 — Cluster / broker objects only
```

Then execute the command in the terminal so the user can interact with the prompts.
