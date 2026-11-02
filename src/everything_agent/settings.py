"""Settings, read from the user's ``.env`` with the process environment as a fallback."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from . import envfile, paths

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are Reachy Mini, a small, friendly desk robot having a spoken conversation. Be warm, "
    "curious and natural. Keep replies to one or two short sentences, unless the user asks for "
    "something longer, like a story or an explanation; then tell it in short, easy sentences."
)
DEFAULT_LLM_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LLM_MODEL = "google/gemini-2.5-flash"
DEFAULT_VOICE_ID = "a0e99841-438c-4a64-b679-ae501e7d6091"
DEFAULT_WEB_PORT = 8042
DEFAULT_CLAUDE_MODEL = "claude-haiku-5-5"
API_KEY = "api_key"
SETUP_TOKEN = "setup_token"

AUTO_LANGUAGE = "auto"
LANGUAGES = {"en": "English", "hi": "Hindi", "fr": "French", "es": "Spanish", "ja": "Japanese"}

_SPOKEN_RULES = (
    " Everything you write is spoken aloud by a voice, so write only plain spoken sentences: no "
    "emoji, markdown, lists or headings, and spell out symbols."
)
_MULTILINGUAL_INSTRUCTION = (
    " Reply in the language of the user's latest message and switch whenever they do. If they mix "
    "languages, such as Hindi with English words, reply in the same mix. Write each language in its "
    "own script (Hindi in Devanagari, not Latin letters) so your voice pronounces it correctly. "
    "Never ask the user to speak English; if you didn't catch something, ask them to repeat it."
)
_ONE_LANGUAGE_INSTRUCTION = " Always reply in {language}, even if the user's words are unclear."

RESTART_EXIT_CODE = 75
DESKTOP_ENV = "EVERYTHING_AGENT_DESKTOP"
DESKTOP_TOKEN_ENV = "EVERYTHING_AGENT_DESKTOP_TOKEN"


@dataclass(frozen=True)
class Field:
    """One setting the app's pages may show and change."""

    key: str
    label: str
    kind: Literal["secret", "text", "textarea", "bool", "choice"]
    hint: str = ""
    default: str = ""
    required: bool = False


FIELDS: tuple[Field, ...] = (
    Field("CARTESIA_API_KEY", "Cartesia API key", "secret",
          "Lets Reachy hear and speak. Get one at play.cartesia.ai.", required=True),
    Field("LLM_API_KEY", "AI model API key", "secret",
          "For OpenRouter or any OpenAI-compatible provider. Not needed for a local Ollama model.",
          required=True),
    Field("LLM_BASE_URL", "AI model address", "text",
          "Any OpenAI-compatible endpoint. For Ollama use http://localhost:11434.", DEFAULT_LLM_BASE_URL),
    Field("LLM_MODEL", "AI model", "text", "The model name your provider uses.", DEFAULT_LLM_MODEL),
    Field("SYSTEM_PROMPT", "Personality", "textarea",
          "How Reachy is told to behave. Leave empty for the friendly default.", ""),
    Field("LANGUAGE_CODE", "Language", "choice", "", AUTO_LANGUAGE),
    Field("CARTESIA_VOICE_ID", "Voice", "text", "", DEFAULT_VOICE_ID),
    Field("VAD_THRESHOLD", "Microphone sensitivity", "choice",
          "How loud speech must be before Reachy listens. Higher suits a noisy room.", "0.03"),
    Field("BARGE_IN_ENABLED", "Stop talking when I interrupt", "bool",
          "Works best in a quiet room; Reachy can mistake its own voice for yours.", "false"),
    Field("CLAUDE_ENABLED", "Ask Claude for hard questions", "bool",
          "Reachy hands questions that need the web or careful thinking to Claude. "
          "Add an Anthropic API key or a Claude setup token.", "true"),
    Field("ANTHROPIC_API_KEY", "Anthropic API key", "secret",
          "Fastest. Paid per question; get one at platform.claude.com."),
    Field("CLAUDE_CODE_OAUTH_TOKEN", "Claude setup token", "secret",
          "Uses your Claude plan. On any computer with Claude Code, run claude setup-token and paste what it prints."),
    Field("CLAUDE_AUTH", "Ask Claude with", "choice",
          "If it fails, Reachy tries the other one.", API_KEY),
)
FIELDS_BY_KEY = {f.key: f for f in FIELDS}


