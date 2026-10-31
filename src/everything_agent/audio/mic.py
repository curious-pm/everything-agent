"""Reads the microphone on its own thread, so a slow read never stalls the event loop."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any, Callable

logger = logging.getLogger(__name__)

_MAX_BACKLOG = 500


class MicReader:
    def __init__(self, read: Callable[[], Any], loop: asyncio.AbstractEventLoop, lock: threading.Lock) -> None:
        self._read = read
        self._loop = loop
        self._frames: deque[Any] = deque(maxlen=_MAX_BACKLOG)
        self._ready = asyncio.Event()
        self.lock = lock
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, name="mic-reader", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with self.lock:
                    frame = self._read()
            except Exception:
                logger.debug("Mic read failed", exc_info=True)
                frame = None
            if frame is None:
                time.sleep(0.005)
                continue
            self._frames.append(frame)
            try:
                self._loop.call_soon_threadsafe(self._ready.set)
            except RuntimeError:
                return

    async def get(self, timeout_s: float) -> Any:
        """The next frame, or None after ``timeout_s`` without one."""
        await asyncio.sleep(0)
        if not self._frames:
            self._ready.clear()
            try:
                await asyncio.wait_for(self._ready.wait(), timeout_s)
            except asyncio.TimeoutError:
                return None
        return self._frames.popleft() if self._frames else None
