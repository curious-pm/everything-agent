"""One core per user, held by a file lock the OS releases when the process exits."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import IO


class SingleInstance:
    def __init__(self, state_dir: Path) -> None:
        self._lock_path = state_dir / "launcher.lock"
        self._lock_file: IO[str] | None = None

    def acquire(self) -> bool:
        """True if no other core holds the lock; it is then held until this process exits."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(self._lock_path, "a+", encoding="utf-8")
        try:
            if sys.platform == "win32":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock_file.close()
            return False
        self._lock_file = lock_file
        return True
