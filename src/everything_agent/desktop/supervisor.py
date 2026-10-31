"""Runs the Reachy daemon and the conversation app as child processes and keeps them up."""

from __future__ import annotations

import enum
import logging
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import httpx
import psutil

from ..settings import DESKTOP_ENV, DESKTOP_TOKEN_ENV, RESTART_EXIT_CODE
from . import children

logger = logging.getLogger(__name__)

DAEMON_API = "http://127.0.0.1:8000/api/daemon"
APPS_API = "http://127.0.0.1:8000/api/apps"
DAEMON_MODES = {"real": [], "mockup": ["--mockup-sim"]}
MODES = ("auto", *DAEMON_MODES)
_ROBOT_SERIAL_ADAPTER_ID = "VID:PID=1A86:55D3"
_ROBOT_POLL_S = 10.0
_DAEMON_READY_S = 90.0
_APP_READY_S = 120.0
_APP_STOP_S = 20.0
_RETRY_S = 10.0
_BACKOFF_S = (1, 2, 5, 10, 30, 60)
_HEALTHY_RUN_S = 60.0


class State(enum.Enum):
    STARTING = "Starting"
    RUNNING = "Running"
    RESTARTING = "Restarting after a problem"
    ROBOT_NOT_FOUND = "Robot not found"
    DAEMON_CONFLICT = "Another Reachy app is running"
    STOPPING = "Stopping"
    STOPPED = "Stopped"


def robot_plugged_in() -> bool:
    from serial.tools import list_ports

    return any(_ROBOT_SERIAL_ADAPTER_ID in (port.hwid or "").upper() for port in list_ports.comports())


