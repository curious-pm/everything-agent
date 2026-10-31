"""Everything Agent as a Reachy Mini app."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
from typing import Callable

from reachy_mini import ReachyMini, ReachyMiniApp

from . import envfile, logs, paths
from .robot import Robot
from .runtime import Runtime
from .server.api import serve
from .settings import DEFAULT_WEB_PORT, RESTART_EXIT_CODE, desktop_mode, ensure_env_file

logger = logging.getLogger(__name__)

__all__ = ["RESTART_EXIT_CODE", "EverythingAgent"]


def _page_url() -> str:
    """For the gear icon in Reachy Mini's own dashboard."""
    port = envfile.read_values(paths.env_path()).get("WEB_PORT") or DEFAULT_WEB_PORT
    return f"http://0.0.0.0:{port}"


class EverythingAgent(ReachyMiniApp):
    custom_app_url: str | None = _page_url()
    dont_start_webserver = True
    restart_requested = False

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        log_path = logs.configure()
        logger.info("Everything Agent starting; logs in %s", log_path)
        ensure_env_file()
        robot = Robot(reachy_mini)
        robot.start()
        breathing_stop = threading.Event()
        threading.Thread(target=robot.breathe, args=(breathing_stop,), name="breathing", daemon=True).start()
        try:
            asyncio.run(_main(robot, stop_event, self._restart if desktop_mode() else None))
        finally:
            breathing_stop.set()
            robot.stop()

    def _restart(self) -> None:
        self.restart_requested = True
        self.stop()


async def _main(robot: Robot, stop_event: threading.Event, restart: Callable[[], None] | None) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def relay_stop() -> None:
        stop_event.wait()
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(stop.set)

    threading.Thread(target=relay_stop, name="stop-relay", daemon=True).start()
    runtime = Runtime(robot, restart)
    results = await asyncio.gather(runtime.run(stop), serve(runtime, stop), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.error("Stopped with an error", exc_info=result)


if __name__ == "__main__":
    from .__main__ import main

    sys.exit(main())
