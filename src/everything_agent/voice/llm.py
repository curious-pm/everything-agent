"""Streaming replies from any OpenAI-compatible API, or Ollama."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

import httpx

from ..settings import Settings
from ..tools import ToolCall

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    """One pooled client, so every reply reuses a warm connection."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0), limits=httpx.Limits(keepalive_expiry=120.0),
        )
    return _client


async def warm_up(settings: Settings) -> None:
    """Open the connection (DNS, TLS) before the first reply needs it."""
    try:
        await client().head(settings.llm_base_url, timeout=5.0)
    except httpx.HTTPError as exc:
        logger.debug("Couldn't pre-open the model connection: %s", exc)


class ReplyError(RuntimeError):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


_RETRY_STATUSES = {429, 500, 502, 503, 504}


def _no_thinking(settings: Settings) -> dict[str, Any]:
    """How each provider is told to skip its reasoning step; unknown providers get nothing."""
    if settings.llm_thinking:
        return {}
    if "openrouter.ai" in settings.llm_base_url:
        return {"reasoning": {"enabled": False}}
    if "generativelanguage.googleapis.com" in settings.llm_base_url:
        return {"reasoning_effort": "none"}
    return {}


_thinking_required: set[str] = set()


async def stream_reply(
    settings: Settings, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str | ToolCall]:
    """Yield the reply's text as it's generated, then the tool calls."""
    if settings.llm_provider == "ollama":
        async for item in _ollama(settings, messages, tools):
            yield item
        return
    extra = {} if settings.llm_model in _thinking_required else _no_thinking(settings)
    if tools:
        extra = {**extra, "tools": tools}
    retried = False
    for _ in range(3):
        try:
            async for item in _openai(settings, messages, extra):
                yield item
            return
        except ReplyError as exc:
            about_tools = "tool" in str(exc).lower()
            if exc.status == 400 and set(extra) - {"tools"} and not about_tools:
                logger.info("%s won't skip its reasoning step; letting it think", settings.llm_model)
                _thinking_required.add(settings.llm_model)
                extra = {k: v for k, v in extra.items() if k == "tools"}
            elif exc.status in (400, 404) and "tools" in extra:
                logger.warning("%s can't use tools (%s); replying without them", settings.llm_model, exc)
                extra = {k: v for k, v in extra.items() if k != "tools"}
            elif exc.status in _RETRY_STATUSES and not retried:
                retried = True
                logger.info("The model answered HTTP %s; trying once more", exc.status)
                await asyncio.sleep(0.5)
            else:
                raise
    async for item in _openai(settings, messages, extra):
        yield item


async def _openai(settings: Settings, messages: list[dict[str, Any]], extra: dict[str, Any]) -> AsyncIterator[str | ToolCall]:
    payload = {"model": settings.llm_model, "messages": messages, "stream": True, **extra}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with client().stream("POST", f"{settings.llm_base_url}/chat/completions", headers=headers, json=payload) as resp:
        if resp.status_code != 200:
            body = (await resp.aread()).decode("utf-8", errors="replace")[:300]
            raise ReplyError(f"HTTP {resp.status_code} from the model: {body}", resp.status_code)
        calls: dict[int, ToolCall] = {}
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if event.get("error"):
                raise ReplyError(str(event["error"]))
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    yield delta["content"]
                for piece in delta.get("tool_calls") or []:
                    call = calls.setdefault(piece.get("index", len(calls)), ToolCall(id="", name=""))
                    call.id = piece.get("id") or call.id
                    function = piece.get("function") or {}
                    call.name += function.get("name") or ""
                    call.arguments += function.get("arguments") or ""
        for index, call in sorted(calls.items()):
            if call.name:
                call.id = call.id or f"call_{index}"
                yield call


async def _ollama(
    settings: Settings, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
) -> AsyncIterator[str | ToolCall]:
    payload = {"model": settings.llm_model, "messages": messages, "stream": True, "think": settings.llm_thinking, "keep_alive": "10m"}
    if tools:
        payload["tools"] = tools
    calls: list[ToolCall] = []
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
    async with client().stream("POST", f"{settings.llm_base_url}/api/chat", headers=headers, json=payload) as resp:
        if resp.status_code != 200:
            body = (await resp.aread()).decode("utf-8", errors="replace")[:300]
            raise ReplyError(f"HTTP {resp.status_code} from Ollama: {body}", resp.status_code)
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            message = event.get("message") or {}
            if message.get("content"):
                yield message["content"]
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                arguments = function.get("arguments")
                calls.append(ToolCall(
                    id=f"call_{len(calls)}", name=function.get("name") or "",
                    arguments=arguments if isinstance(arguments, str) else json.dumps(arguments or {}),
                ))
    for call in calls:
        if call.name:
            yield call
