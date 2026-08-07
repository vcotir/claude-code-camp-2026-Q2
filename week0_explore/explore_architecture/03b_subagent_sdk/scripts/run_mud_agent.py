#!/usr/bin/env python3
"""
Interactive MUD orchestrator using the Claude Agent SDK.

Defines character-specific play-mud subagents programmatically via
AgentDefinition (no filesystem load from .claude/agents/). The orchestrator
can spawn multiple subagents in parallel (e.g. dummy + Smarty).

Compatible with Claude Code's agent runtime.

Usage:
  python scripts/run_mud_agent.py
  python scripts/run_mud_agent.py --goal "Launch dummy and Smarty in parallel; each looks and scores"
  # type goals at the prompt; /quit or Ctrl-D to exit
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Unbuffered stdout/stderr so piped/background runs show progress immediately.
os.environ.setdefault("PYTHONUNBUFFERED", "1")
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

# Project root: parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ollama Anthropic-compatible endpoint (https://ollama.com/blog/claude)
DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Prefer a tool-capable local model; override with --model / MUD_AGENT_MODEL
DEFAULT_OLLAMA_MODEL = os.environ.get("MUD_AGENT_MODEL", "qwen3.6-balanced")

# ---------------------------------------------------------------------------
# Shared play-mud instructions (character-specific binding appended per agent)
# ---------------------------------------------------------------------------

PLAY_MUD_BASE_PROMPT = """\
# Play Mud Agent

You are a player-journey agent for CircleMUD (tbaMUD). You act in the live game
through a local CLI bridge and keep markdown state files up to date.

## Project layout (dependencies)

All paths are **relative to the project / workspace root** (the directory that
contains `scripts/` and `data/`). Do **not** look under `.claude/` for the
client or state files — those moved out of the old skill package.

| Path | Role |
|------|------|
| `scripts/mud_client.py` | TCP bridge: connect → login → one command → print response → exit |
| `data/<character>/player.md` | Character status, inventory, credentials notes, move budget |
| `data/<character>/world.md` | Location, exits, NPCs, maps, environmental notes |

```bash
python3 scripts/mud_client.py --user <user> --password <password> "look"
```

## Interaction interface

To talk to the MUD, **always** use `scripts/mud_client.py`. Never open raw
sockets, `nc`, or `telnet` yourself.

- Each invocation opens a connection, logs in, sends **one** game command,
  prints the response, and exits.
- ANSI color codes are stripped so output is agent-readable.
- On `TIMEOUT ERROR`, `CONNECTION ERROR`, or `LOGIN ERROR`, report the exact
  message and stop looping on the same failure.
- Quote multi-word commands. Prefer short atomic actions (`look`, `n`,
  `get torch`, `open door`).
- Prefer **one** client session at a time for *this* character — concurrent
  logins of the same name thrash the character (“body usurped”). Other
  characters may run in parallel in other subagents.

### Class → guild routes (from Temple Square / Market Square)

- **Warrior:** Market Square → **e** (Main Street, general) → **e** (Main Street, weapons) → **s** Swordsmen guild
- **Mage:** Market Square → **w** (Main Street, bakery side) → **w** (Main Street, magic shop) → **s** Mages' guild
- **Cleric:** Temple Square → **w** Clerics' Guild
- **Thief:** Market/Common area → Dark Alley → **s** Thieves' Guild

## Persistence & state management

**Before** an action, read your character-specific state files.
**After** each successful `mud_client.py` response, update those files
immediately (location, exits, HP, inventory, goals, map notes).

## Gameplay loop

1. **Receive** — run mud_client with your character flags and read output.
2. **State update** — write changes into your player.md and world.md.
3. **Decide** — pick the next atomic move toward the goal.
4. **Execute** — run the next command through the client.
5. **Loop** until the goal is achieved or the move budget is exhausted.

## Move budget

