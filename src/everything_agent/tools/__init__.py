"""Things Reachy can do besides talking, offered to the model as tool calls."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable

from ..settings import Settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""

    def args(self) -> dict[str, Any]:
        try:
            value = json.loads(self.arguments or "{}")
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}


@dataclass
class ToolContext:
    """What a tool may do to the conversation."""

    announce: Callable[[str], None]
    announce_stream: Callable[[AsyncIterator[str]], None]
    spawn: Callable[[Awaitable[Any]], asyncio.Task]


class Tool:
    """A tool with ``follow_up = False`` works in the background and announces its own result."""

    name = ""
    description = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    follow_up = True
    ack = ""

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        raise NotImplementedError

    async def warm_up(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


def available(settings: Settings) -> list[Tool]:
    from . import ask_claude

    if settings.claude and (settings.anthropic_api_key or settings.claude_setup_token):
        return [ask_claude.AskClaude(settings)]
    return []
