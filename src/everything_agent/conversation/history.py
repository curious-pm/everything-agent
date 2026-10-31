"""The running conversation, saved to disk so it survives restarts."""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from .. import envfile, paths

logger = logging.getLogger(__name__)

MAX_MESSAGES = 60


def history_path() -> Path:
    return paths.data_dir() / "conversation.json"


class History:
    def __init__(self, system_prompt: str, path: Path | None = None, keep: int = MAX_MESSAGES) -> None:
        self.path = path or history_path()
        self.keep = keep
        self.system_prompt = system_prompt
        self.messages: list[dict[str, str]] = self._load()

    def _load(self) -> list[dict[str, str]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(raw, list):
            return []
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in raw
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        ]
        return self._trimmed(messages)

    def _trimmed(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        messages = messages[-self.keep:]
        while messages and messages[0]["role"] != "user":
            messages = messages[1:]
        return messages

    def add(self, role: str, content: str) -> dict[str, str]:
        message = {"role": role, "content": content}
        self.messages.append(message)
        self.messages = self._trimmed(self.messages)
        return message

    def remove(self, message: dict[str, str]) -> None:
        self.messages = [m for m in self.messages if m is not message]

    def clear(self) -> None:
        self.messages = []
        self.save()

    def for_model(self) -> list[dict[str, str]]:
        """What the model sees: the system prompt with the real date and time, then the conversation."""
        return [{"role": "system", "content": f"{self.system_prompt}\n\n{now_context()}"}, *self.messages]

    def lines(self, limit: int) -> list[dict[str, str]]:
        return [{"role": m["role"], "text": m["content"]} for m in self.messages if m["content"].strip()][-limit:]

    def save(self) -> None:
        try:
            envfile.write_private(self.path, json.dumps(self.messages, ensure_ascii=False))
        except OSError:
            logger.warning("Couldn't save the conversation to %s", self.path, exc_info=True)


def now_context(now: dt.datetime | None = None) -> str:
    """The model has no clock and guesses old dates, so every request says what time it is."""
    now = (now or dt.datetime.now()).astimezone()
    return (
        f"Right now it is {now.strftime('%A %d %B %Y, %H:%M')} ({now.tzname()}). "
        "Use this for anything about dates or times and never guess the year."
    )
