# n8n Code node — Python (Native) — paste this whole file into the node.
#
# Target: self-hosted n8n via `npx n8n` on the same host as tbaMUD.
#
# Setup in n8n:
#   1. Add a **Code** node
#   2. Language: **Python (Native)**  (not Pyodide legacy — no raw sockets)
#   3. Mode: **Run Once for All Items**  (uses `_items`)
#      — or **Run Once for Each Item** (uses `_item`; see MODE note below)
#   4. Paste this file as the code body
#
# Start n8n (example):
#   nvm use 22
#   export N8N_USER_FOLDER="$HOME/.n8n-home"
#   npx n8n
#   # UI: http://localhost:5678
#
# Input item JSON fields (all optional except you usually want `command`):
#   command   str   game command          default: "look"
#   user      str   character name        default: "dummy"
#   password  str   character password    default: "helloworld"
#   host      str   MUD host              default: "localhost"
#     (same machine as npx n8n → "localhost" is correct)
#   port      int   MUD port              default: 4000
#   no_login  bool  skip login handshake  default: false
#   keep_ansi bool  keep ANSI codes       default: false
#
# Output item JSON:
#   command, user, host, port, response, ok, error
#
# Requires self-hosted **Native Python** task runners (stdlib socket).
# If the Python runner fails under npx n8n, use Execute Command + mud_client.py
# as a fallback. Pyodide cannot open TCP sockets.
#
# MODE note: for "Run Once for Each Item", change the bottom block from
#   results = run_all(_items)
#   return results
# to:
#   return run_one(_item)

from __future__ import annotations

import re
import select
import socket
import time
from typing import Any

