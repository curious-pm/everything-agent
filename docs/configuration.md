# Configuration

Most settings can be changed in the app under **Settings**. Everything, including options the app
doesn't show, lives in one `.env` file, which you can also edit by hand. Restart the app after
editing it.

## Where settings are stored

| System | Settings (`.env`) | Conversation and mute state | Logs |
| --- | --- | --- | --- |
| Windows | `%LOCALAPPDATA%\everything_agent\` | `%LOCALAPPDATA%\everything_agent\` | `%LOCALAPPDATA%\everything_agent\Logs\` |
| macOS | `~/Library/Application Support/everything_agent/` | `~/Library/Application Support/everything_agent/` | `~/Library/Logs/everything_agent/` |
| Linux and the robot | `~/.config/everything_agent/` | `~/.local/share/everything_agent/` | `~/.local/state/everything_agent/log/` |

Setting the environment variable `EVERYTHING_AGENT_HOME` to a folder puts all of these in that
folder instead (logs in `logs/` inside it).

On macOS, Linux and the robot, the `.env` file is readable only by your user account. Values in
it take precedence over environment variables with the same name. [`.env.example`](../.env.example) lists every option
with a short explanation.

## Keys

| Setting | Default | Description |
| --- | --- | --- |
| `CARTESIA_API_KEY` | | **Required.** Speech to text and Reachy's voice. |
| `LLM_API_KEY` | | **Required**, except for Ollama. Key for the AI model provider. |
| `ANTHROPIC_API_KEY` | | Optional. Lets Reachy hand hard questions to Claude, paid per question. |
| `CLAUDE_CODE_OAUTH_TOKEN` | | Optional. A token from `claude setup-token`; uses your Claude plan. |

## AI model

| Setting | Default | Description |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint, or `http://localhost:11434` for Ollama. |
| `LLM_MODEL` | `google/gemini-2.5-flash` | The model name your provider uses. |
| `LLM_PROVIDER` | guessed | `openai` (any OpenAI-compatible API) or `ollama`. Guessed from the address when empty. |
| `LLM_THINKING` | `false` | Let the model reason before answering: better at hard questions, about a second slower. |

The model is the biggest part of Reachy's reply time. A provider close to you, or a fast model,
makes replies start sooner. Each reply's timing is in the log as a `Timing:` line.

Examples:

```ini
# OpenRouter (default)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=google/gemini-2.5-flash

# Google's own endpoint
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-2.5-flash

# A local model with Ollama (no key needed)
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2
```

## How Reachy talks

| Setting | Default | Description |
| --- | --- | --- |
| `LANGUAGE_CODE` | `auto` | `auto` replies in the language you speak; `en`, `hi`, `fr`, `es` or `ja` always use that one. |
| `CARTESIA_VOICE_ID` | Greg | Reachy's voice. Easier to choose in **Settings → How Reachy talks**. |
| `SYSTEM_PROMPT` | built in | Reachy's personality. Empty uses the friendly default. |
| `CARTESIA_TTS_MODEL` | `sonic-3` | Cartesia voice model. |
| `CARTESIA_STT_MODEL` | `ink-preview` | Cartesia speech-to-text model. |

## Listening

| Setting | Default | Description |
| --- | --- | --- |
| `VAD_THRESHOLD` | `0.03` | How loud speech must be before Reachy listens (0.01 to 0.1). Raise it in a noisy room. |
| `END_OF_TURN_SILENCE_MS` | `550` | Silence that ends your turn. |
| `UNFINISHED_SILENCE_MS` | `1600` | The longer wait after "and", "um" or a trailing comma. |
| `BARGE_IN_ENABLED` | `false` | Talking over Reachy stops its reply. Works best in a quiet room. |
| `BARGE_IN_THRESHOLD` | `0.12` | How loud you must be to interrupt. |
| `STT_IDLE_TIMEOUT_S` | `60` | Seconds of quiet before the speech-to-text connection closes. It reopens when you talk. |

## Claude

| Setting | Default | Description |
| --- | --- | --- |
| `CLAUDE_ENABLED` | `true` | Hand hard questions to Claude when a key or token is set. |
| `CLAUDE_AUTH` | `api_key` | Which to use first when both are set: `api_key` or `setup_token`. The other is the backup. |
| `CLAUDE_MODEL` | `claude-haiku-5-5` | The Claude model. |
| `CLAUDE_TIMEOUT_S` | `60` | How long to wait for an answer. |

## Without the robot

| Setting | Default | Description |
| --- | --- | --- |
| `AUDIO_INPUT_DEVICE` | system default | Microphone, by the name shown in the app's Settings. |
| `AUDIO_OUTPUT_DEVICE` | system default | Speaker, by the name shown in the app's Settings. |
| `REACHY_MODE` | `auto` | Desktop app only: `auto`, `real` (wait for the robot) or `mockup` (never use the robot). |

## Web page

| Setting | Default | Description |
| --- | --- | --- |
| `WEB_PORT` | `8042` | Port of the web page. |
| `WEB_ALLOWED_HOSTS` | | Extra host names the page answers to, comma-separated. IP addresses, `localhost` and `<hostname>.local` always work. |
| `WEB_PIN_HASH` | | Set by the page when someone chooses a PIN. Only a hash is stored. Delete this line to reset a forgotten PIN. |
| `WEB_HOST` | see description | Address the page listens on. `0.0.0.0` (the whole network) by default; the desktop app uses `127.0.0.1` (this computer only) until a PIN is set. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

## Fine-tuning

Rarely needed; the defaults suit most rooms.

| Setting | Default | Description |
| --- | --- | --- |
| `VAD_MIN_SPEECH_MS` | `300` | How long sound must last before it counts as speech. |
| `VAD_PREROLL_MS` | `600` | Audio kept from just before speech starts, so the first word isn't clipped. |
| `ECHO_TAIL_MS` | `500` | How long Reachy ignores the microphone after it stops speaking. |
| `PLAYBACK_PREBUFFER_MS` | `150` | Audio buffered before playback starts. |
