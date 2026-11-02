"""The "is everything working" checklist on the Advanced settings page."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ..settings import API_KEY, Settings
from ..voice.voices import VOICES_URL, headers

DAEMON_STATUS_URL = "http://127.0.0.1:8000/api/daemon/status"
_MIC_STALE_S = 3.0


def _result(status: str, detail: str) -> dict[str, str]:
    """status is ok, warn, fail or off."""
    return {"status": status, "detail": detail}


def _rejected(what: str, resp: httpx.Response) -> dict[str, str]:
    if resp.status_code in (401, 403):
        return _result("fail", f"{what} rejected the key (HTTP {resp.status_code}).")
    return _result("warn", f"Couldn't confirm the {what} key (HTTP {resp.status_code}).")


async def check_cartesia(client: httpx.AsyncClient, settings: Settings) -> dict[str, str]:
    if not settings.cartesia_api_key:
        return _result("fail", "No Cartesia key yet.")
    try:
        resp = await client.get(VOICES_URL, params={"limit": 1}, headers=headers(settings.cartesia_api_key))
    except httpx.HTTPError as exc:
        return _result("warn", f"Couldn't reach Cartesia: {type(exc).__name__}.")
    return _result("ok", "Cartesia key works.") if resp.status_code == 200 else _rejected("Cartesia", resp)


async def check_model(client: httpx.AsyncClient, settings: Settings) -> dict[str, str]:
    if settings.llm_provider == "ollama":
        url, auth, what = f"{settings.llm_base_url}/api/tags", {}, "Ollama"
    else:
        if not settings.llm_api_key:
            return _result("fail", "No AI model key yet.")
        path = "key" if "openrouter.ai" in settings.llm_base_url else "models"
        url, auth, what = f"{settings.llm_base_url}/{path}", {"Authorization": f"Bearer {settings.llm_api_key}"}, "AI model provider"
    try:
        resp = await client.get(url, headers=auth)
    except httpx.HTTPError as exc:
        return _result("fail", f"Couldn't reach the {what}: {type(exc).__name__}.")
    return _result("ok", f"{settings.llm_model} via {what}.") if resp.status_code == 200 else _rejected(what, resp)


async def check_robot(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        status = (await client.get(DAEMON_STATUS_URL)).json()
    except (httpx.HTTPError, ValueError):
        return _result("fail", "The robot service isn't answering.")
    if status.get("state") != "running":
        return _result("fail", status.get("error") or f"The robot service is {status.get('state')}.")
    if status.get("mockup_sim_enabled") or status.get("simulation_enabled"):
        return _result("ok", "No robot connected; using this computer's microphone and speaker.")
    return _result("ok", "Robot connected.")


def check_mic(live: dict[str, Any]) -> dict[str, str]:
    age = live.get("mic_frame_age_s")
    if live.get("session") != "running" or (age is None and (live.get("uptime_s") or 0) < _MIC_STALE_S):
        return _result("warn", "Reachy is still starting; check again in a moment.")
    if age is None:
        return _result("fail", "No sound from the microphone yet.")
    if age > _MIC_STALE_S:
        return _result("fail", f"The microphone stopped sending sound {age:.0f}s ago.")
    if live.get("mic_muted"):
        return _result("warn", "Reachy's microphone is muted.")
    if not live.get("mic_level"):
        return _result("ok", "The microphone is on. Say something and watch Reachy start listening.")
    return _result("ok", "The microphone is sending sound.")


async def check_claude(settings: Settings) -> dict[str, str]:
    if not settings.claude:
        return _result("off", "Turned off; Reachy answers everything itself.")
    key, token = settings.anthropic_api_key, settings.claude_setup_token
    if not key and not token:
        return _result("warn", "No Anthropic API key or Claude setup token yet, so Reachy answers hard questions itself.")
    using_key = bool(key) and (settings.claude_auth == API_KEY or not token)
    backup = ""
    if key and token:
        backup = " The setup token is the backup." if using_key else " The API key is the backup."
    if not using_key:
        return _result("ok", f"Using the Claude setup token ({settings.claude_model}).{backup}")
    import anthropic

    try:
        async with anthropic.AsyncAnthropic(api_key=key, timeout=8.0, max_retries=0) as client:
            await client.models.retrieve(settings.claude_model)
    except anthropic.AuthenticationError:
        return _result("fail", "Anthropic rejected the API key.")
    except anthropic.NotFoundError:
        return _result("fail", f"The API key can't use {settings.claude_model}.")
    except anthropic.APIStatusError as exc:
        return _result("warn", f"Couldn't confirm the Anthropic API key (HTTP {exc.status_code}).")
    except anthropic.APIConnectionError:
        return _result("warn", "Couldn't reach Anthropic.")
    return _result("ok", f"Anthropic API key works ({settings.claude_model}).{backup}")


async def run_checks(settings: Settings, live: dict[str, Any]) -> dict[str, dict[str, str]]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        cartesia, model, robot, claude = await asyncio.gather(
            check_cartesia(client, settings), check_model(client, settings), check_robot(client), check_claude(settings),
        )
    return {"cartesia": cartesia, "llm": model, "robot": robot, "mic": check_mic(live), "claude": claude}
