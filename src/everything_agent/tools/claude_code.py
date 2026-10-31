"""Runs Claude Code (``claude -p``) on one question, using Claude Code's own login."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import envfile, paths
from ..settings import DESKTOP_TOKEN_ENV, FIELDS

logger = logging.getLogger(__name__)

ALLOWED_TOOLS = ("WebSearch", "WebFetch", "Read", "Glob", "Grep")
_OFF_LIMITS = tuple(
    f"{tool}(//**/{pattern})"
    for tool in ("Read", "Grep", "Glob")
    for pattern in (
        ".env", ".env.*", ".ssh/**", ".aws/**", ".claude/**", ".config/**", ".git-credentials", ".netrc",
        ".npmrc", "*.pem", "*.key", "everything_agent/**",
    )
)
_SECRET_ENV = {f.key for f in FIELDS if f.kind == "secret"} | {"WEB_PIN", "WEB_PIN_HASH", DESKTOP_TOKEN_ENV, "EVERYTHING_AGENT_CORE_TOKEN"}
_SOURCES = re.compile(r"\n+\s*(\*\*)?sources:?(\*\*)?\s*\n.*\Z", re.IGNORECASE | re.DOTALL)
_SPOKEN_ANSWER = (
    "Your answer is read aloud by a small desk robot's voice. Answer in two or three short spoken "
    "sentences: no markdown, lists, code, file paths or links. Work fast, since the user is waiting: "
    "use as few look-ups as you can. If you can't find out, say so in one sentence."
)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_AUTH_MARKERS = ("not logged in", "please run /login", "authentication", "invalid api key", "unauthorized")


@dataclass
class Answer:
    text: str = ""
    error: str = ""
    seconds: float = 0.0


def executable(command: str = "claude") -> str | None:
    if not command:
        return None
    path = Path(command)
    if path.is_absolute():
        return str(path) if path.is_file() else None
    return shutil.which(command)


def _environment() -> dict[str, str]:
    hidden = set(envfile.read_values(paths.env_path())) | _SECRET_ENV
    return {k: v for k, v in os.environ.items() if k not in hidden}


def workspace() -> Path:
    """An empty folder to run in; Claude can only read files under it and the shared folders."""
    path = Path(tempfile.gettempdir()) / "everything-agent-claude"
    path.mkdir(exist_ok=True)
    return path


def _low_priority() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS | _NO_WINDOW}
    return {"preexec_fn": lambda: os.nice(10), "start_new_session": True}


def command_line(exe: str, folders: list[str] | tuple[str, ...] = ()) -> list[str]:
    argv = [
        exe, "-p", "--output-format", "json",
        "--restricted", "--strict-mcp-config", "--no-session-persistence",
        "--tools", ",".join(ALLOWED_TOOLS),
        "--permission-mode", "dontAsk",
        "--allowedTools", ",".join(ALLOWED_TOOLS),
        "--disallowedTools", ",".join(_OFF_LIMITS),
        "--append-system-prompt", _SPOKEN_ANSWER,
    ]
    for folder in folders:
        argv += ["--add-dir", folder]
    return argv


def parse(stdout: str) -> Answer:
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return Answer(error=stdout.strip()[:200] or "Claude Code gave no answer.")
    if not isinstance(result, dict):
        return Answer(error="Claude Code stopped: no answer.")
    text = (result.get("result") or "").strip()
    if result.get("is_error") or not text:
        return Answer(error=text or f"Claude Code stopped: {result.get('subtype', 'no answer')}.")
    return Answer(text=_SOURCES.sub("", text).strip())


def describe(error: str) -> str:
    """A short spoken reason for a failure."""
    if any(marker in error.lower() for marker in _AUTH_MARKERS):
        return "Claude Code isn't signed in on this computer."
    if "usage limit" in error.lower() or "rate limit" in error.lower():
        return "Claude has reached its usage limit for now."
    return "Claude Code ran into a problem."


async def ask(question: str, command: str = "claude", timeout_s: float = 180.0, folders: tuple[str, ...] = ()) -> Answer:
    started = time.monotonic()
    exe = executable(command)
    if exe is None:
        return Answer(error="Claude Code isn't installed.")
    try:
        proc = await asyncio.create_subprocess_exec(
            *command_line(exe, folders),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=_environment(), cwd=str(workspace()), **_low_priority(),
        )
    except OSError as exc:
        return Answer(error=f"Couldn't start Claude Code: {exc}")
    try:
        out, err = await asyncio.wait_for(proc.communicate(question.encode("utf-8")), timeout_s)
    except asyncio.TimeoutError:
        _kill_tree(proc.pid)
        return Answer(error=f"Claude Code took longer than {timeout_s:.0f} seconds.", seconds=time.monotonic() - started)
    except asyncio.CancelledError:
        _kill_tree(proc.pid)
        raise
    answer = parse(out.decode("utf-8", errors="replace"))
    if not answer.text and not answer.error.strip():
        answer.error = err.decode("utf-8", errors="replace").strip()[-300:]
    answer.seconds = time.monotonic() - started
    return answer


async def version(command: str = "claude") -> str | None:
    exe = executable(command)
    if exe is None:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            exe, "--version", stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, creationflags=_NO_WINDOW,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), 20)
    except (OSError, asyncio.TimeoutError):
        return None
    return out.decode("utf-8", errors="replace").strip() or None


def _kill_tree(pid: int) -> None:
    """Claude starts its own helpers, which would outlive a plain kill."""
    import psutil

    try:
        parent = psutil.Process(pid)
        procs = [*parent.children(recursive=True), parent]
    except psutil.Error:
        return
    for proc in procs:
        with contextlib.suppress(psutil.Error):
            proc.kill()
