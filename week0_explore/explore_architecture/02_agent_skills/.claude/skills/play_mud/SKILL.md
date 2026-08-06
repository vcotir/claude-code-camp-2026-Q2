---
name: play-mud
description: Use this skill to interact with a CircleMUD (tbaMUD) server. It uses mud_client.py as the communication bridge, handles your character's persistent state via data files, and interprets the game world logic. Use this whenever you need to engage in MUD gameplay or interact with the tbaMUD world.
---

# Play Mud Skill

You are a player journey agent playing a CircleMUD (tbaMUD).

## Interaction Interface

To communicate with the MUD, **always** use the script `scripts/mud_client.py`.

```bash
python3 scripts/mud_client.py "look"
python3 scripts/mud_client.py "score"
python3 scripts/mud_client.py "get sword"
```

Defaults (override with flags or env vars):

| Setting  | Default       | Env / flag              |
|----------|---------------|-------------------------|
| Host     | `localhost`   | `MUD_HOST` / `--host`   |
| Port     | `4000`        | `MUD_PORT` / `--port`   |
| User     | `dummy`       | `MUD_USER` / `--user`   |
| Password | `helloworld`  | `MUD_PASS` / `--password` |

- The script opens a connection, logs in, sends **one** game command, prints the response, and exits.
- It strips ANSI color codes so responses are agent-readable.
- If the script returns an error (`TIMEOUT ERROR`, `CONNECTION ERROR`, `LOGIN ERROR`), tell the user exactly what happened.
- Quote multi-word commands. Prefer short atomic actions (`look`, `n`, `get torch`).

## Persistence & State Management

The game world and your character's state are persistent. Maintain them by updating:

- **Player Data**: `data/player.md` (status, inventory, attributes, credentials notes)
- **World Data**: `data/world.md` (location, NPCs, exits, environmental details)

**Before** performing an action, read both files to ground yourself in the current state.  
**After** each `mud_client.py` response, update the relevant file immediately.

## Gameplay Loop

1. **Receive world info** — from `mud_client.py` output.
2. **State update** — write changes into `data/world.md` and `data/player.md` (Track useful player info, explored locations, navigation details, current goals, and important observations)
3. **Decision** — pick the next atomic move toward the user's goal.
4. **Execute** — run `python3 scripts/mud_client.py "<command>"`.
5. **Loop** — repeat until the current goal is achieved.

## Goals & Execution

The user will give high-level quests (e.g. "Find a weapon and go to the tavern"). Break them into atomic actions, update persistent files each step, and report progress as you move through the world.

## Move Budget

- **Hard cap: 100 moves per run** (a "move" = one `mud_client.py` invocation that is a directional travel command: `n`/`s`/`e`/`w`/`u`/`d` or long forms, plus `enter`/`leave` if used to change rooms).
- Non-travel commands (`look`, `list`, `score`, `where`, etc.) do **not** count against the budget unless the user says otherwise.
- Track `moves_used` / `moves_remaining` in `data/player.md`. Stop exploration when the budget is exhausted and report what you know so far.
- On reconnect, resume from `data/player.md` + `data/world.md` without replaying the whole path unless the live room disagrees with the files.