def _bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _number(values: dict[str, str], key: str, default: float, cast: type = float):
    raw = (values.get(key) or "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        logger.warning("%s=%r isn't a number; using %s", key, raw, default)
        return default


def desktop_mode() -> bool:
    """True when started by the desktop app rather than Reachy's own app launcher."""
    return _bool(os.environ.get(DESKTOP_ENV), False)


def system_prompt(base: str, language: str) -> str:
    base = (base or DEFAULT_SYSTEM_PROMPT).strip() + _SPOKEN_RULES
    if language == AUTO_LANGUAGE:
        return base + _MULTILINGUAL_INSTRUCTION
    return base + _ONE_LANGUAGE_INSTRUCTION.format(language=LANGUAGES.get(language, language))


@dataclass(frozen=True)
class Settings:
    cartesia_api_key: str = ""
    llm_api_key: str = ""
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_provider: str = "openai"
    llm_thinking: bool = False
    personality: str = ""
    language: str = AUTO_LANGUAGE
    voice_id: str = DEFAULT_VOICE_ID
    tts_model: str = "sonic-3"
    stt_model: str = "ink-preview"
    vad_threshold: float = 0.03
    vad_min_speech_ms: int = 300
    vad_preroll_ms: int = 600
    end_silence_ms: int = 550
    unfinished_silence_ms: int = 1600
    echo_tail_ms: int = 500
    prebuffer_ms: int = 150
    stt_idle_timeout_s: float = 60.0
    barge_in: bool = False
    barge_in_threshold: float = 0.12
    claude: bool = True
    anthropic_api_key: str = field(default="", repr=False)
    claude_setup_token: str = field(default="", repr=False)
    claude_auth: str = API_KEY
    claude_model: str = DEFAULT_CLAUDE_MODEL
    claude_timeout_s: float = 60.0
    web_host: str = "0.0.0.0"
    web_port: int = DEFAULT_WEB_PORT
    web_pin: str = ""
    web_pin_hash: str = ""
    web_allowed_hosts: tuple[str, ...] = ()
    desktop: bool = False
    desktop_token: str = field(default="", repr=False)
    env_path: Path | None = None

    @property
    def multilingual(self) -> bool:
        return self.language == AUTO_LANGUAGE

    @property
    def system_prompt(self) -> str:
        return system_prompt(self.personality, self.language)

    @property
    def tts_language(self) -> str:
        return "en" if self.multilingual else self.language

    def missing(self) -> list[str]:
        needed = ["CARTESIA_API_KEY"]
        if self.llm_provider != "ollama":
            needed.append("LLM_API_KEY")
        present = {"CARTESIA_API_KEY": self.cartesia_api_key, "LLM_API_KEY": self.llm_api_key}
        return [key for key in needed if not present[key]]

    @classmethod
    def load(cls, env_path: Path | None = None, environ: dict[str, str] | None = None) -> "Settings":
        """The ``.env`` file wins over the environment, since the app's pages write to it."""
        env_path = env_path or paths.env_path()
        environ = dict(os.environ if environ is None else environ)
        values = {**environ, **envfile.read_values(env_path)}

        def get(key: str, default: str = "") -> str:
            return (values.get(key) or default).strip()

        desktop = _bool(environ.get(DESKTOP_ENV), False)
        base_url = get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
        provider = get("LLM_PROVIDER").lower() or ("ollama" if ":11434" in base_url else "openai")
        provider = {"api": "openai", "local": "ollama"}.get(provider, provider)
        if provider not in ("openai", "ollama"):
            logger.warning("LLM_PROVIDER=%r isn't openai or ollama; using openai", provider)
            provider = "openai"
        language = get("LANGUAGE_CODE", AUTO_LANGUAGE).lower()
        if language in ("multi", "multilingual"):
            language = AUTO_LANGUAGE
        pin, pin_hash = get("WEB_PIN"), get("WEB_PIN_HASH")
        default_host = "127.0.0.1" if desktop and not (pin or pin_hash) else "0.0.0.0"

        return cls(
            cartesia_api_key=get("CARTESIA_API_KEY"),
            llm_api_key=get("LLM_API_KEY"),
            llm_base_url=base_url,
            llm_model=get("LLM_MODEL", DEFAULT_LLM_MODEL),
            llm_provider=provider,
            llm_thinking=_bool(values.get("LLM_THINKING"), False),
            personality=get("SYSTEM_PROMPT"),
            language=language,
            voice_id=get("CARTESIA_VOICE_ID", DEFAULT_VOICE_ID),
            tts_model=get("CARTESIA_TTS_MODEL", "sonic-3"),
            stt_model=get("CARTESIA_STT_MODEL", "ink-preview"),
            vad_threshold=_number(values, "VAD_THRESHOLD", 0.03),
            vad_min_speech_ms=_number(values, "VAD_MIN_SPEECH_MS", 300, int),
            vad_preroll_ms=_number(values, "VAD_PREROLL_MS", 600, int),
            end_silence_ms=_number(values, "END_OF_TURN_SILENCE_MS", 550, int),
            unfinished_silence_ms=_number(values, "UNFINISHED_SILENCE_MS", 1600, int),
            echo_tail_ms=_number(values, "ECHO_TAIL_MS", 500, int),
            prebuffer_ms=_number(values, "PLAYBACK_PREBUFFER_MS", 150, int),
            stt_idle_timeout_s=_number(values, "STT_IDLE_TIMEOUT_S", 60.0),
            barge_in=_bool(values.get("BARGE_IN_ENABLED"), False),
            barge_in_threshold=_number(values, "BARGE_IN_THRESHOLD", 0.12),
            claude=_bool(values.get("CLAUDE_ENABLED"), True),
            anthropic_api_key=get("ANTHROPIC_API_KEY"),
            claude_setup_token=get("CLAUDE_CODE_OAUTH_TOKEN"),
            claude_auth=SETUP_TOKEN if get("CLAUDE_AUTH").lower() == SETUP_TOKEN else API_KEY,
            claude_model=get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL),
            claude_timeout_s=_number(values, "CLAUDE_TIMEOUT_S", 60.0),
            web_host=get("WEB_HOST", default_host),
            web_port=_number(values, "WEB_PORT", DEFAULT_WEB_PORT, int),
            web_pin=pin,
            web_pin_hash=pin_hash,
            web_allowed_hosts=tuple(h.strip() for h in get("WEB_ALLOWED_HOSTS").split(",") if h.strip()),
            desktop=desktop,
            desktop_token=(environ.get(DESKTOP_TOKEN_ENV) or "").strip(),
            env_path=env_path,
        )


def ensure_env_file(path: Path | None = None) -> Path:
    """The user's ``.env``, created empty with a pointer to the example on first run."""
    path = path or paths.env_path()
    if not path.is_file():
        envfile.write_private(
            path,
            "# Everything Agent settings. The app's Settings page edits this file;\n"
            "# see .env.example in the project for every option.\n",
        )
    return path
