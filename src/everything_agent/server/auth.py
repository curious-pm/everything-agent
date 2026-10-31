"""Who may use the page: the desktop window by its launcher's token, a browser by PIN."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from pathlib import Path

from .. import envfile

SESSION_TTL_S = 7 * 24 * 3600
_LOCK_AFTER = 5
_LOCK_FOR_S = 300
_MAX_FAILURES_PER_HOUR = 30
_ITERATIONS = 200_000
MIN_PIN_LENGTH = 6


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def pin_matches(pin: str, stored: str) -> bool:
    try:
        _scheme, iterations, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac("sha256", pin.encode(), base64.b64decode(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


class LockedOut(Exception):
    def __init__(self, seconds: float) -> None:
        super().__init__(f"Too many wrong PINs. Try again in {seconds:.0f} seconds.")
        self.seconds = seconds


class Auth:
    def __init__(self, pin_hash: str, plain_pin: str, desktop_token: str, env_path: Path | None) -> None:
        self._pin_hash = pin_hash or (hash_pin(plain_pin) if plain_pin else "")
        self._desktop_token = desktop_token
        self._env_path = env_path
        self._sessions: dict[str, float] = {}
        self._failures: dict[str, tuple[int, float]] = {}
        self._recent_failures: list[float] = []

    @property
    def pin_set(self) -> bool:
        return bool(self._pin_hash)

    def token_ok(self, token: str | None) -> bool:
        return bool(self._desktop_token and token) and hmac.compare_digest(token.encode(), self._desktop_token.encode())

    def bearer_ok(self, authorization: str | None) -> bool:
        scheme, _, token = (authorization or "").partition(" ")
        return scheme.lower() == "bearer" and self.token_ok(token)

    def session_ok(self, session: str | None) -> bool:
        if not session or session not in self._sessions:
            return False
        now = time.monotonic()
        if self._sessions[session] < now:
            del self._sessions[session]
            return False
        self._sessions[session] = now + SESSION_TTL_S
        return True

    def _new_session(self) -> str:
        session = secrets.token_urlsafe(32)
        self._sessions[session] = time.monotonic() + SESSION_TTL_S
        return session

    def check_not_locked(self, client: str) -> None:
        now = time.monotonic()
        self._recent_failures = [t for t in self._recent_failures if now - t < 3600]
        if len(self._recent_failures) >= _MAX_FAILURES_PER_HOUR:
            raise LockedOut(self._recent_failures[0] + 3600 - now)
        count, locked_until = self._failures.get(client, (0, 0.0))
        if locked_until > now:
            raise LockedOut(locked_until - now)
        if locked_until:
            del self._failures[client]

    def login(self, pin: str, client: str) -> str | None:
        """A new session for the right PIN, None for a wrong one; raises LockedOut after too many."""
        self.check_not_locked(client)
        if self.pin_matches(pin):
            self._failures.pop(client, None)
            return self._new_session()
        now = time.monotonic()
        count = self._failures.get(client, (0, 0.0))[0] + 1
        self._failures[client] = (count, now + _LOCK_FOR_S if count >= _LOCK_AFTER else 0.0)
        self._recent_failures.append(now)
        if len(self._failures) > 1000:
            self._failures = {c: f for c, f in self._failures.items() if f[1] > now}
        return None

    def pin_matches(self, pin: str) -> bool:
        return bool(self._pin_hash) and pin_matches(pin, self._pin_hash)

    def set_pin(self, pin: str) -> str:
        """Saves a new PIN, signs everyone out and returns a session for whoever set it."""
        self._pin_hash = hash_pin(pin)
        if self._env_path is not None:
            envfile.set_values(self._env_path, {"WEB_PIN_HASH": self._pin_hash, "WEB_PIN": ""})
        self._sessions.clear()
        return self._new_session()

    def logout(self, session: str | None) -> None:
        self._sessions.pop(session or "", None)
