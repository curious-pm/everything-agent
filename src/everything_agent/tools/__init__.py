"""Things Reachy can do besides talking, offered to the model as tool calls."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

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

    def schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


def available(settings: Settings) -> list[Tool]:
    from . import ask_claude, claude_code

    if settings.claude_code and claude_code.executable(settings.claude_code_command):
        return [ask_claude.AskClaude(settings)]
    return []
