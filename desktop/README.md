# Desktop shell

Tauri 2 app around the Python core (`python -m everything_agent.desktop`): the window with the
UI from `../ui`, a tray icon, start at login, the Ctrl+Alt+M (Cmd+Alt+M) mute shortcut, and
putting the robot to sleep at log-off and shutdown.

```bash
npm install
npx tauri dev            # debug shell; runs the core from the repository's .venv
```

`../scripts/build_desktop.*` builds the release installer with the packaged core inside
(`src-tauri/core/`, bundled through `tauri.core.conf.json`). `EVERYTHING_AGENT_CORE_EXE` points the shell
at another core, e.g. a Python interpreter.

The core prints JSON lines (`hello`, `state`, `reply`) and reads JSON-line commands (`restart`,
`restart_all`, `mute`, `get_mute`). Closing its stdin stops Reachy and puts the robot to sleep.
On Windows the core runs in a job object, so nothing outlives the shell.
