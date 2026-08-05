---
name: play-mud
description: Play a MUD (Multi-User Dungeon) text game over a TCP/telnet connection. Use this skill whenever the user wants to play, explore, or interact with a MUD — especially tbaMUD / CircleMUD variants. Triggers on requests like "play the MUD", "log into the mud", "move north", "attack the goblin", "check my score", "look around", "what's in my inventory", "send a tell to X", or any in-character MUD command. Also use when the user wants to inspect/manage the MUD connection itself (check if connected, reconnect, read pending output). Persists a single long-lived session across many commands.
---

# MUD Player

Play a MUD running at `localhost:4000` (tbaMUD / CircleMUD). One persistent connection is kept open for the whole conversation. Every command goes through the `scripts/mud_client.py` helper — never open a raw socket yourself.

## Connection

- Host: `localhost`, port `4000`, TCP (telnet-line)
- Login: `dummy` / `helloworld`
- Protocol: tbaMUD uses IAC negotiation + ANSI color. The helper strips both automatically.

## How to act

1. **Always go through the helper.** Call `python3 scripts/mud_client.py <verb> [args]`. The verbs are listed in `scripts/USAGE.md` (read it on first use). The helper maintains a single socket and login state across calls.
2. **First action of every turn that needs output: read what's pending.** If the user has just connected and you haven't seen the MOTD / room, call `read` until the prompt appears, then summarize. If the user asks you to do something in-game, first `read` to catch any prompt the previous action left behind, then `send` the new command.
3. **Stay in character.** Respond as the player character. The MUD output is the game's narration — quote/paraphrase it, don't editorialize as Claude.
4. **Stay safe in combat.** Don't blindly `kill` everything. `look` first, `consider` the foe, check your own HP with `score` before re-engaging. Flee (`flee`) if HP is low. Never drop wielded gear without a reason.
5. **Don't spam commands.** tbaMUD throttles input. Wait for the prompt (the helper shows the last line ending in `> ` or `]`) before sending the next command. If you send two commands too fast, the second is silently dropped.
6. **Remember persistent state.** The game remembers rooms, HP, position, affects between turns. Don't restate stats the user already saw unless they changed.

## Command categories

| Want to... | Commands |
|---|---|
| See where you are / what's around | `look`, `examine <thing>`, `glance` |
| Move | `north`/`south`/`east`/`west`/`up`/`down` (or `n`/`s`/`e`/`w`/`u`/`d`), `enter`/`leave`, `follow <name>` |
| Survey | `score`, `hp`, `affects`, `inventory` (or `inv`), `equipment` (or `eq`), `time`, `weather` |
| Combat | `kill <target>`, `flee`, `consider <target>`, `wield <weapon>`, `wear <armor>`, `remove <armor>` |
| Items | `get <item>`, `drop <item>`, `put <item> <container>`, `drink <fountain>`, `eat <food>`, `use <item>` |
| Meta | `who`, `help <topic>`, `save`, `quit` |

`tbaMUD` is case-insensitive and accepts abbreviations (`inv`, `eq`, `l`, `n`, `sc`).

## Reading output

The MUD sends **lots** of text plus color codes. The helper strips ANSI and IAC and prints a clean transcript. Some patterns to look for:

- A line ending in `> ` is the input prompt — safe to send the next command.
- `[HP:...] [MV:...]>` is the combat prompt — current HP and movement (stamina).
- `You are hit!` / `You die.` / `You are dead!` mean combat is happening — react, don't send more movement.
- `You cannot do that!` / `Huh?!` = bad command. Re-read what you sent and try again.

## Connection trouble

If the helper errors with `Not connected`, the socket died. Run `python3 scripts/mud_client.py reconnect` and then `read` to catch the MOTD. If reconnect fails three times in a row, surface the error to the user instead of looping.

## Anti-patterns

- Don't `Bash` with `nc` or `telnet` directly — bypasses the persistent session and the color/IAC stripping.
- Don't try to read the socket character-by-character from the agent — the helper does this for you.
- Don't issue 5 movement commands in a row without `read`ing between them. You'll miss the room description (and any mobs that spawned).
- Don't `quit` unless the user says they're done — the session is theirs.