# ---------------------------------------------------------------------------
# Defaults (override per item JSON or env if your runner injects env)
# ---------------------------------------------------------------------------
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4000
DEFAULT_USER = "dummy"
DEFAULT_PASS = "helloworld"

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x18|\x1b.")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def normalize(text: str) -> str:
    text = strip_ansi(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def recv_until(
    sock: socket.socket,
    *,
    idle: float = 0.4,
    overall: float = 10.0,
    stop_on: list[str] | None = None,
) -> str:
    buf = b""
    start = time.time()
    last_data = time.time()
    markers = [s.lower() for s in (stop_on or [])]

    while time.time() - start < overall:
        remaining = overall - (time.time() - start)
        if remaining <= 0:
            break
        ready, _, _ = select.select([sock], [], [], min(0.15, remaining))
        if ready:
            chunk = sock.recv(8192)
            if not chunk:
                break
            buf += chunk
            last_data = time.time()
            if markers:
                text = strip_ansi(buf.decode("utf-8", errors="ignore")).lower()
                if any(marker in text for marker in markers):
                    time.sleep(0.12)
                    while select.select([sock], [], [], 0.05)[0]:
                        more = sock.recv(8192)
                        if not more:
                            break
                        buf += more
                    break
        elif buf and not markers and (time.time() - last_data) >= idle:
            break

    return buf.decode("utf-8", errors="ignore")


def send_line(sock: socket.socket, line: str) -> None:
    sock.sendall((line + "\n").encode("utf-8"))


def login(sock: socket.socket, user: str, password: str) -> str:
    transcript: list[str] = []

    banner = recv_until(
        sock,
        idle=1.0,
        overall=12.0,
        stop_on=["by what name", "name do you wish"],
    )
    transcript.append(banner)
    if "by what name" not in strip_ansi(banner).lower() and "name do you wish" not in strip_ansi(
        banner
    ).lower():
        raise RuntimeError(
            "TIMEOUT ERROR: Never received name prompt from MUD "
            f"(got {len(banner)} bytes). Is the server ready on the port?"
        )

    send_line(sock, user)
    after_name = recv_until(
        sock,
        idle=0.5,
        overall=8.0,
        stop_on=["password:", "no player by that name", "already playing", "wrong name"],
    )
    transcript.append(after_name)
    after_name_clean = strip_ansi(after_name).lower()

    if "no player by that name" in after_name_clean:
        raise RuntimeError(f"LOGIN ERROR: Unknown character '{user}'.")

    if "password:" not in after_name_clean:
        raise RuntimeError(
            "LOGIN ERROR: Expected password prompt after name. "
            f"Server said:\n{normalize(after_name)}"
        )

    send_line(sock, password)
    after_pass = recv_until(
        sock,
        idle=0.6,
        overall=10.0,
        stop_on=[
            "reconnecting",
            "welcome",
            "press return",
            "make your choice",
            "incorrect",
            "wrong password",
            ">",
        ],
    )
    transcript.append(after_pass)
    after_pass_clean = strip_ansi(after_pass).lower()

    if "incorrect" in after_pass_clean or "wrong password" in after_pass_clean:
        raise RuntimeError("LOGIN ERROR: Incorrect password.")

    for _ in range(6):
        text = strip_ansi("".join(transcript)).lower()
        latest = strip_ansi(transcript[-1]).lower() if transcript else ""

        if "press return" in latest or "hit return" in latest or "*** press" in latest:
            send_line(sock, "")
            more = recv_until(sock, idle=0.5, overall=6.0, stop_on=["press return", ">", "1)"])
            transcript.append(more)
            continue

        if re.search(r"\b1\)\s*enter", latest) or (
            "make your choice" in latest and "1)" in latest
        ):
            send_line(sock, "1")
            more = recv_until(sock, idle=0.5, overall=6.0, stop_on=[">", "press return"])
            transcript.append(more)
            continue

        if ">" in latest and "by what name" not in latest:
            break

        if "reconnecting" in text and ">" in latest:
            break

        break

    return "".join(transcript)


def send_command(
    command: str,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    user: str = DEFAULT_USER,
    password: str = DEFAULT_PASS,
    login_enabled: bool = True,
    keep_ansi: bool = False,
) -> str:
    try:
        with socket.create_connection((host, int(port)), timeout=10) as sock:
            sock.setblocking(False)

            login_text = ""
            if login_enabled and user:
                try:
                    login_text = login(sock, user, password)
                except RuntimeError as exc:
                    return str(exc)

            send_line(sock, command)
            response = recv_until(sock, idle=0.45, overall=6.0, stop_on=None)

            if not response.strip():
                if not command.strip():
                    body = login_text
                else:
                    return (
                        f"TIMEOUT ERROR: No response from {host}:{port} "
                        f"within timeout after command {command!r}."
                    )
            else:
                body = response

            return body if keep_ansi else normalize(body)

    except OSError as exc:
        return f"CONNECTION ERROR: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"CONNECTION ERROR: {exc}"


def _item_json(item: Any) -> dict[str, Any]:
    """Native Python uses bracket access: item['json']['field']."""
    if item is None:
        return {}
    if isinstance(item, dict):
        # already a json dict, or full n8n item
        if "json" in item and isinstance(item["json"], dict):
            return item["json"]
        return item
    # duck-type object with .json
    j = getattr(item, "json", None)
    if isinstance(j, dict):
        return j
    return {}


def _as_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off", ""):
        return False
    return default


def run_one(item: Any) -> dict[str, Any]:
    """Process a single n8n item → one output item dict with 'json' key."""
    data = _item_json(item)

    command = str(data.get("command") or data.get("cmd") or "look")
    user = str(data.get("user") or data.get("username") or DEFAULT_USER)
    password = str(data.get("password") or data.get("pass") or DEFAULT_PASS)
    host = str(data.get("host") or DEFAULT_HOST)
    port = int(data.get("port") or DEFAULT_PORT)
    login_enabled = not _as_bool(data.get("no_login"), False)
    keep_ansi = _as_bool(data.get("keep_ansi"), False)

    response = send_command(
        command,
        host=host,
        port=port,
        user=user,
        password=password,
        login_enabled=login_enabled,
        keep_ansi=keep_ansi,
    )

    err_prefixes = ("CONNECTION ERROR:", "TIMEOUT ERROR:", "LOGIN ERROR:")
    ok = not any(response.startswith(p) for p in err_prefixes)
    error = None if ok else response.split(":", 1)[0].strip() + ":"

    out = {
        "command": command,
        "user": user,
        "host": host,
        "port": port,
        "response": response,
        "ok": ok,
        "error": None if ok else response,
    }
    # Preserve other input fields for chaining
    for k, v in data.items():
        if k not in out:
            out[k] = v

    return {"json": out}


def run_all(items: Any) -> list[dict[str, Any]]:
    """Process all input items (Run Once for All Items)."""
    if items is None:
        items = [{"json": {}}]
    # Empty input → still run one default look
    try:
        length = len(items)
    except TypeError:
        length = 0
    if length == 0:
        return [run_one({"json": {}})]

    results: list[dict[str, Any]] = []
    for item in items:
        results.append(run_one(item))
    return results


# ---------------------------------------------------------------------------
# n8n entry — Native Python
# Mode: Run Once for All Items  →  _items
# Mode: Run Once for Each Item  →  swap to: return run_one(_item)
# ---------------------------------------------------------------------------
results = run_all(_items)  # noqa: F821  — provided by n8n Code node
return results  # noqa: F821
