# n8n MUD client (Python Code node)

Target setup: **self-hosted n8n via `npx n8n`** on the same machine as tbaMUD (`localhost:4000`).

## Files

| File | Purpose |
|------|---------|
| **`mud_client_n8n.py`** | Paste into a Code node (self-contained) |
| **`mud_client.py`** | Original CLI bridge (shell / agents) |

## Start n8n (`npx`)

Use a supported Node (n8n 2.33.x wants **≥22.22**; 22.18 is borderline):

```bash
nvm use 22   # or nvm install 22 && nvm use 22
# optional: fix npm cache if you hit EPERM
# sudo chown -R "$(whoami)" ~/.npm

# durable data (recommended)
export N8N_USER_FOLDER="$HOME/.n8n-home"

# same machine as MUD → host stays localhost in the Code node
npx n8n
# editor: http://localhost:5678
```

### Native Python (required for this script)

`mud_client_n8n.py` needs **Python (Native)** so it can open TCP sockets to the MUD.

On pure `npx n8n` you may see:

```text
Failed to start Python task runner in internal mode.
because its virtual environment is missing from this system.
```

If Python Code nodes fail:

1. Install system **Python 3** (`python3 --version`).
2. Prefer a current n8n + enable runners per [task runners docs](https://docs.n8n.io/hosting/configuration/task-runners/).
3. For n8n 2.x, internal JS runners often work; **native Python** may need an external runners image / extra setup. If Native Python still won’t start, options are:
   - Fix/configure Python task runners (official path), or
   - Call the **CLI** from an **Execute Command** node:  
     `python3 /path/to/04_n8n/mud_client.py --user dummy --password helloworld "look"`  
     (works without the Code-node Python runner).

**Pyodide (legacy Python)** cannot use raw sockets — do not use it for this client.

## Code node setup

1. **Code** node → Language: **Python (Native)**
2. Mode: **Run Once for All Items**
3. Paste entire `mud_client_n8n.py`

### Per-item mode

Replace the bottom of the paste with:

```python
return run_one(_item)
```

## Input / output

**Input item JSON** (Set node or previous step):

```json
{
  "command": "look",
  "user": "dummy",
  "password": "helloworld",
  "host": "localhost",
  "port": 4000
}
```

| Field | Default | Notes |
|-------|---------|--------|
| `command` | `look` | also `cmd` |
| `user` | `dummy` | |
| `password` | `helloworld` | |
| `host` | `localhost` | same machine as `npx n8n` + MUD |
| `port` | `4000` | |
| `no_login` | `false` | |
| `keep_ansi` | `false` | |

**Output:**

```json
{
  "command": "look",
  "user": "dummy",
  "host": "localhost",
  "port": 4000,
  "response": "The Entrance Hall…",
  "ok": true,
  "error": null
}
```

Failures: `ok: false` and `error`/`response` start with  
`CONNECTION ERROR:` | `TIMEOUT ERROR:` | `LOGIN ERROR:`.

## Minimal workflow

```
Manual Trigger → Set (command/user/password) → Code (mud_client_n8n) → …
```

## Same-machine networking

With `npx n8n` and tbaMUD both on the host:

- Code node `"host": "localhost"` / `"port": 4000` is correct.
- No Docker host aliases needed.

## CLI fallback (always works)

```bash
python3 mud_client.py --user dummy --password helloworld "look"
```

Or from n8n **Execute Command** if the Python Code runner is unavailable.
