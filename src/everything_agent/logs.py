"""Logging to the console and a rotating file; apps started by a launcher have no visible console."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import paths

LOG_FILES = {"app": "app.log", "desktop": "desktop.log", "daemon": "daemon.log"}
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_configured = False


def configure(name: str = "app", log_dir: Path | None = None) -> Path:
    """Attach console and file handlers to the root logger once; returns the log file."""
    global _configured
    log_dir = log_dir or paths.log_dir()
    log_path = log_dir / LOG_FILES[name]
    if _configured:
        return log_path
    _configured = True

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    root = logging.getLogger()
    root.setLevel((os.getenv("LOG_LEVEL") or "INFO").strip().upper())
    formatter = logging.Formatter(_FORMAT)
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        root.addHandler(console)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(formatter)
        root.addHandler(handler)
    except OSError:
        logging.getLogger(__name__).exception("Can't write logs to %s; console only", log_path)

    for noisy in ("websockets", "httpcore", "httpx", "asyncio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_path


def tail(name: str, lines: int, log_dir: Path | None = None) -> str:
    """The last lines of one of the app's logs, or "" if it doesn't exist yet."""
    path = (log_dir or paths.log_dir()) / LOG_FILES[name]
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 256_000))
            data = f.read()
    except OSError:
        return ""
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[-lines:])
