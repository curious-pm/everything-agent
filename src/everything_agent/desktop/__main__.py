"""``python -m everything_agent.desktop``: the desktop app's core, started by the Tauri shell."""

from __future__ import annotations

import argparse
import sys

from .. import envfile, logs, paths
from . import core, os_events
from .supervisor import MODES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="everything-agent-desktop")
    parser.add_argument(
        "--mode", choices=MODES,
        help="auto (default) uses the robot when it's plugged in, else this computer's microphone and speaker",
    )
    parser.add_argument("--headless", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    os_events.prepare()
    logs.configure("desktop")
    mode = args.mode or (envfile.read_values(paths.env_path()).get("REACHY_MODE") or "auto").strip().lower()
    if mode not in MODES:
        mode = "auto"

    return core.run(mode)


if __name__ == "__main__":
    sys.exit(main())