- **Hard cap: 100 moves per run** (directional travel only counts).
- Non-travel commands (`look`, `list`, `score`, `where`, etc.) do **not** count
  unless the user says otherwise.
- Track `moves_used` / `moves_remaining` in your player.md.
- On reconnect, resume from state files without replaying the whole path unless
  the live room disagrees with the files.
"""

# Character roster for parallel multi-agent play
CHARACTERS: dict[str, dict[str, str]] = {
    "dummy": {
        "user": "dummy",
        "password": "helloworld",
        "class": "Warrior",
        "guild": "Entrance Hall To The Guild Of Swordsmen",
        "state_dir": "data/dummy",
    },
    "smarty": {
        "user": "Smarty",
        "password": "helloworld",
        "class": "Magic User",
        "guild": "Entrance To The Mages' Guild",
        "state_dir": "data/smarty",
    },
}


def make_character_agent(key: str) -> AgentDefinition:
    """Build a locked-down AgentDefinition for one MUD character."""
    info = CHARACTERS[key]
    user = info["user"]
    password = info["password"]
    state = info["state_dir"]
    agent_name = f"play-mud-{key}"

    description = (
        f"Player journey agent for CircleMUD character **{user}** "
        f"({info['class']}). Use for play/explore/fight/shop/map/quest as "
        f"{user} only. State in `{state}/`. Credentials: "
        f"--user {user} --password {password}."
    )

    prompt = (
        PLAY_MUD_BASE_PROMPT
        + f"""

## Bound character (locked)

You control **only** this character. Do not log in as anyone else.

| Field | Value |
|-------|-------|
| Agent name | `{agent_name}` |
| Character | `{user}` |
| Password | `{password}` |
| Class | {info['class']} |
| Guild target | {info['guild']} |
| State dir | `{state}/` |
| player.md | `{state}/player.md` |
| world.md | `{state}/world.md` |

Always pass credentials explicitly:

```bash
python3 scripts/mud_client.py --user {user} --password {password} "<cmd>"
```

Only read/write `{state}/player.md` and `{state}/world.md` for persistence.

## Persona (critical)

You **are** the MUD character **{user}**, not a general-purpose chatbot.
Questions like "are you hungry?", "what is your HP?", "where are you?" refer to
**the in-game character**, never to you-as-an-AI.

To answer character-state questions:
1. Read `{state}/player.md` (and `{state}/world.md` if needed).
2. If state is stale or missing the fact, run mud_client (`score`, `look`,
   `affects`, etc.) with your credentials and update the state files.
3. Answer with the **character** fact (e.g. "dummy is hungry" / "not hungry").
   Never say "I am an AI so I don't feel hunger."
"""
    )

    return AgentDefinition(
        description=description,
        prompt=prompt,
        tools=["Bash", "Read", "Write", "Edit", "Grep", "Glob"],
        model="inherit",
        permissionMode="acceptEdits",
        # Foreground: parent waits for the result. Background agents return
        # "async launched" and the orchestrator ends the turn too early.
        background=False,
    )


ORCHESTRATOR_PROMPT = """\
You are a thin coordinator for CircleMUD (tbaMUD) play sessions.

You have two specialized player subagents (Agent tool):
- `play-mud-dummy` — warrior **dummy** (state: data/dummy/)
- `play-mud-smarty` — mage **Smarty** (state: data/smarty/)

Rules:
1. For any in-game play/explore/fight/shop/map/quest request, delegate via the
   Agent tool. Do not open raw sockets, nc, or telnet yourself.
2. **One character → one subagent.** Never have two agents log in as the same
   character (body usurped).
3. **Parallelism:** When the user asks about both characters, multi-party goals,
   or explicitly wants parallel work, spawn **both** `play-mud-dummy` and
   `play-mud-smarty` in the **same turn** (two Agent tool calls together) so
   they run concurrently. Different characters may safely run in parallel.
