"""Cartesia's voice library for the voice picker, and short samples to hear a voice first."""

from __future__ import annotations

import time
from typing import Any

import httpx

API_VERSION = "2024-11-13"
VOICES_URL = "https://api.cartesia.ai/voices"
TTS_BYTES_URL = "https://api.cartesia.ai/tts/bytes"
_MAX_PAGES = 40
_CACHE_S = 6 * 3600

SAMPLE_LINES = {
    "en": "Hi! I'm Reachy. This is how I'd sound when we talk.",
    "hi": "नमस्ते! मैं रीची हूँ। हम बात करेंगे तो मैं ऐसा सुनाई दूँगा।",
    "fr": "Bonjour ! Je suis Reachy. Voici ma voix quand nous parlons.",
    "es": "¡Hola! Soy Reachy. Así sonaría cuando hablemos.",
    "de": "Hallo! Ich bin Reachy. So klinge ich, wenn wir uns unterhalten.",
    "ja": "こんにちは！リーチーです。お話しするときはこんな声です。",
}

_cache: dict[str, Any] = {"at": 0.0, "key": "", "voices": []}


def headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Cartesia-Version": API_VERSION}


def _slim(voice: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": voice.get("id", ""),
        "name": voice.get("name", ""),
        "description": voice.get("description") or "",
        "language": voice.get("language") or "",
        "gender": voice.get("gender") or "",
    }


async def library(client: httpx.AsyncClient, api_key: str) -> list[dict[str, Any]]:
    """Every active voice, from a copy refreshed every few hours."""
    if _cache["voices"] and _cache["key"] == api_key and time.monotonic() - _cache["at"] < _CACHE_S:
        return _cache["voices"]
    voices: list[dict[str, Any]] = []
    params: dict[str, Any] = {"limit": 100}
    for _ in range(_MAX_PAGES):
        resp = await client.get(VOICES_URL, params=params, headers=headers(api_key))
        resp.raise_for_status()
        page = resp.json()
        voices += [_slim(v) for v in page.get("data", []) if v.get("status", "active") == "active"]
        if not page.get("has_more") or not page.get("next_page"):
            break
        params = {"limit": 100, "starting_after": page["next_page"]}
    voices.sort(key=lambda v: v["name"].lower())
    _cache.update(at=time.monotonic(), key=api_key, voices=voices)
    return voices


async def voice(client: httpx.AsyncClient, api_key: str, voice_id: str) -> dict[str, Any] | None:
    resp = await client.get(f"{VOICES_URL}/{voice_id}", headers=headers(api_key))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return _slim(resp.json())


async def sample(client: httpx.AsyncClient, api_key: str, model: str, voice_id: str, language: str) -> bytes:
    """A short WAV of the voice saying hello, in its own language when there's a line for it."""
    lang = language if language in SAMPLE_LINES else "en"
    resp = await client.post(
        TTS_BYTES_URL,
        headers=headers(api_key),
        json={
            "model_id": model,
            "transcript": SAMPLE_LINES[lang],
            "voice": {"mode": "id", "id": voice_id},
            "language": lang,
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000},
        },
    )
    resp.raise_for_status()
    return resp.content
