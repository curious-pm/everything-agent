"""Cartesia streaming text to speech over one long-lived socket."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
from typing import Any, AsyncIterator
from urllib.parse import urlencode

import numpy as np
import websockets

from .language import detect_language

logger = logging.getLogger(__name__)

TTS_URL = "wss://api.cartesia.ai/tts/websocket"
TTS_VERSION = "2024-11-13"
SAMPLE_RATE = 24000


class CartesiaTTS:
    def __init__(self, api_key: str, model: str, voice_id: str, language: str, multilingual: bool) -> None:
        self._api_key = api_key
        self._model = model
        self.voice_id = voice_id
        self._language = language
        self._multilingual = multilingual
        self._ws: Any = None
        self._seq = 0

    def _language_for(self, text: str) -> str:
        if not self._multilingual:
            return self._language
        self._language = detect_language(text, fallback=self._language)
        return self._language

    async def _connect(self, attempts: int = 3) -> Any:
        if self._ws is not None:
            return self._ws
        query = urlencode({"cartesia_version": TTS_VERSION})
        for attempt in range(1, attempts + 1):
            try:
                self._ws = await websockets.connect(
                    f"{TTS_URL}?{query}", additional_headers={"X-API-Key": self._api_key}, open_timeout=5,
                )
                return self._ws
            except (OSError, asyncio.TimeoutError, websockets.InvalidHandshake) as exc:
                if attempt == attempts or isinstance(exc, websockets.InvalidStatus):
                    raise
                logger.info("The voice didn't connect (%s); trying again", type(exc).__name__)
                await asyncio.sleep(0.2)

    async def prewarm(self) -> None:
        try:
            await self._connect()
        except Exception as exc:
            logger.warning("Couldn't pre-open the Cartesia voice socket: %s", exc)

    async def stream(self, text: str) -> AsyncIterator[np.ndarray]:
        """Mono float32 chunks at 24 kHz for ``text``, as they're synthesized."""
        self._seq += 1
        context_id = f"reply-{self._seq}"
        request = json.dumps({
            "model_id": self._model,
            "transcript": text,
            "voice": {"mode": "id", "id": self.voice_id},
            "language": self._language_for(text),
            "output_format": {"container": "raw", "encoding": "pcm_f32le", "sample_rate": SAMPLE_RATE},
            "context_id": context_id,
        })
        ws = await self._connect()
        try:
            await ws.send(request)
        except websockets.ConnectionClosed:
            self._ws = None
            ws = await self._connect()
            await ws.send(request)

        while True:
            try:
                raw = await ws.recv()
            except websockets.ConnectionClosed:
                self._ws = None
                logger.warning("The Cartesia voice socket closed mid-sentence")
                return
            message = json.loads(raw)
            if message.get("context_id") != context_id:
                continue
            kind = message.get("type")
            if kind == "chunk" and message.get("data"):
                yield np.frombuffer(base64.b64decode(message["data"]), dtype="<f4").astype(np.float32)
            elif kind == "done":
                return
            elif kind == "error":
                raise RuntimeError(f"Cartesia text to speech: {message.get('error')}")

    async def close(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            with contextlib.suppress(Exception):
                await ws.close()
