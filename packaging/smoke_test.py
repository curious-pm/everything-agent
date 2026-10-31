"""Usage: python packaging/smoke_test.py <path to the packaged "Everything Agent Core" executable>"""

import json
import os
import subprocess
import sys
import tempfile
import time

import httpx

DAEMON_API = "http://127.0.0.1:8000/api/daemon"
_INHERITED_PYTHON_ENV = ("PYTHON", "__PYVENV", "VIRTUAL_ENV", "GST_", "GI_")


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith(_INHERITED_PYTHON_ENV)}


def _last_lines(log, count: int) -> list[str]:
    log.seek(0)
    return log.read().strip().splitlines()[-count:]


def robot_service_starts(exe: str) -> str:
    log = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [exe, "--child", "everything_agent.desktop.daemon_entry", "--mockup-sim", "--wake-up-on-start"],
        stdout=log, stderr=subprocess.STDOUT, env=clean_env(),
    )
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return "exited: " + " ".join(_last_lines(log, 3))
            try:
                if httpx.get(f"{DAEMON_API}/status", timeout=2).json().get("state") == "running":
                    return ""
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1)
        return "didn't report running within 2 minutes; last log lines: " + " | ".join(_last_lines(log, 6))
    finally:
        try:
            httpx.post(f"{DAEMON_API}/stop", params={"goto_sleep": "false"}, timeout=10)
        except httpx.HTTPError:
            pass
        proc.terminate()
        proc.wait(20)
        log.close()


def devices_listed(exe: str) -> str:
    result = subprocess.run(
        [exe, "--child", "everything_agent.devices"], capture_output=True, text=True, timeout=120, env=clean_env(),
    )
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    if result.returncode != 0 or not lines:
        return " ".join(result.stderr.strip().splitlines()[-3:])
    found = json.loads(lines[-1])
    print(f"     {len(found['inputs'])} microphones, {len(found['outputs'])} speakers")
    return ""


def main() -> int:
    exe = os.path.abspath(sys.argv[1])
    failures = 0
    for name, check in (("robot service", robot_service_starts), ("device listing", devices_listed)):
        problem = check(exe)
        print(f"{'FAIL' if problem else 'ok  '} {name}{': ' + problem if problem else ''}")
        failures += bool(problem)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