4. If only one character is mentioned, spawn only that agent.
5. **Foreground only:** Always set `run_in_background: false` on Agent tool
   calls (or omit background). Do **not** launch async/background agents.
   Wait until each subagent returns its final result before answering the user.
6. After subagents finish, summarize **their actual results** for the user.
   Never say you will "let them know later" — you already have the results.
7. Keep your own tool use minimal — delegate gameplay.
"""

EXIT_COMMANDS = frozenset({"/quit", "/exit", "quit", "exit", ":q"})

DEFAULT_PARALLEL_GOAL = (
    "Launch play-mud-dummy and play-mud-smarty in parallel in the same turn. "
    "Each agent: (1) read its state files, (2) run look and score via "
    "mud_client.py with its own credentials, (3) update its state files, "
    "(4) report location/HP/goal status. Do not move between rooms. "
    "Then summarize both results for me."
)


def ollama_env(base_url: str) -> dict[str, str]:
    """Env that routes Claude Code CLI / Agent SDK through Ollama's Anthropic API."""
    return {
        "ANTHROPIC_AUTH_TOKEN": "ollama",
        "ANTHROPIC_API_KEY": "ollama",
        "ANTHROPIC_BASE_URL": base_url.rstrip("/"),
    }


def apply_ollama_process_env(base_url: str) -> None:
    """Set process env so the spawned Claude CLI authenticates against Ollama."""
    for key, value in ollama_env(base_url).items():
        os.environ[key] = value


def build_options(*, model: str, ollama_base_url: str | None) -> ClaudeAgentOptions:
    """Claude Code–compatible options: programmatic subagents, no filesystem agents."""
    env: dict[str, str] = {}
    if ollama_base_url:
        env.update(ollama_env(ollama_base_url))

    return ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=ORCHESTRATOR_PROMPT,
        model=model,
        allowed_tools=["Bash", "Read", "Write", "Edit", "Grep", "Glob", "Agent"],
        permission_mode="acceptEdits",
        # Do not set setting_sources — avoids loading .claude/agents from disk.
        env=env,
        agents={
            "play-mud-dummy": make_character_agent("dummy"),
            "play-mud-smarty": make_character_agent("smarty"),
        },
    )


def print_banner(*, model: str, backend: str) -> None:
    print("MUD orchestrator (Claude Agent SDK + parallel AgentDefinitions)")
    print(f"cwd: {PROJECT_ROOT}")
    print(f"backend: {backend}")
    print(f"model: {model}")
    print("Subagents: play-mud-dummy | play-mud-smarty  (can run in parallel)")
    print("Type a goal and press Enter. Session context is kept across turns.")
    print("Commands: /quit  /exit  (also Ctrl-D / Ctrl-C)")
    print()


def _agent_name_from_tool_input(inp: dict | None) -> str:
    """Resolve subagent name from Agent/Task tool input (field names vary by CLI)."""
    if not inp:
        return "?"
    for key in (
        "subagent_type",
        "subagentType",
        "agent",
        "agent_type",
        "agentType",
        "name",
        "type",
    ):
        val = inp.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Sometimes only description/prompt are filled; sniff known agent names.
    blob = " ".join(str(inp.get(k, "")) for k in ("description", "prompt", "name"))
    for name in ("play-mud-dummy", "play-mud-smarty", "play-mud"):
        if name in blob:
            return name
    return "?"


