"""Mute switches for Reachy's microphone and speaker, kept in a file the desktop tray can flip."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import paths

_RECHECK_S = 0.5


@dataclass(frozen=True)
class Mute:
    mic: bool = False
    speaker: bool = False


_lock = threading.Lock()
_cache: dict = {"value": Mute(), "mtime": None, "checked_at": 0.0, "path": None}


def _path() -> Path:
    return paths.data_dir() / "mute.json"


def read() -> Mute:
    """The current switches; cheap enough to call per audio frame."""
    now = time.monotonic()
    path = _path()
    with _lock:
        if _cache["path"] == path and now - _cache["checked_at"] < _RECHECK_S:
            return _cache["value"]
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = None
        if _cache["path"] == path and mtime == _cache["mtime"]:
            _cache["checked_at"] = now
            return _cache["value"]
        value = Mute()
        if mtime is not None:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                value = Mute(mic=bool(raw.get("mic")), speaker=bool(raw.get("speaker")))
            except (OSError, ValueError, AttributeError):
                pass
        _cache.update(value=value, mtime=mtime, checked_at=now, path=path)
        return value


def set_mute(mic: bool | None = None, speaker: bool | None = None) -> Mute:
    with _lock:
        _cache["checked_at"] = 0.0
    current = read()
    value = Mute(mic=current.mic if mic is None else mic, speaker=current.speaker if speaker is None else speaker)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(value)), encoding="utf-8")
    tmp.replace(path)
    with _lock:
        _cache.update(value=value, mtime=path.stat().st_mtime, checked_at=time.monotonic(), path=path)
    return value
