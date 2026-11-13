# Everything Agent

[![CI](https://github.com/curious-pm/everything-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/curious-pm/everything-agent/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/curious-pm/everything-agent)](https://github.com/curious-pm/everything-agent/releases/latest)
[![License](https://img.shields.io/github/license/curious-pm/everything-agent)](LICENSE)

Hands-free voice conversation for [Reachy Mini](https://www.pollen-robotics.com/reachy-mini/).
No wake word, no button: talk, and Reachy answers out loud, moving its head as it speaks.

https://github.com/user-attachments/assets/64e124a4-e29d-4925-b330-89da745c174e

*Recorded from the app; voices regenerated with Cartesia.*

It runs on the robot, as a desktop app on Windows and macOS (with or without a robot), and in
any browser on the same network.

## Requirements

- A [Cartesia](https://play.cartesia.ai/keys) API key, for speech to text and the voice.
- An [OpenRouter](https://openrouter.ai/keys) API key, or any OpenAI-compatible provider, or a
  local [Ollama](https://ollama.com).
- Optional: an [Anthropic API key](https://platform.claude.com/settings/keys) or a Claude setup
  token (`claude setup-token`), so Reachy can pass hard questions to Claude.

You enter the keys on the setup screen the first time you open the app. They stay on the device.

## Install

**On the robot (Reachy Mini Wireless)**

```bash
pip install git+https://github.com/curious-pm/everything-agent
```

Start the app from the robot's dashboard and open <http://reachy-mini.local:8042>. The first
visit asks you to set a PIN, then for your keys.

**Desktop (Windows, macOS)**

Download the installer from [Releases](../../releases). The installers aren't code-signed yet:
on Windows choose **More info → Run anyway**, on macOS right-click the app and choose **Open**.

**From source**

```bash
git clone https://github.com/curious-pm/everything-agent && cd everything-agent
uv sync
uv run reachy-mini-daemon --mockup-sim   # in a second terminal; drop --mockup-sim with a robot
uv run python -m everything_agent
```

Then open <http://127.0.0.1:8042>. The [installation guide](docs/installation.md) has the details,
including first-time setup and updating.

## How it works

```
microphone → speech to text → language model → voice → speaker + head motion
```

Each stage streams into the next, so Reachy starts speaking after the first sentence of the
reply. A reply usually starts 2.5 to 3 seconds after you stop talking, most of it the model's
response time; a faster provider can be set under **Settings → Advanced**.

Questions that need the web or careful reasoning are handed to Claude through the `ask_claude`
tool. Claude can only search the web; it can't read files or run commands.

## Documentation

| Guide | |
| --- | --- |
| [Installation](docs/installation.md) | Robot, desktop app, or from source |
| [Using Everything Agent](docs/usage.md) | Talking, interrupting, languages, settings, Claude |
| [Configuration](docs/configuration.md) | Where settings live, and every option |
| [Troubleshooting](docs/troubleshooting.md) | Logs and common problems |
| [Architecture](docs/architecture.md) | How it works inside |
| [Development](docs/development.md) | Running from source, tests, building the installers |
| [Releasing](docs/releasing.md) | Publishing a new version |

## Development

```bash
uv sync --extra dev
uv run pytest                       # Python tests
cd ui && npm ci && npm test         # UI tests
```

See [Development](docs/development.md) for running the app from source, working on the UI and the
desktop app, and building the installers.

## Security

The web page is protected by a PIN and served over plain HTTP, so use it only on networks you
trust. On the robot, set the PIN right after installing. Report vulnerabilities privately as
described in [SECURITY.md](docs/SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Everything Agent is an independent project, not affiliated with Pollen Robotics, Hugging Face
or Anthropic.
