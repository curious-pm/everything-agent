"""Read and edit ``.env`` files in place, keeping comments and other lines intact."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import dotenv_values

_NEEDS_QUOTING = ("\n", "\r", '"', "#", "\\", "'", "$")


def read_values(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    return {k: v for k, v in dotenv_values(path, interpolate=False).items() if v is not None}


def _quote(value: str) -> str:
    """Quote a value so it reads back unchanged; unquoted, dotenv stops at ``#`` and strips spaces."""
    if value == "":
        return ""
    if any(ch in value for ch in _NEEDS_QUOTING) or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        return f'"{escaped}"'
    return value


def _assignment(key: str) -> re.Pattern[str]:
    """``KEY=`` and its whole value, including a quoted multi-line one."""
    return re.compile(
        r"^" + re.escape(key) + r"[ \t]*=[ \t]*"
        r'(?:"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r"|[^\n]*)",
        re.MULTILINE,
    )


def set_values(path: Path, values: dict[str, str]) -> None:
    """Set or append several KEY=value lines in one atomic write."""
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for key, value in values.items():
        line = f"{key}={_quote(value)}"
        pattern = _assignment(key)
        if pattern.search(text):
            text = pattern.sub(lambda _m: line, text, count=1)
        else:
            text += ("" if not text or text.endswith("\n") else "\n") + line + "\n"
    write_private(path, text)


def write_private(path: Path, text: str) -> None:
    """Atomically write a file only its owner can read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def set_value(path: Path, key: str, value: str) -> None:
    set_values(path, {key: value})
