"""Entry point of the packaged core that the desktop shell starts."""

import multiprocessing
import sys

PYTHON_INTERPRETER_FLAGS = ("-m", "-c", "-u", "-I", "-E", "-s", "-B", "-V", "--version")

if len(sys.argv) > 1 and sys.argv[1] in PYTHON_INTERPRETER_FLAGS:
    sys.exit(2)

from everything_agent.desktop.children import run_child_if_requested  # noqa: E402

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_child_if_requested()

    from everything_agent.desktop.__main__ import main

    sys.exit(main())
