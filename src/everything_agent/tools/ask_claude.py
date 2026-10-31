"""Hands hard questions to Claude Code in the background; Reachy speaks the answer when it comes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..settings import Settings
from . import Tool, ToolContext, claude_code

logger = logging.getLogger(__name__)


class AskClaude(Tool):
    name = "ask_claude"
    description = (
        "Hand a hard question to Claude, a much more capable assistant with live web access that can "
        "also read folders the user has shared with it. Use it whenever the question needs current or recent "
        "information (news, prices, scores, releases, anything after your training), a web look-up, the "
        "user's files, or careful multi-step reasoning, research or planning you would otherwise guess at. "
        "Also use it whenever the user asks you to ask Claude or to look something up properly. Never say "
        "you can't browse or don't have current information: call this instead. Don't use it for chit-chat "
        "or things you already know well, since it takes ten seconds or more. When you call it, say one "
        "short sentence that you're looking into it, and don't answer the question yourself; Claude's "
        "answer is spoken to the user automatically when it's ready."
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
        self.command = settings.claude_code_command
        self.timeout_s = settings.claude_code_timeout_s
        self.folders = settings.claude_code_folders
        self.busy = False

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        question = str(args.get("question") or "").strip()
        if not question:
            return "No question was given."
        if self.busy:
            return "Claude is still working on the previous question; its answer comes first."
        self.busy = True
        ctx.spawn(self._answer(question, ctx)).add_done_callback(self._done)
        return "Claude is working on it; the answer will be spoken when it's ready."

    def _done(self, _task: asyncio.Task) -> None:
        self.busy = False

    async def _answer(self, question: str, ctx: ToolContext) -> None:
        logger.info("Asking Claude Code: %s", question)
        answer = await claude_code.ask(question, self.command, self.timeout_s, self.folders)
        self.busy = False
        if answer.text:
            logger.info("Claude answered in %.1fs", answer.seconds)
            ctx.announce(answer.text)
        else:
            logger.warning("Claude Code couldn't answer after %.1fs: %s", answer.seconds, answer.error)
            ctx.announce(f"Sorry, I couldn't get an answer from Claude. {claude_code.describe(answer.error)}")
