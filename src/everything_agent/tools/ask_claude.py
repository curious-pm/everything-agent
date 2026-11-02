"""Hands hard questions to Claude in the background; Reachy speaks the answer as it arrives."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator

from ..settings import Settings
from . import Tool, ToolContext, claude

logger = logging.getLogger(__name__)


class AskClaude(Tool):
    name = "ask_claude"
    description = (
        "Hand a hard question to Claude, a much more capable assistant with live web access. Use it "
        "whenever the question needs current or recent information (news, prices, scores, releases, "
        "anything after your training), a web look-up, or careful multi-step reasoning, research or "
        "planning you would otherwise guess at. Also use it whenever the user asks you to ask Claude or "
        "to look something up properly. Never say you can't browse or don't have current information: "
        "call this instead. Don't use it for chit-chat or things you already know well. When you call "
        "it, say one short sentence that you're looking into it, and don't answer the question yourself; "
        "Claude's answer is spoken to the user automatically."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The full question, standing on its own: Claude can't see this conversation, so include every detail it needs.",
            },
        },
        "required": ["question"],
    }
    follow_up = False
    ack = "Let me look into that."

    def __init__(self, settings: Settings) -> None:
        self.backends = claude.backends(settings)
        self.timeout_s = settings.claude_timeout_s
        self.busy = False

    async def warm_up(self) -> None:
        if self.backends:
            await self.backends[0].warm_up()

    async def close(self) -> None:
        for backend in self.backends:
            await backend.close()

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        question = str(args.get("question") or "").strip()
        if not question:
            return "No question was given."
        if self.busy:
            return "Claude is still working on the previous question; its answer comes first."
        self.busy = True
        ctx.announce_stream(self.answer(question))
        return "Claude is working on it; the answer will be spoken when it's ready."

    async def answer(self, question: str) -> AsyncIterator[str]:
        """Claude's answer as it streams, trying the other way in if the first fails before saying anything."""
        logger.info("Asking Claude: %s", question)
        started = time.monotonic()
        reason = "Claude ran into a problem."
        try:
            async with asyncio.timeout(self.timeout_s):
                for backend in self.backends:
                    spoke = False
                    try:
                        async for text in backend.answer(question):
                            if not spoke:
                                logger.info("Claude (%s) started answering after %.1fs", backend.name, time.monotonic() - started)
                            spoke = True
                            yield text
                        return
                    except claude.ClaudeError as exc:
                        reason = str(exc)
                        logger.warning("Claude via %s couldn't answer: %s", backend.name, exc)
                        if spoke:
                            return
        except TimeoutError:
            reason = f"Claude took longer than {self.timeout_s:.0f} seconds."
            logger.warning(reason)
        finally:
            self.busy = False
        yield f"Sorry, I couldn't get an answer from Claude. {reason}"
