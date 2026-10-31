"""Where the app keeps its settings, conversation and logs."""

from __future__ import annotations

import os
from pathlib import Path

import platformdirs

APP_DIR = "everything_agent"
HOME_ENV = "EVERYTHING_AGENT_HOME"


def _home() -> Path | None:
    value = (os.environ.get(HOME_ENV) or "").strip()
    return Path(value) if value else None


def config_dir() -> Path:
    return _home() or Path(platformdirs.user_config_dir(APP_DIR, appauthor=False))


def data_dir() -> Path:
    return _home() or Path(platformdirs.user_data_dir(APP_DIR, appauthor=False))


def log_dir() -> Path:
    home = _home()
    return home / "logs" if home else Path(platformdirs.user_log_dir(APP_DIR, appauthor=False))


def state_dir() -> Path:
    home = _home()
    return home / "state" if home else Path(platformdirs.user_state_dir(APP_DIR, appauthor=False))


def env_path() -> Path:
    return config_dir() / ".env"
