"""Plays one reply at a time from a worker thread, keeping a little ahead of the speaker."""

from __future__ import annotations

import asyncio
import logging
import queue
import time
from typing import Protocol

import numpy as np

from .. import mute
from .dsp import rms

logger = logging.getLogger(__name__)

_MAX_LEAD_S = 0.4
_END = "end"
_INTERRUPT = "interrupt"


class AudioOut(Protocol):
    sample_rate: int

    def begin_playback(self) -> None: ...
    def push(self, chunk: np.ndarray) -> None: ...
    def clear_playback(self) -> None: ...
    def end_playback(self) -> None: ...


class Speaker:
    """One reply's audio goes in with ``put``; ``finish`` waits for it to be heard (or cut off)."""

    def __init__(self, out: AudioOut, prebuffer_s: float) -> None:
        self.out = out
        self.prebuffer_s = prebuffer_s
        self.duck_gain = 1.0
        self.stop_now = False
        self.audible_until = 0.0
        self.level = 0.0
        self._queue: queue.Queue | None = None
        self._future: asyncio.Future | None = None

    @property
    def playing(self) -> bool:
        return self._queue is not None

    def begin(self, loop: asyncio.AbstractEventLoop) -> None:
        self.stop_now = False
        self.duck_gain = 1.0
        self._queue = queue.Queue()
        self._future = loop.run_in_executor(None, self._play, self._queue)

    def put(self, chunk: np.ndarray) -> None:
        if self._queue is not None and chunk.size:
            self._queue.put(chunk)

    async def finish(self, interrupt: bool = False) -> float:
        """Seconds of audio played. With ``interrupt``, queued audio is dropped."""
        q, future = self._queue, self._future
        self._queue = self._future = None
        if q is None or future is None:
            return 0.0
        q.put(_INTERRUPT if interrupt else _END)
        try:
            return await future
        except Exception:
            logger.exception("Playback failed")
            return 0.0

    def _play(self, q: queue.Queue) -> float:
        rate = self.out.sample_rate
        self.out.begin_playback()
        deadline: float | None = None
        held: list[np.ndarray] = []
        held_s = 0.0
        released = False
        gain = 1.0
        played_s = 0.0
        interrupted = False

        def push(chunk: np.ndarray) -> None:
            nonlocal deadline, gain, played_s
            now = time.monotonic()
            if deadline is None or deadline < now:
                deadline = now
            if deadline - now > _MAX_LEAD_S:
                time.sleep(deadline - now - _MAX_LEAD_S)
            if self.stop_now:
                return
            target = 0.0 if mute.read().speaker else self.duck_gain
            if target != 1.0 or gain != 1.0:
                chunk = chunk * np.linspace(gain, target, chunk.shape[0], dtype=np.float32)
            gain = target
            self.out.push(chunk.astype(np.float32, copy=False))
            deadline += chunk.size / rate
            played_s += chunk.size / rate
            self.audible_until = deadline
            self.level = rms(chunk)

        try:
            while True:
                if self.stop_now:
                    interrupted = True
                    break
                try:
                    item = q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if isinstance(item, str):
                    interrupted = item == _INTERRUPT
                    break
                if released:
                    push(item)
                    continue
                held.append(item)
                held_s += item.size / rate
                if held_s >= self.prebuffer_s:
                    released = True
                    for chunk in held:
                        push(chunk)
                    held = []
            if interrupted:
                self.out.clear_playback()
            else:
                for chunk in held:
                    push(chunk)
                if deadline is not None:
                    time.sleep(max(0.0, deadline - time.monotonic()))
        finally:
            self.out.end_playback()
            self.level = 0.0
        return played_s