def daemon_status(timeout: float = 2.0) -> dict | None:
    try:
        r = httpx.get(f"{DAEMON_API}/status", timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _child_env(**extra: str) -> dict[str, str]:
    env = {**os.environ, DESKTOP_ENV: "1", "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", **extra}
    if sys.platform == "win32":
        _disable_ksvideosrc(env)
    return env


def _disable_ksvideosrc(env: dict[str, str]) -> None:
    ranks = [r for r in env.get("GST_PLUGIN_FEATURE_RANK", "").split(",") if r and not r.startswith("ksvideosrc:")]
    env["GST_PLUGIN_FEATURE_RANK"] = ",".join([*ranks, "ksvideosrc:0"])


class Supervisor:
    """Owns both child processes; all lifecycle work happens on one background thread."""

    def __init__(
        self,
        mode: str,
        web_port: int,
        log_dir: Path,
        state_dir: Path,
        on_change: Callable[[State, str], None],
        token: str | None = None,
    ) -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")
        self.mode = mode
        self.active_mode = "mockup"
        self.web_port = web_port
        self.token = token or secrets.token_urlsafe(32)
        self.state = State.STOPPED
        self.detail = ""
        self._log_dir = log_dir
        self._pid_file = state_dir / "daemon.pid"
        self._on_change = on_change
        self._daemon: subprocess.Popen | None = None
        self._app: subprocess.Popen | None = None
        self._stopping = threading.Event()
        self._wake = threading.Event()
        self._restart_app = False
        self._restart_all = False
        self._thread = threading.Thread(target=self._run, name="supervisor", daemon=True)

    def start(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file.parent.mkdir(parents=True, exist_ok=True)
        self._thread.start()
        threading.Thread(target=self._watch_robot, name="robot-watch", daemon=True).start()

    def stop(self, timeout: float = 60.0) -> None:
        """Stop the app, then the daemon (the robot goes to sleep); blocks until done."""
        self._stopping.set()
        self._wake.set()
        self._stop_app()
        if self._thread.ident is not None:
            self._thread.join(timeout)

    def restart_app(self) -> None:
        self._restart_app = True
        self._wake.set()
        self._stop_app()

    def restart_all(self) -> None:
        self._restart_all = True
        self._wake.set()
        self._stop_app()

    def _watch_robot(self) -> None:
        while not self._stopping.wait(_ROBOT_POLL_S):
            if self.state != State.RUNNING or self.mode != "auto":
                continue
            try:
                wanted = "real" if robot_plugged_in() else "mockup"
            except Exception:
                logger.exception("Couldn't list serial ports")
                continue
            if wanted != self.active_mode:
                logger.info("Robot %s; switching", "plugged in" if wanted == "real" else "unplugged")
                self.restart_all()

    def _set(self, state: State, detail: str = "") -> None:
        if (state, detail) == (self.state, self.detail):
            return
        self.state, self.detail = state, detail
        logger.info("State: %s%s", state.value, f" ({detail})" if detail else "")
        try:
            self._on_change(state, detail)
        except Exception:
            logger.exception("State listener failed")

    def _wait(self, seconds: float | None) -> None:
        self._wake.wait(seconds)
        self._wake.clear()

    def _run(self) -> None:
        failures = 0
        try:
            self._stop_orphaned_daemon()
            while not self._stopping.is_set():
                if not self._ensure_daemon():
                    continue
                started = time.monotonic()
                code = self._run_app()
                if self._stopping.is_set():
                    break
                self._stop_daemon()
                if self._restart_all:
                    self._restart_all = False
                    continue
                if self._restart_app or code == RESTART_EXIT_CODE:
                    self._restart_app = False
                    failures = 0
                    continue
                failures = 0 if time.monotonic() - started > _HEALTHY_RUN_S else failures + 1
                delay = _BACKOFF_S[min(failures, len(_BACKOFF_S) - 1)]
                self._set(State.RESTARTING, f"the app stopped (code {code}); trying again in {delay}s")
                self._wait(delay)
        except Exception:
            logger.exception("The supervisor crashed")
        finally:
            self._set(State.STOPPING)
            self._stop_app()
            self._stop_daemon()
            self._set(State.STOPPED)

    def _stop_orphaned_daemon(self) -> None:
        """A daemon left by a core that crashed would otherwise look like someone else's."""
        try:
            pid = int(self._pid_file.read_text(encoding="utf-8").strip())
            proc = psutil.Process(pid)
            if children.DAEMON_ENTRY not in proc.cmdline():
                return
        except (OSError, ValueError, psutil.Error):
            return
        logger.info("Stopping a daemon left over from the last run (pid %s)", pid)
        self._shutdown_daemon(proc)
        self._pid_file.unlink(missing_ok=True)

    def _ensure_daemon(self) -> bool:
        """True once our daemon runs; otherwise sets a state, waits and returns False."""
        if self._daemon is not None and self._daemon.poll() is None:
            if (daemon_status() or {}).get("state") == "running":
                return True
            self._stop_daemon()
        if self._daemon is None and daemon_status() is not None:
            self._set(State.DAEMON_CONFLICT, "Quit Reachy Mini Control or any other Reachy app; Reachy starts by itself after that.")
            self._wait(_RETRY_S)
            return False

        if self.mode == "auto":
            try:
                self.active_mode = "real" if robot_plugged_in() else "mockup"
            except Exception:
                logger.exception("Couldn't list serial ports; starting without the robot")
                self.active_mode = "mockup"
        else:
            self.active_mode = self.mode
        self._set(State.STARTING, "connecting to the robot" if self.active_mode == "real" else "starting with this computer's microphone and speaker")
        autostart = self.active_mode == "mockup"
        with open(self._log_dir / "daemon.log", "a", encoding="utf-8", errors="replace") as log:
            self._daemon = subprocess.Popen(
                children.command(
                    children.DAEMON_ENTRY, *DAEMON_MODES[self.active_mode], "--goto-sleep-on-stop",
                    "--wake-up-on-start" if autostart else "--no-autostart",
                ),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=children.NO_WINDOW, env=_child_env(),
            )
        self._pid_file.write_text(str(self._daemon.pid), encoding="utf-8")

        deadline = time.monotonic() + _DAEMON_READY_S
        status: dict | None = None
        start_requested = autostart
        while time.monotonic() < deadline and not self._stopping.is_set() and self._daemon.poll() is None:
            status = daemon_status()
            state = (status or {}).get("state")
            if state in ("running", "error"):
                break
            if state in ("not_initialized", "stopped") and not start_requested:
                try:
                    httpx.post(f"{DAEMON_API}/start", params={"wake_up": "true"}, timeout=5).raise_for_status()
                    start_requested = True
                except httpx.HTTPError:
                    pass
            self._wake.wait(1.0)
        if self._stopping.is_set():
            return False
        if (status or {}).get("state") == "running":
            if autostart:
                self._stop_daemon_started_app()
            return True
        reason = ((status or {}).get("error") or "the robot service didn't start").rstrip(".")
        self._set(State.ROBOT_NOT_FOUND, f"{reason}. Check the robot is plugged in and switched on.")
        self._stop_daemon()
        self._wait(_RETRY_S)
        return False

    def _stop_daemon_started_app(self) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not self._stopping.is_set():
            try:
                r = httpx.get(f"{APPS_API}/current-app-status", timeout=2)
                if r.status_code == 200 and r.json():
                    logger.info("Stopping the startup app the daemon launched by itself")
                    httpx.post(f"{APPS_API}/stop-current-app", timeout=30)
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1.0)

    def _stop_daemon(self) -> None:
        proc, self._daemon = self._daemon, None
        if proc is not None:
            try:
                self._shutdown_daemon(psutil.Process(proc.pid))
            except psutil.Error:
                pass
            proc.wait()
        self._pid_file.unlink(missing_ok=True)

    @staticmethod
    def _shutdown_daemon(proc: psutil.Process) -> None:
        try:
            httpx.post(f"{DAEMON_API}/stop", params={"goto_sleep": "true"}, timeout=5)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                status = daemon_status()
                if not status or status.get("state") in ("stopped", "error"):
                    break
                time.sleep(0.5)
        except httpx.HTTPError:
            pass
        try:
            proc.terminate()
            proc.wait(10)
        except psutil.TimeoutExpired:
            proc.kill()
        except psutil.Error:
            pass

    def _run_app(self) -> int:
        """Start the app, report it running once its page answers, and return its exit code."""
        self._set(State.STARTING, "starting the conversation")
        with open(self._log_dir / "app-console.log", "a", encoding="utf-8", errors="replace") as log:
            self._app = subprocess.Popen(
                children.command(children.APP_MODULE),
                stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                env=_child_env(**{DESKTOP_TOKEN_ENV: self.token}), creationflags=children.NO_WINDOW,
            )
        app = self._app
        if self._stopping.is_set():
            self._stop_app()
        deadline = time.monotonic() + _APP_READY_S
        while app.poll() is None and time.monotonic() < deadline and not self._stopping.is_set():
            try:
                if httpx.get(f"http://127.0.0.1:{self.web_port}/api/auth", timeout=2).status_code == 200:
                    self._set(State.RUNNING)
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        if app.poll() is None and self.state != State.RUNNING and not self._stopping.is_set():
            logger.warning("The app runs but its page never answered on port %d", self.web_port)
            self._set(State.RUNNING, "the page isn't answering")
        code = app.wait()
        logger.info("The conversation app exited with code %s", code)
        return code

    def _stop_app(self) -> None:
        app = self._app
        if app is None or app.poll() is not None:
            return
        try:
            assert app.stdin is not None
            app.stdin.close()
        except OSError:
            pass
        try:
            app.wait(_APP_STOP_S)
        except subprocess.TimeoutExpired:
            logger.warning("The app didn't stop within %.0fs; ending it", _APP_STOP_S)
            app.kill()
            app.wait()
