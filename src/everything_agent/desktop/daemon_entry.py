"""The robot daemon as the desktop app runs it: the chosen microphone and speaker, and no camera."""

from __future__ import annotations

import os
from typing import Any


def _no_camera() -> None:
    """Feeds the daemon a black test pattern instead of the computer's webcam."""
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    from reachy_mini.media import media_server

    original = media_server.GstMediaServer._build_autovideo_source

    def blank_source(self: Any) -> list[Any]:
        elements = original(self)
        blank = Gst.ElementFactory.make("videotestsrc")
        blank.set_property("pattern", "black")
        blank.set_property("is-live", True)
        return [blank, *elements[1:]]

    media_server.GstMediaServer._build_autovideo_source = blank_source


def main() -> None:
    from reachy_mini.media import media_server

    from .. import devices, envfile, paths

    saved = envfile.read_values(paths.env_path())
    for key in (devices.INPUT_SETTING, devices.OUTPUT_SETTING):
        os.environ[key] = saved.get(key, "")
    devices.use_chosen_audio(media_server)
    _no_camera()

    from reachy_mini.daemon.app.main import main as daemon_main

    daemon_main()


if __name__ == "__main__":
    main()
