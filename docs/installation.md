# Installation

Everything Agent runs in three places. Pick the one that fits:

| Where | Best for | Microphone and speaker |
| --- | --- | --- |
| [On the robot](#on-the-robot) | Reachy Mini Wireless, running on its own | The robot's, with hardware echo cancelling |
| [Desktop app](#desktop-app-windows-and-macos) | A Windows or Mac computer, with or without a robot | The robot's when it's plugged in over USB, otherwise the computer's |
| [From source](#from-source) | Development, or Linux | Same as the desktop app |

Whichever you choose, you can also open the app in any browser on the same network.

## What you need

Two API keys, entered on the setup screen the first time you open the app:

| What for | Service | Get a key |
| --- | --- | --- |
| Hearing and speaking | [Cartesia](https://cartesia.ai) | [play.cartesia.ai/keys](https://play.cartesia.ai/keys) |
| Thinking | [OpenRouter](https://openrouter.ai), any OpenAI-compatible provider, or a local [Ollama](https://ollama.com) (no key needed) | [openrouter.ai/keys](https://openrouter.ai/keys) |

Optional, for questions that need the web or careful reasoning: an
[Anthropic API key](https://platform.claude.com/settings/keys) or a Claude setup token. See
[Hard questions go to Claude](usage.md#hard-questions-go-to-claude).

Keys are stored only on the device the app runs on.

## On the robot

For Reachy Mini Wireless, which runs the app on its own Raspberry Pi.

1. Open a terminal on the robot and install the app:

   ```bash
   pip install git+https://github.com/curious-pm/everything-agent@v1.0.0
   ```

2. Start **Everything Agent** from the robot's dashboard.
3. On your phone or laptop, open <http://reachy-mini.local:8042>.
4. Choose a PIN (6 characters or more), then paste your keys.

Set the PIN yourself right after installing: the first visitor to the page chooses it.

## Desktop app (Windows and macOS)

| System | Installer |
| --- | --- |
| Windows 10 or 11 (64-bit) | `Everything.Agent_<version>_x64-setup.exe` |
| macOS 13 or later, Apple silicon | `Everything.Agent_<version>_aarch64.dmg` |

1. Download the installer from the [latest release](https://github.com/curious-pm/everything-agent/releases/latest).
2. Install and open it. The installers aren't code-signed yet:
   - **Windows:** if SmartScreen says "Windows protected your PC", choose **More info**, then **Run anyway**.
   - **macOS:** the first time, right-click the app and choose **Open**.
3. Follow the setup screen: choose a microphone and speaker (used when no robot is plugged in),
   paste your keys, and choose whether Reachy starts when you log in.

The app starts the Reachy Mini software for you. With the robot plugged in over USB it uses the
robot; unplug it and the app switches to the computer's microphone and speaker. You don't need
Reachy Mini Control running, and it should be closed: only one app can use the robot at a time.

To open the app from your phone, set a web page PIN under **Settings → Advanced**, then restart
the app. Until a PIN is set, the desktop app only answers on the computer it runs on.

## From source

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or later (uv installs it if missing).

```bash
git clone https://github.com/curious-pm/everything-agent
cd everything-agent
uv sync
```

Start the Reachy Mini software in one terminal. Without a robot, add `--mockup-sim` to use the
computer's microphone and speaker:

```bash
uv run reachy-mini-daemon --mockup-sim
```

Start the app in a second terminal, then open <http://127.0.0.1:8042>:

```bash
uv run python -m everything_agent
```

The first visit asks you to choose a PIN, then for your keys.

To work on the app itself, see [Development](development.md).

## Updating

- **Robot:** run the `pip install` command again with the new version, then restart the app
  from the dashboard.
- **Desktop app:** download and run the new installer. Your settings and conversation are kept.
- **From source:** `git pull`, then `uv sync`.

## Uninstalling

- **Windows:** Settings → Apps → Everything Agent → Uninstall.
- **macOS:** drag Everything Agent from Applications to the Bin.
- **Robot:** `pip uninstall everything_agent`.

Your settings and conversation stay in the app's folder after uninstalling; delete it to remove
them too. See [Configuration](configuration.md#where-settings-are-stored) for where it is.