def _format_tool_result_content(content: object, *, limit: int = 1200) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or item))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    else:
        text = str(content)
    text = text.strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _print_content_blocks(
    content: object,
    *,
    who: str,
    tool_use_ids: dict[str, str],
    verbose: bool,
) -> None:
    """Print text / tool calls / tool results from assistant or user content."""
    if content is None:
        return
    if isinstance(content, str):
        if content.strip():
            print(f"{who}{content}", flush=True)
        return

    if not isinstance(content, list):
        return

    for block in content:
        if isinstance(block, TextBlock) and block.text and block.text.strip():
            print(f"{who}{block.text}", flush=True)
        elif isinstance(block, ThinkingBlock) and verbose and block.thinking:
            snippet = block.thinking.strip().replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:199] + "…"
            print(f"{who}[thinking] {snippet}", file=sys.stderr, flush=True)
        elif isinstance(block, ToolUseBlock):
            name = block.name
            inp = block.input or {}
            if name in ("Agent", "Task"):
                sub = _agent_name_from_tool_input(inp)
                tool_use_ids[block.id] = sub
                desc = (inp.get("description") or inp.get("prompt") or "")[:120]
                print(f"[delegated → {sub}] id={block.id}", file=sys.stderr, flush=True)
                if desc:
                    print(f"  task: {desc}", file=sys.stderr, flush=True)
                if verbose and sub == "?":
                    print(f"  raw input keys: {list(inp.keys())}", file=sys.stderr, flush=True)
                    print(f"  raw input: {inp!r}"[:500], file=sys.stderr, flush=True)
            else:
                # Compact tool call line (subagent tools show under that agent)
                summary = ""
                if name == "Bash":
                    summary = str(inp.get("command") or "")[:100]
                elif name in ("Read", "Write", "Edit"):
                    summary = str(inp.get("file_path") or inp.get("path") or "")[:100]
                elif name == "Grep":
                    summary = str(inp.get("pattern") or "")[:80]
                print(f"{who}[tool → {name}] {summary}".rstrip(), file=sys.stderr, flush=True)
        elif isinstance(block, ToolResultBlock):
            body = _format_tool_result_content(block.content)
            if body and _is_async_launch_noise(body) and not verbose:
                # One short line instead of the long agentId boilerplate
                print(f"{who}[tool result] async agent launched (background)", file=sys.stderr, flush=True)
                continue
            label = "error" if block.is_error else "result"
            if body:
                print(f"{who}[tool {label}] {body}", file=sys.stderr, flush=True)


# SystemMessage subtypes that are pure noise (even with --verbose we skip most)
_SYSTEM_NOISE = frozenset(
    {
        "thinking_tokens",
        "init",
        "status",
        "compact_boundary",
    }
)


def _handle_system_message(
    message: SystemMessage,
    *,
    tool_use_ids: dict[str, str],
    task_labels: dict[str, str],
    verbose: bool,
) -> None:
    """Surface useful system events; hide token spam."""
    subtype = message.subtype or ""
    data = message.data or {}

    if subtype in _SYSTEM_NOISE:
        return

    if subtype in ("task_started", "task_notification", "task_progress", "task_updated"):
        task_id = str(data.get("task_id") or "")
        tool_use_id = data.get("tool_use_id")
        subagent = data.get("subagent_type") or data.get("description")
        if tool_use_id and tool_use_id in tool_use_ids:
            subagent = tool_use_ids[tool_use_id]
        if task_id and subagent:
            task_labels[task_id] = str(subagent)
        label = task_labels.get(task_id) or subagent or task_id[:8] or "?"

        if subtype == "task_started":
            print(f"[task started] {label}", file=sys.stderr, flush=True)
            return
        if subtype == "task_progress":
            tool = data.get("last_tool_name") or data.get("description") or ""
            print(f"[{label}] progress {tool}".rstrip(), file=sys.stderr, flush=True)
            return
        if subtype == "task_notification":
            status = data.get("status") or "done"
            summary = data.get("summary") or ""
            print(f"[task {status}] {label}: {summary}", file=sys.stderr, flush=True)
            if summary:
                print(f"[{label}] {summary}", flush=True)
            return
        if subtype == "task_updated" and verbose:
            print(f"[task updated] {label} {data.get('patch') or data.get('status')}", file=sys.stderr, flush=True)
            return
        return

    if subtype == "background_tasks_changed":
        if verbose:
            tasks = data.get("tasks") or []
            print(f"[background tasks] n={len(tasks) if hasattr(tasks, '__len__') else tasks}", file=sys.stderr, flush=True)
        return

    if verbose:
        # Avoid dumping huge data blobs; keys only for unknown subtypes
        print(f"[system:{subtype}] {list(data.keys())}", file=sys.stderr, flush=True)


