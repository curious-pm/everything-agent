"""How the core starts its child processes, from source or from a packaged build."""

from __future__ import annotations

import runpy
import subprocess
import sys

CHILD_FLAG = "--child"
APP_MODULE = "everything_agent"
DAEMON_ENTRY = "everything_agent.desktop.daemon_entry"
DEVICES_MODULE = "everything_agent.devices"
_ALLOWED = (APP_MODULE, DAEMON_ENTRY, DEVICES_MODULE)
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def command(module: str, *args: str) -> list[str]:
    if frozen():
        return [sys.executable, CHILD_FLAG, module, *args]
    return [sys.executable, "-m", module, *args]


def _set_up_bundled_gstreamer() -> None:
    try:
        import gstreamer_libs

        gstreamer_libs.setup_python_environment()
    except ImportError:
        pass


def run_child_if_requested() -> None:
    """In a packaged build, run the requested child module and exit; otherwise do nothing."""
    if len(sys.argv) < 3 or sys.argv[1] != CHILD_FLAG:
        return
    module = sys.argv[2]
    if module not in _ALLOWED:
        sys.exit(f"unknown child {module!r}")
    _set_up_bundled_gstreamer()
    sys.argv = [module, *sys.argv[3:]]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
    sys.exit(0)
