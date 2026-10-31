"""What happened in the conversation, kept briefly for the pages that follow it live."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

MAX_EVENTS = 200


class Events:
    """A thread-safe ring buffer of numbered events; readers ask for what's newer than a number."""

    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._seq = 0

    def publish(self, kind: str, /, **data: Any) -> None:
        with self._lock:
            self._seq += 1
            self._events.append({"seq": self._seq, "at": time.time(), "kind": kind, **data})

    def since(self, seq: int) -> tuple[int, list[dict[str, Any]]]:
        """(latest number, events newer than ``seq``), oldest first."""
        with self._lock:
            return self._seq, [e for e in self._events if e["seq"] > seq]

    @property
    def latest(self) -> int:
        with self._lock:
            return self._seq
