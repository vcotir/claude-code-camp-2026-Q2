# 00 · Configuration (Python)

We want to able to manage all configurations from an external file eg. `~/.boukensha/settings.yaml`
We want a dedicated class to handle configuration. eg. `boukensha.config.Config`
Please consider that as we add configuration in each iteration we will be updating the configuration schema and class.
We can hardcode defaults but we should not hardcode configurable values.

Configuration is organised by **task** — a role in the agentic loop bound to its
own LLM. week1_baseline only drives a single `player` task (the main loop), but
a more advanced loop will assign different LLMs to different tasks. A task is
either a "single-task" or a "multi-task" — the latter being a full agent.

## Python environment (do this first)

All Python steps in this repo share **one virtualenv at the repository root**.
Create it once, then assume it is there.

From the **repository root**:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e week1_baseline/python/00_config
```

Requires Python 3.11+. Later `week1_baseline/python/01_*` … folders reuse this
same `.venv`. Launchers call `.venv/bin/python` and will fail if you skip this.

## Design Considerations

We want to use the standard library as much as possible avoiding external
packages. Python does not ship YAML or `.env` loading, so this step needs two
third-party packages listed in `pyproject.toml`: `python-dotenv` and `PyYAML`.

Settings keys are **strings only** (YAML in Python yields string keys). Call
`config.tasks("player")` and `config.dig("mud", "host")` — not symbols.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `Config` class |
| `boukensha/tasks/base.py` | abstract `Base` (provider/model + prompt resolution) |
| `boukensha/tasks/player.py` | concrete `Player` (the main loop) |
| `boukensha/__init__.py` | top-level package |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test |

---

## Config directory resolution

The class looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — set this to point at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

Python and Ruby share the **same** repo-root `.boukensha/` (settings, `.env`,
prompt overrides).

## Config directory structure

The class expects the following:

```
.boukensha/
  .env                 # stores credentials eg. LLMs APIs (never committed to repo)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

---

## Tasks

`boukensha.tasks.base.Base` is an abstract stateless class. All behaviour is
expressed as class methods that accept a `settings` dict — no instances are
created. Concrete subclasses define `.task_name()`. For now only
`boukensha.tasks.player.Player` exists; future steps add per-turn ceilings
(`max_iterations`, `max_turn_tokens`, `max_output_tokens`,
`compaction_threshold`) — these are **not** read yet.

`Config.tasks()` returns the raw dict from `settings.yaml` under `tasks:`. Pass a
name to look up a specific task's settings dict, then pass it to the stateless
class:

```python
from boukensha.config import Config
from boukensha.tasks.player import Player

config = Config()
Player.provider(config.tasks("player"))
Player.system_prompt(
    config.tasks("player"),
    user_prompts_dir=config.user_prompts_dir(),
    default_prompts_dir=Config.PROMPTS_DIR,
)
```

## System prompt resolution

Per task, `Player.system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** — the default system prompt shipped with the library.

(We no longer use a top-level `system.override`; override is now per-task via
`prompt_override.system`.)

## Configuration Schema

The following properties so far:
- `tasks`: a map of task name → task config (provider, model, prompt_override).
- `tasks.<name>.prompt_override.system`: when `true`, the task's
  `.boukensha/prompts/<name>/system.md` overrides the default system prompt.
- `mud`: MUD connection information for the main player.

```yaml
tasks:
  player:
    provider: anthropic        # provider name (string)
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Run Example

With the repo-root `.venv` already created (see the top of this file):

```bash
./week1_baseline/bin/python/00_config
```

Ruby reference (same `.boukensha/`, same smoke-test fields):

```bash
./week1_baseline/bin/ruby/00_config
```

Expected output (values from your `.boukensha/`):

```
=== Boukensha Step 0: Configuration ===

Config dir:     /path/to/repo/.boukensha
Tasks:          player

-- player task --
Provider:       anthropic
Model:          claude-haiku-4-5
Prompt override?True
System prompt:  You are a MUD player assistant. Use the tools available to y...

MUD host:       localhost:4000
MUD user:       dummy

API key set?    True

<Config dir=/path/to/repo/.boukensha tasks=player>
```

`True`/`False` are Python's boolean spelling (Ruby prints `true`/`false`).
The `Config` line is a Python `__str__` rather than Ruby's `#<Boukensha::Config …>`.

## Considerations
These are observed but we don't want to these fixed since future steps will break.
- We have a default prompt e.g. prompts/system.md it's supposed to be scoped on a task e.g. prompts/<task>/system.md
- Settings file should accept .yml or .yaml, right now it only takes .yaml
