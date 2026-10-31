"""Reachy Mini's microphone, speaker and head, through the Reachy Mini SDK."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_RATE = 16000
NEUTRAL_ANTENNAS = (-0.1745, 0.1745)
_HEAD_Z_FLOOR = -0.165
_EASE_S = 0.6


class Robot:
    def __init__(self, mini: Any) -> None:
        self.mini = mini
        media = mini.media
        self.media_lock = threading.Lock()
        self.asleep = threading.Event()
        self.input_rate = int(media.get_input_audio_samplerate() or DEFAULT_RATE)
        self.out = _Output(self, int(media.get_output_audio_samplerate() or DEFAULT_RATE))

    def start(self) -> None:
        for name in ("enable_motors", "enable_wobbling"):
            try:
                getattr(self.mini, name)()
            except Exception as exc:
                logger.warning("%s failed: %s", name, exc)
        self.mini.media.start_recording()

    def stop(self) -> None:
        try:
            self.mini.media.stop_recording()
        except Exception:
            logger.debug("Stopping the recording failed", exc_info=True)

    def read_mic(self) -> np.ndarray | None:
        return self.mini.media.get_audio_sample()

    def restart_recording(self) -> None:
        with self.media_lock:
            self.mini.media.stop_recording()
            self.mini.media.start_recording()

    def go_to_sleep(self) -> None:
        self.asleep.set()
        try:
            self.mini.disable_wobbling()
        except Exception:
            logger.debug("disable_wobbling failed", exc_info=True)
        self.mini.goto_sleep()

    def wake_up(self) -> None:
        try:
            self.mini.enable_motors()
        except Exception:
            logger.debug("enable_motors failed", exc_info=True)
        self.mini.wake_up()
        try:
            self.mini.enable_wobbling()
        except Exception:
            logger.debug("enable_wobbling failed", exc_info=True)
        self.asleep.clear()

    def breathe(self, stop: threading.Event) -> None:
        """Gentle idle motion until ``stop`` is set; speech wobble is added on top by the SDK."""
        from reachy_mini.utils import create_head_pose
        from reachy_mini.utils.interpolation import linear_pose_interpolation

        antennas = np.array(NEUTRAL_ANTENNAS)
        start: Any = None
        t0 = time.monotonic()
        was_asleep = True
        failures = 0
        while not stop.is_set():
            if self.asleep.is_set():
                was_asleep = True
                time.sleep(0.1)
                continue
            if was_asleep:
                was_asleep = False
                t0 = time.monotonic()
                try:
                    start = self.mini.get_current_head_pose()
                except Exception:
                    start = None
            t = time.monotonic() - t0
            head = create_head_pose(
                yaw=3.0 * np.sin(2 * np.pi * 0.08 * t), pitch=2.0 * np.sin(2 * np.pi * 0.11 * t), degrees=True,
            )
            head[2, 3] += 0.005 * np.sin(2 * np.pi * 0.1 * t)
            if start is not None and t < _EASE_S:
                head = linear_pose_interpolation(start, head, t / _EASE_S)
            head[2, 3] = max(head[2, 3], _HEAD_Z_FLOOR)
            try:
                self.mini.set_target(head=head, antennas=antennas, body_yaw=0.0)
            except Exception as exc:
                failures += 1
                if failures == 1:
                    logger.warning("Head motion failed, retrying quietly: %s", exc)
                time.sleep(1.0)
                continue
            if failures:
                logger.info("Head motion is back after %d failed tries", failures)
                failures = 0
            time.sleep(0.02)


class _Output:
    def __init__(self, robot: Robot, sample_rate: int) -> None:
        self._robot = robot
        self.sample_rate = sample_rate

    def begin_playback(self) -> None:
        self._robot.mini.media.start_playing()

    def push(self, chunk: np.ndarray) -> None:
        self._robot.mini.media.push_audio_sample(chunk)

    def clear_playback(self) -> None:
        audio = getattr(self._robot.mini.media, "audio", None)
        try:
            if audio is not None:
                audio.clear_player()
        except Exception as exc:
            logger.warning("Couldn't drop queued speech: %s", exc)

    def end_playback(self) -> None:
        with self._robot.media_lock:
            self._robot.mini.media.stop_playing()
            self._robot.mini.media.start_recording()
