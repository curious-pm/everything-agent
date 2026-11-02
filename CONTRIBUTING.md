# Contributing

Thanks for helping. A few things keep the project easy to work on:

- **One feature per change**, with tests. Python tests live in `tests/` (`pytest`), UI tests
  next to the UI (`cd ui && npm test`). The conversation loop has a test harness with a
  pretend robot and pretend cloud services (`tests/test_conversation.py`); use it for
  anything that touches listening or replying.
- **No comments in the code.** Say it with names: a well-named constant or function instead
  of a comment. Anything a reader really needs to know that the code can't say goes in the
  notes below. Docstrings are one line, and only where the name isn't enough.
- **Latency is a feature.** Anything on the path from "user stops talking" to "Reachy starts
  speaking" should stream and should not wait on anything it doesn't need. The app logs a
  `Timing:` line for every reply; check it before and after.
- **UI wording talks to the user, not about the system**: "I can't hear you right now",
  not "Microphone input disabled".
- **Rebuild the UI** (`cd ui && npm run build`) when you change it; the built files in
  `src/everything_agent/web/` are committed so installs from git work without Node.
- **Adding a tool**: subclass `Tool` in `src/everything_agent/tools/` and list it in
  `tools.available()`. A tool returns a result the model then answers with, or, with
  `follow_up = False`, works in the background and speaks through `ctx.announce`.
- **Checks run on every pull request** (`.github/workflows/ci.yml`): Python tests and ruff,
  UI type check, lint and tests, and clippy for the desktop shell. Run them locally first.
- **Releasing**: bump the version in `pyproject.toml`, `src/everything_agent/__init__.py`,
  `desktop/src-tauri/tauri.conf.json` and `desktop/src-tauri/Cargo.toml`, then push a tag
  such as `v0.2.0`. The release workflow builds the Windows and macOS installers and opens
  a draft release with them attached; check it and publish.

## Notes

Things that aren't obvious from the code, and cost time to find out.

### Conversation loop

- Cartesia speech-to-text has no end-of-speech detection. The app decides the user has
  finished (550 ms of silence, 1.6 s after "and", "um" or a trailing comma) and sends
  `finalize`, which comes back as `flush_done` once every word is in.
- Speech-to-text only connects once the local loudness check hears someone; the audio just
  before is kept (pre-roll) so the first word isn't clipped. It disconnects after a minute
  of quiet.
- While Reachy talks, the microphone mostly hears Reachy, so that audio isn't transcribed.
  The last second of it is kept: after an interruption it holds the start of the user's words.
- A reply is withdrawn if the user keeps talking before Reachy has said anything; the words
  are answered together with what follows. That's why the end-of-turn silence can be short.
- Barge-in first ducks the speaker. Reachy's echo drops with it, a real voice doesn't; if the
  loudness lasts through the duck, the reply stops.
- The model's connection is kept open between turns and refreshed while the user talks: a
  fresh TLS connection costs several round trips per reply.
- Every request carries the current date and time; the model has no clock and guesses.

### Model providers

- Reasoning is turned off unless `LLM_THINKING` is set (it costs about a second per turn):
  OpenRouter with `reasoning.enabled=false`, Gemini with `reasoning_effort=none`. Models that
  refuse that are remembered and allowed to think.
- Ollama uses its native `/api/chat`, because its OpenAI-compatible API can't turn thinking off.
- OpenRouter lists its models to anyone, so the key check uses `/key`, not `/models`.

### Claude tool

- An Anthropic API key goes straight to the Messages API with the basic `web_search` tool;
  dynamic filtering would add a code-execution step and more delay.
- A setup token can't call the Messages API, so it runs Claude Code's agent through
  `claude-agent-sdk`, whose wheel bundles the Claude Code binary. The agent is started when the
  conversation starts and warmed with one tiny question: starting it takes a few seconds and
  its first answer is slower.
- Each question gets a fresh agent session, so earlier questions don't slow later ones.
- The agent gets only `WebSearch`, no settings files or MCP servers, and an environment with
  this app's keys blanked. `ANTHROPIC_API_KEY` is blanked too, or it would win over the token.
- The answer streams into `Conversation.announce_stream`, which waits for the first words
  before taking the turn, so the user can keep talking while Claude works.

