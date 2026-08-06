#!/usr/bin/env python3
"""
CLI bridge for CircleMUD / tbaMUD.

Each invocation opens a connection, logs in (if credentials are available),
sends one game command, prints the server response, and disconnects.

Usage:
  python3 mud_client.py "look"
  python3 mud_client.py --user dummy --password helloworld "score"
  MUD_USER=dummy MUD_PASS=helloworld python3 mud_client.py "where"
"""

from __future__ import annotations

import argparse
import os
import re
import select
import socket
import sys
import time
from typing import Iterable, Optional

DEFAULT_HOST = os.environ.get("MUD_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("MUD_PORT", "4000"))
DEFAULT_USER = os.environ.get("MUD_USER", "dummy")
DEFAULT_PASS = os.environ.get("MUD_PASS", "helloworld")

# ANSI / control sequences common on tbaMUD banners
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x18|\x1b.")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def normalize(text: str) -> str:
    """Strip ANSI and normalize newlines for agent-readable output."""
    text = strip_ansi(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse long blank runs that banners produce
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def recv_until(
    sock: socket.socket,
    *,
    idle: float = 0.4,
    overall: float = 10.0,
    stop_on: Optional[Iterable[str]] = None,
) -> str:
    """
    Read from a non-blocking socket until:
      - any of the stop_on substrings appear (preferred exit when provided), or
      - no new data for `idle` seconds after some data arrived (only when
        stop_on is empty — MUD client-detect pauses can exceed idle), or
      - overall timeout.
    """
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
                    # Short grace period for trailing bytes of the same burst
                    time.sleep(0.12)
                    while select.select([sock], [], [], 0.05)[0]:
                        more = sock.recv(8192)
                        if not more:
                            break
                        buf += more
                    break
        elif buf and not markers and (time.time() - last_data) >= idle:
            # Idle-exit only when we are not waiting for a specific prompt.
            # tbaMUD "Attempting to Detect Client..." can pause >1s mid-banner.
            break

    return buf.decode("utf-8", errors="ignore")


def send_line(sock: socket.socket, line: str) -> None:
    sock.sendall((line + "\n").encode("utf-8"))


def login(sock: socket.socket, user: str, password: str) -> str:
    """
    Complete the tbaMUD login handshake and return accumulated transcript.
    Raises RuntimeError on obvious failures.
    """
    transcript: list[str] = []

    # Wait for name prompt (client detection can take a couple seconds)
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

    # CircleMUD/tbaMUD often wants RETURN through MOTD, or a menu selection.
    for _ in range(6):
        text = strip_ansi("".join(transcript)).lower()
        latest = strip_ansi(transcript[-1]).lower() if transcript else ""

        if "press return" in latest or "hit return" in latest or "*** press" in latest:
            send_line(sock, "")
            more = recv_until(sock, idle=0.5, overall=6.0, stop_on=["press return", ">", "1)"])
            transcript.append(more)
            continue

        # Main menu style: "1) Enter the game"
        if re.search(r"\b1\)\s*enter", latest) or (
            "make your choice" in latest and "1)" in latest
        ):
            send_line(sock, "1")
            more = recv_until(sock, idle=0.5, overall=6.0, stop_on=[">", "press return"])
            transcript.append(more)
            continue

        # In-game prompt usually ends with "> " (e.g. "24H 100M 85V > ")
        if ">" in latest and "by what name" not in latest:
            break

        # Reconnecting lands straight in-game with a prompt
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
    """
    Connect, optionally log in, send one command, return the response text.
    """
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.setblocking(False)

            login_text = ""
            if login_enabled and user:
                try:
                    login_text = login(sock, user, password)
                except RuntimeError as exc:
                    return str(exc)

            # Send the actual game command
            send_line(sock, command)
            response = recv_until(
                sock,
                idle=0.45,
                overall=6.0,
                stop_on=None,
            )

            # If the server was silent, surface that clearly
            if not response.strip():
                # Sometimes the useful output was only on the login path
                # (e.g. empty command after reconnect). Fall back carefully.
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
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        return f"CONNECTION ERROR: {exc}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Send one command to a tbaMUD/CircleMUD server and print the response."
    )
    p.add_argument(
        "command",
        nargs="?",
        default="look",
        help='Game command to send (default: "look"). Quote multi-word commands.',
    )
    p.add_argument("--host", default=DEFAULT_HOST, help=f"MUD host (default: {DEFAULT_HOST})")
    p.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"MUD port (default: {DEFAULT_PORT})"
    )
    p.add_argument(
        "--user",
        default=DEFAULT_USER,
        help=f"Character name (default: env MUD_USER or '{DEFAULT_USER}')",
    )
    p.add_argument(
        "--password",
        default=DEFAULT_PASS,
        help="Character password (default: env MUD_PASS or skill default)",
    )
    p.add_argument(
        "--no-login",
        action="store_true",
        help="Skip login; send the command raw on a fresh connection (debug only).",
    )
    p.add_argument(
        "--ansi",
        action="store_true",
        help="Keep ANSI color codes in the output.",
    )
    p.add_argument(
        "--echo",
        action="store_true",
        help="Echo the command being sent (prefixed with '>>> ').",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.echo:
        print(f">>> {args.command}")

    result = send_command(
        args.command,
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        login_enabled=not args.no_login,
        keep_ansi=args.ansi,
    )
    print(result)

    # Non-zero exit on hard errors so agents/scripts can detect failures
    if result.startswith(("CONNECTION ERROR:", "TIMEOUT ERROR:", "LOGIN ERROR:")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
