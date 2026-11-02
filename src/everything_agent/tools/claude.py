"""Claude answers hard questions, through an Anthropic API key or a Claude setup token."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

from ..settings import API_KEY, DESKTOP_TOKEN_ENV, FIELDS, SETUP_TOKEN, Settings

logger = logging.getLogger(__name__)

_SPOKEN_ANSWER = (
    "You answer questions for Reachy, a small desk robot, and your answer is read aloud by its voice. "
    "Answer in two or three short spoken sentences: no markdown, lists, code, links or sources. Reachy "
    "has already told the user it's looking into it, so never say you are searching or checking; start "
    "with the answer. Use web search only when the question needs current information, and use as few "
    "searches as give a reliable answer. If you can't find out, say so in one sentence. Today is {today}."
)
_MAX_TOKENS = 2048
_MAX_CONTINUATIONS = 3
_WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
_SECRET_ENV = {f.key for f in FIELDS if f.kind == "secret"} | {"WEB_PIN", "WEB_PIN_HASH", DESKTOP_TOKEN_ENV, "EVERYTHING_AGENT_CORE_TOKEN"}


class ClaudeError(Exception):
    """A failure, worded to be spoken."""


def _system() -> str:
    return _SPOKEN_ANSWER.format(today=datetime.now().astimezone().strftime("%A %d %B %Y, %H:%M %Z"))


class ApiKeyClaude:
    """The Claude API, called directly with an Anthropic API key."""

    name = "Anthropic API key"

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s, max_retries=1)
        self.model = model

    async def warm_up(self) -> None:
        pass

    async def answer(self, question: str) -> AsyncIterator[str]:
        anthropic = self._anthropic
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        try:
            for _ in range(_MAX_CONTINUATIONS):
                async with self._client.messages.stream(
                    model=self.model, max_tokens=_MAX_TOKENS, system=_system(), tools=[_WEB_SEARCH],
                    output_config={"effort": "low"}, messages=messages,
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_delta" and event.delta.type == "text_delta":
                            yield event.delta.text
                    message = await stream.get_final_message()
                if message.stop_reason == "refusal":
                    raise ClaudeError("Claude couldn't help with that one.")
                if message.stop_reason != "pause_turn":
                    return
                messages = [*messages, {"role": "assistant", "content": message.content}]
        except anthropic.AuthenticationError as exc:
            raise ClaudeError("The Anthropic API key was rejected.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ClaudeError("The Anthropic API key isn't allowed to use Claude.") from exc
        except anthropic.RateLimitError as exc:
            raise ClaudeError("Claude has reached its usage limit for now.") from exc
        except anthropic.BadRequestError as exc:
            if "credit balance" in str(exc).lower():
                raise ClaudeError("The Anthropic account is out of credit.") from exc
            raise ClaudeError("Claude couldn't take that question.") from exc
        except anthropic.APIStatusError as exc:
            raise ClaudeError("Claude ran into a problem.") from exc
        except anthropic.APIConnectionError as exc:
            raise ClaudeError("Couldn't reach Claude.") from exc

    async def close(self) -> None:
        await self._client.close()


class SetupTokenClaude:
    """Claude Code's agent through the Agent SDK, signed in with a ``claude setup-token`` token.

    The agent process is kept running between questions; starting it takes seconds.
    """

    name = "Claude setup token"

    def __init__(self, token: str, model: str) -> None:
        self.token = token
        self.model = model
        self._client: Any = None
        self._lock = asyncio.Lock()

    def options(self) -> Any:
        from claude_agent_sdk import ClaudeAgentOptions

        workspace = os.path.join(tempfile.gettempdir(), "everything-agent-claude")
        os.makedirs(workspace, exist_ok=True)
        hidden = {key: "" for key in os.environ if key in _SECRET_ENV or key.startswith(("CLAUDE", "ANTHROPIC"))}
        return ClaudeAgentOptions(
            model=self.model,
            system_prompt=_system(),
            tools=["WebSearch"],
            allowed_tools=["WebSearch"],
            permission_mode="dontAsk",
            setting_sources=[],
            mcp_servers={},
            strict_mcp_config=True,
            include_partial_messages=True,
            effort="low",
            max_turns=3,
            cwd=workspace,
            env={**hidden, "CLAUDE_CODE_OAUTH_TOKEN": self.token},
        )

    async def _connected(self) -> Any:
        if self._client is None:
            from claude_agent_sdk import ClaudeSDKClient

            started = time.monotonic()
            client = ClaudeSDKClient(options=self.options())
            await client.connect()
            self._client = client
            logger.info("Claude's agent started in %.1fs", time.monotonic() - started)
        return self._client

    async def warm_up(self) -> None:
        """Start the agent and send it one tiny question, so the user's first one is quick."""
        try:
            async for _ in self.answer("Reply with just: ok"):
                pass
        except ClaudeError as exc:
            logger.warning("Claude's agent didn't warm up: %s", exc)

    async def answer(self, question: str) -> AsyncIterator[str]:
        from claude_agent_sdk import ClaudeSDKError, ResultMessage
        from claude_agent_sdk.types import StreamEvent

        async with self._lock:
            finished = False
            try:
                client = await self._connected()
                await client.query(question, session_id=str(uuid.uuid4()))
                async for message in client.receive_response():
                    if isinstance(message, StreamEvent):
                        event = message.event
                        delta = event.get("delta") or {}
                        if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                            yield delta.get("text", "")
                    elif isinstance(message, ResultMessage):
                        finished = True
                        if message.is_error:
                            raise ClaudeError(_describe(message))
            except ClaudeSDKError as exc:
                logger.warning("Claude's agent failed: %s", exc)
                raise ClaudeError("Claude ran into a problem.") from exc
            finally:
                if not finished:
                    await self.close()

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            with contextlib.suppress(Exception):
                await client.disconnect()


def _describe(result: Any) -> str:
    text = f"{result.result or ''} {result.errors or ''} {result.api_error_status or ''}".lower()
    if result.api_error_status in (401, 403) or any(m in text for m in ("oauth", "not logged in", "invalid", "unauthorized")):
        return "The Claude setup token was rejected."
    if result.api_error_status == 429 or "limit" in text:
        return "Claude has reached its usage limit for now."
    if result.stop_reason == "refusal":
        return "Claude couldn't help with that one."
    return "Claude ran into a problem."


def backends(settings: Settings) -> list[ApiKeyClaude | SetupTokenClaude]:
    """The configured ways in, preferred first; the rest are fallbacks."""
    found: dict[str, ApiKeyClaude | SetupTokenClaude] = {}
    if settings.anthropic_api_key:
        found[API_KEY] = ApiKeyClaude(settings.anthropic_api_key, settings.claude_model, settings.claude_timeout_s)
    if settings.claude_setup_token:
        found[SETUP_TOKEN] = SetupTokenClaude(settings.claude_setup_token, settings.claude_model)
    order = sorted(found, key=lambda kind: kind != settings.claude_auth)
    return [found[kind] for kind in order]