### Robot and audio

- Neutral antennas sit about 10° apart: at exactly zero they shake from gear backlash.
- Head height is clamped at −0.165 m; below that the SDK's inverse kinematics can get stuck.
- Motor torque must be on or movement targets silently do nothing, and `wake_up` doesn't turn
  it back on.
- The SDK records and plays through one pipeline. Stopping playback also stops the microphone,
  so recording is restarted straight away, and restarts never overlap a microphone read.
- Speaker pushes are paced to stay at most 0.4 s ahead; gain changes are ramped across a chunk
  to avoid clicks.
- Without the robot, the SDK pairs echo cancelling only with the default microphone, so a
  chosen microphone is swapped into the default slot to keep it.
- On Windows, audio devices are listed from the registry: GStreamer's device monitor comes back
  empty while the devices are in use. Loopback "microphones" that record the speakers are
  filtered out, and the instance number Windows adds ("3- USB Audio") is ignored when comparing.

### Desktop app

- The Tauri shell starts the Python core and talks to it in JSON lines over stdin and stdout.
  Commands: `restart`, `restart_all`, `mute`, `get_mute`, `quit`. Closing the core's stdin
  stops it, and the robot goes to sleep first.
- The shell hands the core its API token in `EVERYTHING_AGENT_CORE_TOKEN` (never on the command line)
  and the page gets it in `window.__EVERYTHING_AGENT__` before any page code runs.
- On Windows the core runs in a kill-on-close job object, so nothing outlives the shell. On
  log-off a hidden top-level window catches `WM_QUERYENDSESSION` (message-only windows don't
  get it) and keeps the core alive long enough to put the robot to sleep.
- The core starts the robot daemon and the app. They always restart together, because the
  daemon's media only reaches an app started with it. With a real robot the daemon starts with
  `--no-autostart`: its autostart would also launch Reachy Mini Control's saved startup app,
  which fights ours for the microphone. Without a robot, the daemon gets a black test pattern
  instead of the webcam.
- The app exits with code 75 to ask to be restarted (e.g. a new microphone was chosen).
- WebView2 keeps rendering a minimized page, so the shell sends a `everything-agent-visibility` event and
  the 3D view stops redrawing.
- The uninstaller doesn't know about the start-at-login entry, so `windows/hooks.nsh` removes it.

### Packaging

- A packaged build is one executable, so the core starts its children as
  `<exe> --child <module>`; only modules in `children._ALLOWED` run that way.
- The GStreamer wheels find their DLLs, plugins and the gi bindings relative to their own
  folders, so the spec ships them as plain files. PyInstaller then doesn't see what gi imports,
  hence the hidden imports (`optparse`, `pkgutil`, `inspect`, `selectors`, `typing_extensions`),
  and gi is excluded so PyInstaller's own hooks don't ship a second copy.
- `packaging/smoke_test.py` runs the bundle with a clean environment (no `PYTHON*`, `GST_*` or
  `GI_*` from your venv) and logs the daemon to a file, because an unread pipe fills up and
  blocks it.
- The installers leave out GStreamer's GPL and patent-restricted plugins (x264, x265, the FFmpeg
  and OpenH264 codecs), so the bundle stays LGPL-compatible. Reachy's software doesn't need them.
- `packaging/third_party_licenses.py` writes `THIRD_PARTY_LICENSES.txt` into every installer, from
  the installed Python packages, `ui/package-lock.json` and `cargo metadata`. The web build writes
  its own `THIRD_PARTY_LICENSES.md` for the JavaScript it bundles.
- `uv.lock` pins the Python packages for the installers. The lock is required to work on Python
  3.12 for Windows and macOS (`[tool.uv]` in `pyproject.toml`): newer GStreamer releases dropped
  3.12 wheels. Run `uv lock` after changing dependencies.

### Web page

- The page refuses requests under unknown host names (DNS rebinding) and state-changing
  requests from other sites. Add names in `WEB_ALLOWED_HOSTS` if you reach the robot by
  another name.
- The desktop window can't put headers on a WebSocket, so it sends its token as the first
  message.
- `ui/scripts/copy-robot.mjs` copies the robot model from the installed `reachy_mini` package,
  so the 3D view matches the SDK the app ships with.
