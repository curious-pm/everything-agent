"""``python -m everything_agent``: run the app against a Reachy Mini daemon that's already running."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from typing import Any

import httpx
from dotenv import load_dotenv

from . import logs, paths
from .settings import desktop_mode

logger = logging.getLogger("everything_agent")

DAEMON_STATUS_URL = "http://127.0.0.1:8000/api/daemon/status"


def _daemon_ready(timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if httpx.get(DAEMON_STATUS_URL, timeout=3).json().get("state") == "running":
                return True
        except (httpx.HTTPError, ValueError):
            pass
        if time.monotonic() > deadline:
            return False
        time.sleep(1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="everything-agent", description=__doc__)
    parser.add_argument("--wait", type=float, default=30.0, help="seconds to wait for the daemon (default 30)")
    args = parser.parse_args(argv)

    load_dotenv(paths.env_path(), override=True)
    logs.configure()
    if not _daemon_ready(args.wait):
        logger.error(
            "No Reachy Mini daemon is running on this computer. Start one first: "
            "`reachy-mini-daemon` with the robot plugged in, or `reachy-mini-daemon --mockup-sim` without it."
        )
        return 1

    from reachy_mini.media import audio_gstreamer

    from . import devices
    from .main import RESTART_EXIT_CODE, EverythingAgent

    devices.use_chosen_audio(audio_gstreamer)
    devices.cancel_echo_on_chosen_mic(audio_gstreamer)

    app = EverythingAgent()

    def stop(signum: int, _frame: Any) -> None:
        logger.info("Stopping (signal %s)", signum)
        app.stop()

    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)
    if desktop_mode() and sys.stdin is not None:
        def stop_when_pipe_closes() -> None:
            for _line in sys.stdin:
                pass
            logger.info("The desktop app closed the control pipe; stopping")
            app.stop()

        threading.Thread(target=stop_when_pipe_closes, name="launcher-pipe", daemon=True).start()

    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
    return RESTART_EXIT_CODE if app.restart_requested else 0


if __name__ == "__main__":
    sys.exit(main())
