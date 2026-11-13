# Development

## Prerequisites

| For | You need |
| --- | --- |
| The Python app | [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 if needed) |
| The UI | [Node.js](https://nodejs.org) 22 |
| The desktop app | [Rust](https://rustup.rs) (stable) and the [Tauri prerequisites](https://tauri.app/start/prerequisites/) for your system |

## Set up

```bash
git clone https://github.com/curious-pm/everything-agent
cd everything-agent
uv sync --extra dev
cd ui && npm ci && cd ..
```

## Run it

In one terminal, start the Reachy Mini software. `--mockup-sim` uses the computer's microphone and
speaker instead of a robot:

```bash
uv run reachy-mini-daemon --mockup-sim
```

In a second terminal, start the app and open <http://127.0.0.1:8042>:

```bash
uv run python -m everything_agent
```

### Working on the UI

```bash
cd ui
npm run dev
```

This serves the UI with hot reload on <http://localhost:5173> and forwards `/api` to the app on
port 8042 (set `REACHY_APP_SERVER` to use another address). Before starting, it copies Reachy's 3D
model from the installed `reachy_mini` package; if it can't find it, set `REACHY_PYTHON` to the
Python that has it, for example `.venv/Scripts/python.exe`.

The Python app serves the built UI from `src/everything_agent/web/`, which is committed so that
`pip install` from git works without Node. After changing the UI, rebuild it and commit the result:

```bash
cd ui
npm run build
```

### Working on the desktop app

```bash
cd desktop
npm ci
npx tauri dev
```

The debug shell runs the core from the repository's `.venv` and the UI from the dev server.

## Tests and checks

```bash
uv run pytest                                  # Python tests
uvx ruff check --select F,E9 src tests packaging
cd ui && npx tsc -b && npm run lint && npm test   # UI type check, lint and tests
cd desktop/src-tauri && cargo clippy --all-targets -- -D warnings
```

GitHub Actions runs all of these on every push to `main` and on every pull request
(`.github/workflows/ci.yml`).

The conversation loop has a test harness with a pretend robot and pretend cloud services
(`tests/test_conversation.py`). Use it for anything that touches listening or replying: it runs
the real loop with scripted speech, model replies and voice.

## Building the desktop installers

```bash
uv sync --extra package
scripts/build_desktop.ps1    # Windows: NSIS installer
scripts/build_desktop.sh     # macOS: .app and .dmg
```

The script builds the UI, packs the Python core with PyInstaller into `desktop/src-tauri/core/`,
collects third-party licenses, runs a smoke test on the packaged core, and builds the installer.
See [Releasing](releasing.md) for publishing a release.

## Conventions

- **Latency is a feature.** Anything on the path from "you stop talking" to "Reachy starts
  speaking" should stream and should not wait on anything it doesn't need. Every reply logs a
  `Timing:` line; compare it before and after a change.
- **Names instead of comments.** Prefer a well-named constant or function over a comment.
  Docstrings are one line, and only where the name isn't enough.
- **UI wording talks to the user**, not about the system: "I can't hear you right now", not
  "Microphone input disabled".
- **One change per pull request**, with tests.
- **Commit messages** are a short imperative summary ("Show a demo video at the top of the
  README"), with a body explaining why when it isn't obvious.

## Adding a tool

Tools are how Reachy does things besides talking.

1. Subclass `Tool` in `src/everything_agent/tools/` and set `name`, `description` (what the model
   reads to decide when to use it) and `parameters` (a JSON schema).
2. Implement `run(args, ctx)`:
   - Return a string, and the model answers with it, or
   - Set `follow_up = False`, start the work with `ctx.spawn`, and speak the result with
     `ctx.announce(text)` or, sentence by sentence, `ctx.announce_stream(chunks)`.
3. List it in `tools.available()`, with whatever setting switches it on.
4. Add tests. `tests/test_conversation.py` shows a background tool answering out loud, and
   `tests/test_claude.py` tests `ask_claude` on its own.

## Things that aren't obvious

- **Turn-taking.** Cartesia speech to text has no end-of-speech detection; the app sends
  `finalize` after its own silence timer and waits for `flush_done`.
- **Motors.** Torque must be on or movement targets silently do nothing, and `wake_up` doesn't
  turn it back on. Head height is clamped at -0.165 m; below that the SDK's inverse kinematics can
  get stuck. Neutral antennas sit about 10° apart, because at exactly zero they shake.
- **Audio.** The SDK records and plays through one pipeline: stopping playback also stops the
  microphone, so recording is restarted straight away.
- **Model providers.** Reasoning is turned off unless `LLM_THINKING` is set (OpenRouter
  `reasoning.enabled=false`, Gemini `reasoning_effort=none`); models that refuse are remembered.
  Ollama uses its native `/api/chat`, because its OpenAI-compatible API can't turn thinking off.
- **Desktop.** With a robot, the core starts the daemon with `--no-autostart`, because the
  daemon's autostart would launch Reachy Mini Control's startup app, which competes for the
  microphone. The app exits with code 75 to ask the core to restart it.
- **Windows audio.** Devices are listed from the registry, because GStreamer's device monitor
  comes back empty while devices are in use.
- **Packaging.** The packaged core is a single executable, so it starts its children as
  `<exe> --child <module>`; only modules listed in `desktop/children.py` can run that way. The
  installers leave out GStreamer's GPL and patent-restricted plugins, so the bundle stays
  LGPL-compatible.
