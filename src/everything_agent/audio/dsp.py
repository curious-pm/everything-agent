"""Audio helpers shared by the microphone and speaker paths."""

from __future__ import annotations

import numpy as np


def to_mono(frame: np.ndarray) -> np.ndarray:
    """One channel of float32 samples, whatever layout the SDK handed over."""
    if frame.ndim == 2:
        if frame.shape[1] > frame.shape[0]:
            frame = frame.T
        frame = frame[:, 0]
    return frame.astype(np.float32, copy=False)


def rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0


def float_to_pcm16(samples: np.ndarray) -> bytes:
    """float32 in [-1, 1] to signed 16-bit little-endian PCM."""
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


class Resampler:
    """Streaming linear resampler that stays phase-continuous across chunks, so there are no clicks."""

    def __init__(self, in_rate: int, out_rate: int) -> None:
        self._step = in_rate / out_rate
        self._passthrough = in_rate == out_rate
        self._buf = np.zeros(0, dtype=np.float32)
        self._pos = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        if self._passthrough or x.size == 0:
            return x.astype(np.float32, copy=False)
        buf = np.concatenate([self._buf, x.astype(np.float32, copy=False)])
        if buf.size < 2:
            self._buf = buf
            return np.zeros(0, dtype=np.float32)
        n = int(np.floor((buf.size - 1 - self._pos) / self._step)) + 1
        if n <= 0:
            self._buf = buf
            return np.zeros(0, dtype=np.float32)
        out = np.interp(self._pos + self._step * np.arange(n), np.arange(buf.size), buf).astype(np.float32)
        next_pos = self._pos + self._step * n
        keep_from = min(int(np.floor(next_pos)), buf.size - 1)
        self._buf = buf[keep_from:].copy()
        self._pos = next_pos - keep_from
        return out

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        self._pos = 0.0
