"""Notices the laptop waking from sleep, after which USB, audio and network handles are stale."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

_TICK_S = 5.0
_SUSPEND_GAP_S = 30.0


def watch_for_resume(on_resume: Callable[[], None]) -> None:
    def watch() -> None:
        last = time.time()
        while True:
            time.sleep(_TICK_S)
            now = time.time()
            if now - last > _TICK_S + _SUSPEND_GAP_S:
                logger.info("Woke from sleep (%.0fs gap)", now - last - _TICK_S)
                try:
                    on_resume()
                except Exception:
                    logger.exception("Resume handler failed")
            last = now

    threading.Thread(target=watch, name="resume-watch", daemon=True).start()
