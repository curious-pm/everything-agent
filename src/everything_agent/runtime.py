"""Keeps a conversation running, restarting it when settings change or it fails."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from . import mute
from .conversation.engine import Conversation, Robot
from .events import Events
from .settings import Settings

logger = logging.getLogger(__name__)

_RETRY_S = 3.0


class Runtime:
    def __init__(self, robot: Robot, restart_process: Callable[[], None] | None = None) -> None:
        self.robot = robot
        self.events = Events()
        self.settings = Settings.load()
        self.conversation: Conversation | None = None
        self.state = "starting"
        self.problem = ""
        self.restart_process = restart_process
        self._reload = asyncio.Event()

    def status(self) -> dict[str, Any]:
        if self.conversation is not None and self.state == "running":
            return {**self.conversation.status(), "problem": self.problem}
        muted = mute.read()
        return {
            "session": self.state,
            "phase": "idle",
            "missing": self.settings.missing(),
            "problem": self.problem,
            "mic_muted": muted.mic,
            "speaker_muted": muted.speaker,
        }

    def reload(self) -> None:
        """Pick up saved settings: the current conversation ends and a new one starts."""
        self._reload.set()

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self._reload.clear()
            self.settings = Settings.load(self.settings.env_path)
            missing = self.settings.missing()
            if missing:
                self.state = "needs_setup"
                logger.info("Waiting for settings: %s", ", ".join(missing))
                await _first(stop.wait(), self._reload.wait())
                continue

            self.state = "starting"
            conversation = Conversation(self.settings, self.robot, self.events)
            self.conversation = conversation
            session_stop = asyncio.Event()
            relay = asyncio.create_task(_set_when(session_stop, stop, self._reload))
            prefetch = asyncio.create_task(_prefetch_voices(self.settings.cartesia_api_key))
            try:
                self.state = "running"
                self.problem = ""
                logger.info(
                    "Conversation started: %s via %s, voice %s, language %s",
                    self.settings.llm_model, self.settings.llm_base_url, self.settings.voice_id, self.settings.language,
                )
                await conversation.run(session_stop)
            except Exception as exc:
                logger.exception("The conversation stopped unexpectedly; starting again")
                self.problem = f"{type(exc).__name__}: {exc}"
                self.state = "restarting"
                await _first(stop.wait(), asyncio.sleep(_RETRY_S))
            finally:
                relay.cancel()
                prefetch.cancel()
                self.conversation = None
        self.state = "stopped"


async def _first(*aws: Any) -> None:
    tasks = [asyncio.ensure_future(a) for a in aws]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()


async def _set_when(target: asyncio.Event, *sources: asyncio.Event) -> None:
    await _first(*(s.wait() for s in sources))
    target.set()


async def _prefetch_voices(api_key: str) -> None:
    """The voice picker lists a thousand voices; fetching them takes seconds, so it starts early."""
    import httpx

    from .voice import voices

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await voices.library(client, api_key)
    except httpx.HTTPError as exc:
        logger.debug("Couldn't fetch the voice library ahead of time: %s", exc)
