# Architecture

Everything Agent is a Python app with a React UI, plus a Tauri shell for the desktop. The same
Python app and UI run on the robot, on a laptop and behind the desktop window.

```
                 ┌──────────────────────────── Python app ────────────────────────────┐
 microphone ──▶  │ loudness check ─▶ Cartesia speech to text ─▶ language model ─┐     │
                 │                                                               │     │
 speaker    ◀──  │ speaker pacing ◀─ Cartesia voice ◀─ sentence splitter ◀───────┘     │
                 │        │                                                            │
                 │        └─▶ events ─▶ web server (FastAPI) ─▶ React UI (browser/window)
                 └────────────────────────────────────────────────────────────────────┘
                          ▲ microphone, speaker, head motion
                 Reachy Mini daemon (robot or simulator)
```

## The conversation loop

`src/everything_agent/conversation/engine.py` runs the loop. Every stage streams into the next,
which is what keeps replies fast.

1. **Listening.** A reader thread pulls microphone frames from the Reachy Mini SDK. A local
   loudness check decides when someone is speaking; only then does the app open a Cartesia
   speech-to-text connection. The audio from just before (600 ms) is kept and sent first, so the
   first word isn't clipped. After a minute of quiet the connection closes, so an idle Reachy
   costs nothing.
2. **End of turn.** Cartesia has no end-of-speech detection, so the app decides: 550 ms of silence,
   or 1.6 s after a word like "and" or "um" (`conversation/turn_taking.py`). It then asks Cartesia
   to finalize, and starts the reply once every word is in.
3. **Thinking.** The conversation so far, with the current date and time, streams to the language
   model (`voice/llm.py`). The model's connection is kept open between turns and refreshed while
   you talk, which saves several network round trips per reply.
4. **Speaking.** The reply is split into sentences as it arrives (`conversation/sentences.py`).
   Each finished sentence goes straight to Cartesia's voice over one long-lived socket
   (`voice/tts.py`), so Reachy starts speaking after the first sentence. The speaker thread
   (`audio/speaker.py`) paces playback and tells the UI which sentence is being heard. The SDK
   moves Reachy's head with the voice.
5. **Interruptions.** While Reachy speaks, the microphone mostly hears Reachy, so that audio isn't
   transcribed. With interrupting on (`audio/barge_in.py`), loud sound first turns Reachy's voice
   down; its own echo drops with it, a real voice doesn't, so if the sound lasts, the reply stops.

If you carry on talking before Reachy has said anything, the reply is withdrawn and your words
are answered together. That's why the end-of-turn silence can be short.

## Tools

The model is offered tools (`src/everything_agent/tools/`). A tool either returns a result that
the model then answers with, or works in the background and speaks for itself.

The first tool is `ask_claude`. It hands hard questions to Claude, either through the Claude API
(with an Anthropic API key) or through Claude Code's agent via the Agent SDK (with a setup
token). Claude gets only web search, and its environment has the app's keys removed. Its answer
streams into the conversation sentence by sentence.

## The web server

`src/everything_agent/server/` serves the built UI and its API on port 8042.

| Path | What it does |
| --- | --- |
| `/api/auth`, `/api/auth/login`, `/api/auth/pin`, `/api/auth/logout` | Sign in with the PIN, set or change it |
| `/api/events` (WebSocket) | Live state, sound levels and conversation events for the UI |
| `/api/status`, `/api/info` | Current state, version and network address |
| `/api/say`, `/api/mute`, `/api/sleep`, `/api/wake` | Type to Reachy, mute, sleep and wake |
| `/api/conversation` | Read or clear the conversation |
| `/api/settings`, `/api/voices`, `/api/devices` | Read and save settings, browse voices, choose audio devices |
| `/api/checks`, `/api/logs` | The "check that everything works" list and recent logs |
| `/robot/...` | Reachy's 3D model, from the installed SDK |

Every API call needs a signed-in session (PIN) or the desktop window's token. Requests under
unknown host names or from other websites are refused. See [Security](SECURITY.md).

## The desktop app

The desktop app has two parts:

- **The shell** (`desktop/src-tauri/`, Rust and Tauri) opens the window, the tray icon and the mute
  shortcut. It starts the core and talks to it in JSON lines over stdin and stdout.
- **The core** (`src/everything_agent/desktop/`, Python, packaged with PyInstaller) starts the
  Reachy Mini daemon and the conversation app as child processes, and restarts them when
  something fails, when the robot is plugged in or unplugged, or when the computer wakes from
  sleep.

Closing the shell closes the core's stdin, which stops the app and puts the robot to sleep. On
Windows the core runs in a job object, so nothing outlives the shell.

## What's stored on the device

| File | Contents |
| --- | --- |
| `.env` | Settings and keys, and a hash of the web page PIN |
| `conversation.json` | The last 60 messages |
| `mute.json` | Whether the microphone and speaker are muted |
| `app.log`, `desktop.log`, `daemon.log` | Logs, rotated at 5 MB |

See [Configuration](configuration.md#where-settings-are-stored) for where these are.

## Project layout

```
src/everything_agent/
  main.py            Reachy Mini app entry point (what the robot's launcher starts)
  __main__.py        python -m everything_agent: run against a daemon that's already running
  runtime.py         keeps the web page up; starts and restarts the conversation
  conversation/      the loop: listening, turn-taking, replies, history
  audio/             microphone reader, speaker playback, interruption detection
  voice/             Cartesia speech to text and voice, the language model client
  tools/             what the model can do besides talking (ask_claude)
  server/            web API, PIN sign-in, request guard, the setup checks
  desktop/           the desktop app's core
  robot.py           microphone, speaker, idle head motion, sleep and wake, through the SDK
  web/               the built UI (committed, so installs from git work without Node)
ui/                  the React UI, the same on web and desktop
desktop/             the Tauri shell
packaging/           PyInstaller recipe for the core, and the third-party license collector
scripts/             desktop build scripts
tests/               Python tests, with a pretend robot and pretend cloud services
```
