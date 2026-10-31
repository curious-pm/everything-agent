"""Cartesia streaming speech to text."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any, AsyncIterator
from urllib.parse import urlencode

import websockets

logger = logging.getLogger(__name__)

STT_URL = "wss://api.cartesia.ai/stt/websocket"
STT_VERSION = "2026-08-14"


class SttSession:
    def __init__(self, ws: Any) -> None:
        self._ws = ws

    async def send_audio(self, pcm16: bytes) -> None:
        await self._ws.send(pcm16)

    async def finalize(self) -> None:
        await self._ws.send("finalize")

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._ws.send("close")
        with contextlib.suppress(Exception):
            await self._ws.close()

    async def events(self) -> AsyncIterator[tuple[str, str]]:
        """``("text", words)`` as they're recognized, ``("flushed", "")`` after a finalize."""
        async for raw in self._ws:
            try:
                event = json.loads(raw)
            except (TypeError, ValueError):
                continue
            kind = event.get("type")
            if kind == "transcript" and event.get("text"):
                yield "text", event["text"]
            elif kind == "flush_done":
                yield "flushed", ""
            elif kind == "error":
                raise RuntimeError(f"Cartesia speech to text: {event.get('message') or event}")


async def connect(api_key: str, model: str, sample_rate: int, attempts: int = 3) -> SttSession:
    params = {"model": model, "encoding": "pcm_s16le", "sample_rate": str(sample_rate), "cartesia_version": STT_VERSION}
    url = f"{STT_URL}?{urlencode(params)}"
    for attempt in range(1, attempts + 1):
        try:
            return SttSession(await websockets.connect(url, additional_headers={"X-API-Key": api_key}, open_timeout=5))
        except (OSError, asyncio.TimeoutError, websockets.InvalidHandshake) as exc:
            if attempt == attempts or isinstance(exc, websockets.InvalidStatus):
                raise
            logger.info("Speech to text didn't connect (%s); trying again", type(exc).__name__)
            await asyncio.sleep(0.2)
