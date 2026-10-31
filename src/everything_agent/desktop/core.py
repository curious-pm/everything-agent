"""Headless core for the Tauri shell: JSON-line state on stdout, JSON-line commands on stdin."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from typing import Any, Callable

from .. import envfile, mute, paths
from ..settings import DEFAULT_WEB_PORT, ensure_env_file
from . import os_events, power
from .single_instance import SingleInstance
from .supervisor import State, Supervisor

logger = logging.getLogger(__name__)

TOKEN_ENV = "EVERYTHING_AGENT_CORE_TOKEN"
DAEMON_PORT = 8000
ALREADY_RUNNING_EXIT_CODE = 3


class _Output:
    """JSON lines on the real stdout; anything else that prints goes to stderr."""

    def __init__(self) -> None:
        self._stream = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr
        self._lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        with self._lock:
            try:
                self._stream.write(json.dumps(message) + "\n")
                self._stream.flush()
            except (OSError, ValueError):
                pass


def _handle(command: dict[str, Any], supervisor: Supervisor) -> dict[str, Any] | None:
    name = command.get("cmd")
    if name == "restart":
        supervisor.restart_app()
    elif name == "restart_all":
        supervisor.restart_all()
    elif name == "mute":
        state = mute.set_mute(mic=command.get("mic"), speaker=command.get("speaker"))
        return {"mic": state.mic, "speaker": state.speaker}
    elif name == "get_mute":
        state = mute.read()
        return {"mic": state.mic, "speaker": state.speaker}
    else:
        return {"error": f"unknown command {name!r}"}
    return None


def _reply(command: dict[str, Any], supervisor: Supervisor, send: Callable[[dict], None]) -> None:
    try:
        result = _handle(command, supervisor)
    except Exception as exc:
        logger.exception("Command %r failed", command.get("cmd"))
        result = {"error": f"{type(exc).__name__}: {exc}"}
    if "id" in command:
        send({"event": "reply", "id": command["id"], "result": result})


def run(mode: str) -> int:
    out = _Output()
    instance = SingleInstance(paths.state_dir())
    if not instance.acquire():
        out.send({"event": "already_running"})
        return ALREADY_RUNNING_EXIT_CODE

    env_path = ensure_env_file()
    try:
        web_port = int(envfile.read_values(env_path).get("WEB_PORT") or DEFAULT_WEB_PORT)
    except ValueError:
        web_port = DEFAULT_WEB_PORT

    def on_change(state: State, detail: str) -> None:
        out.send({"event": "state", "state": state.name, "label": state.value, "detail": detail})

    supervisor = Supervisor(
        mode, web_port, paths.log_dir(), paths.state_dir(), on_change, token=os.environ.pop(TOKEN_ENV, None) or None,
    )
    stop_lock = threading.Lock()
    stopped = False

    def stop() -> None:
        nonlocal stopped
        with stop_lock:
            if not stopped:
                supervisor.stop()
                stopped = True

    os_events.install(stop, lambda: threading.Thread(target=stop, daemon=True).start())
    power.watch_for_resume(supervisor.restart_all)

    out.send({"event": "hello", "web_port": web_port, "daemon_port": DAEMON_PORT, "settings": str(env_path)})
    supervisor.start()
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                command = json.loads(line)
            except ValueError:
                command = None
            if not isinstance(command, dict):
                logger.warning("Ignoring a malformed command from the shell")
                continue
            if command.get("cmd") == "quit":
                break
            threading.Thread(target=_reply, args=(command, supervisor, out.send), daemon=True).start()
    finally:
        logger.info("The shell closed the control pipe; stopping")
        stop()
        out.send({"event": "stopped"})
    return 0