def _is_async_launch_noise(text: str) -> bool:
    t = text.lower()
    return "async agent launched" in t or "working in the background" in t


async def handle_turn(
    client: ClaudeSDKClient,
    user_text: str,
    *,
    verbose: bool = False,
) -> None:
    """Stream one query and print orchestrator + subagent activity clearly."""
    # Map Agent tool_use_id → subagent name for labeling nested messages
    tool_use_ids: dict[str, str] = {}
    # Map task_id → label for Task* messages
    task_labels: dict[str, str] = {}

    print("[turn] sending query…", file=sys.stderr, flush=True)
    await client.query(user_text)
    print("[turn] waiting for response stream…", file=sys.stderr, flush=True)

    async for message in client.receive_response():
        if isinstance(message, SystemMessage):
            _handle_system_message(
                message,
                tool_use_ids=tool_use_ids,
                task_labels=task_labels,
                verbose=verbose,
            )
            continue

        parent = getattr(message, "parent_tool_use_id", None)
        if parent and parent in tool_use_ids:
            who = f"[{tool_use_ids[parent]}] "
        elif parent:
            who = f"[subagent:{parent[:8]}] "
        else:
            who = "[orchestrator] "

        if isinstance(message, TaskStartedMessage):
            label = message.description or message.task_type or message.task_id
            if message.tool_use_id and message.tool_use_id in tool_use_ids:
                label = tool_use_ids[message.tool_use_id]
            task_labels[message.task_id] = str(label)
            print(
                f"[task started] {label} (task_id={message.task_id})",
                file=sys.stderr,
                flush=True,
            )
            continue

        if isinstance(message, TaskProgressMessage):
            label = task_labels.get(message.task_id, message.task_id[:8])
            tool = message.last_tool_name or "?"
            print(
                f"[{label}] progress: {message.description or ''} tool={tool}",
                file=sys.stderr,
                flush=True,
            )
            continue

        if isinstance(message, TaskNotificationMessage):
            label = task_labels.get(message.task_id, message.task_id[:8])
            print(
                f"[task {message.status}] {label}: {message.summary}",
                file=sys.stderr,
                flush=True,
            )
            if message.summary:
                print(f"[{label}] {message.summary}", flush=True)
            continue

        if isinstance(message, AssistantMessage):
            if message.error:
                print(f"{who}[error] {message.error}", file=sys.stderr, flush=True)
            _print_content_blocks(
                message.content,
                who=who,
                tool_use_ids=tool_use_ids,
                verbose=verbose,
            )
            continue

        if isinstance(message, UserMessage):
            # Skip verbose dump of async-launch metadata unless -v
            if message.tool_use_result and not verbose:
                status = ""
                if isinstance(message.tool_use_result, dict):
                    status = str(message.tool_use_result.get("status") or "")
                if status == "async_launched":
                    aid = message.tool_use_result.get("agentId", "?")
                    desc = message.tool_use_result.get("description", "")
                    print(
                        f"{who}[async launched] agentId={aid} {desc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    # content often repeats the long "never quote agentId" blurb
                    continue
            elif message.tool_use_result and verbose:
                print(
                    f"{who}[tool_use_result] {message.tool_use_result!r}"[:400],
                    file=sys.stderr,
                    flush=True,
                )

            # Filter async-launch blurb from content blocks
            content = message.content
            if isinstance(content, str) and _is_async_launch_noise(content) and not verbose:
                continue
            if isinstance(content, list) and not verbose:
                filtered = []
                for block in content:
                    if isinstance(block, TextBlock) and _is_async_launch_noise(block.text or ""):
                        continue
                    filtered.append(block)
                content = filtered

            _print_content_blocks(
                content,
                who=who,
                tool_use_ids=tool_use_ids,
                verbose=verbose,
            )
            continue

        if isinstance(message, ResultMessage):
            if message.result:
                print(message.result, flush=True)
            if message.subtype != "success" or message.is_error:
                reason = message.terminal_reason or message.subtype
                errs = "; ".join(message.errors or []) if message.errors else ""
                print(f"[session note: {reason}] {errs}".rstrip(), file=sys.stderr, flush=True)
            else:
                print(
                    f"[turn complete] turns={message.num_turns} cost_usd={message.total_cost_usd}",
                    file=sys.stderr,
                    flush=True,
                )
            continue

        if verbose:
            print(f"[msg] {type(message).__name__}", file=sys.stderr, flush=True)


async def repl(
    *,
    initial_goal: str | None = None,
    one_shot: bool = False,
    model: str,
    ollama_base_url: str | None,
    verbose: bool = False,
) -> int:
    backend = f"ollama ({ollama_base_url})" if ollama_base_url else "anthropic (default)"
    if ollama_base_url:
        apply_ollama_process_env(ollama_base_url)

    print_banner(model=model, backend=backend)
    options = build_options(model=model, ollama_base_url=ollama_base_url)

    try:
        async with ClaudeSDKClient(options=options) as client:
            if initial_goal:
                print(f"> {initial_goal}")
                try:
                    await handle_turn(client, initial_goal, verbose=verbose)
                except Exception as exc:  # noqa: BLE001
                    print(f"Error: {exc}", file=sys.stderr)
                print()
                if one_shot:
                    return 0

            while True:
                try:
                    line = await asyncio.to_thread(input, "> ")
                except EOFError:
                    print()
                    break

                text = line.strip()
                if not text:
                    continue
                if text.lower() in EXIT_COMMANDS:
                    break

                try:
                    await handle_turn(client, text, verbose=verbose)
                except Exception as exc:  # noqa: BLE001 - REPL boundary
                    print(f"Error: {exc}", file=sys.stderr)
                print()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Interactive MUD orchestrator with parallel play-mud subagents."
    )
    p.add_argument(
        "--goal",
        "-g",
        default=None,
        help="Initial goal to run immediately (optional).",
    )
    p.add_argument(
        "--parallel-demo",
        action="store_true",
        help="Run the default dual-character parallel look/score goal, then exit.",
    )
    p.add_argument(
        "--one-shot",
        action="store_true",
        help="With --goal or --parallel-demo, exit after the first turn.",
    )
    p.add_argument(
        "--ollama",
        action="store_true",
        default=True,
        help="Route Claude Code through Ollama Anthropic API (default: on).",
    )
    p.add_argument(
        "--no-ollama",
        action="store_true",
        help="Use default Anthropic / Claude login instead of Ollama.",
    )
    p.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_BASE_URL,
        help=f"Ollama base URL (default: {DEFAULT_OLLAMA_BASE_URL}).",
    )
    p.add_argument(
        "--model",
        "-m",
        default=DEFAULT_OLLAMA_MODEL,
        help=f"Model id for Claude Code / Ollama (default: {DEFAULT_OLLAMA_MODEL}).",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show SystemMessage spam, thinking snippets, and raw Agent tool inputs.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    initial: str | None = args.goal
    one_shot = args.one_shot
    if args.parallel_demo:
        initial = DEFAULT_PARALLEL_GOAL
        one_shot = True
    use_ollama = not args.no_ollama
    ollama_url = args.ollama_url if use_ollama else None
    try:
        return asyncio.run(
            repl(
                initial_goal=initial,
                one_shot=one_shot,
                model=args.model,
                ollama_base_url=ollama_url,
                verbose=args.verbose,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
