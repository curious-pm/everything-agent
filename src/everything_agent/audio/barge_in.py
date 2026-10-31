"""Telling the user talking over Reachy apart from Reachy hearing its own voice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BargeInDetector:
    """Fed one RMS value per frame while Reachy speaks. Not thread-safe."""

    threshold: float
    duck_after_s: float = 0.15
    stop_after_s: float = 0.45
    release_s: float = 0.25
    cooldown_s: float = 1.5
    _run_started: float | None = None
    _quiet_since: float | None = None
    _ducking: bool = False
    _fired_at: float | None = None

    def observe(self, level: float, now: float) -> str:
        """``"none"``, ``"duck"`` or ``"stop"`` (once per interruption)."""
        if self._fired_at is not None and now - self._fired_at < self.cooldown_s:
            self.reset()
            return "none"
        if level >= self.threshold:
            self._quiet_since = None
            if self._run_started is None:
                self._run_started = now
                return "duck" if self._ducking else "none"
            elapsed = now - self._run_started
            if elapsed >= self.stop_after_s:
                self._fired_at = now
                self.reset()
                return "stop"
            if elapsed >= self.duck_after_s:
                self._ducking = True
            return "duck" if self._ducking else "none"
        if self._ducking:
            if self._quiet_since is None:
                self._quiet_since = now
            if now - self._quiet_since < self.release_s:
                return "duck"
        self.reset()
        return "none"

    def reset(self) -> None:
        self._run_started = None
        self._quiet_since = None
        self._ducking = False
