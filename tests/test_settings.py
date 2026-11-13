from everything_agent import envfile
from everything_agent.conversation.history import History
from everything_agent.server.auth import Auth, LockedOut, hash_pin, pin_matches
from everything_agent.settings import DEFAULT_SYSTEM_PROMPT, Settings

import pytest


def test_env_file_edits_keep_other_lines(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# comment\nA=1\nB='two words'\n", encoding="utf-8")
    envfile.set_values(path, {"B": "has # hash", "C": "new"})
    assert path.read_text(encoding="utf-8").startswith("# comment\nA=1\n")
    assert envfile.read_values(path) == {"A": "1", "B": "has # hash", "C": "new"}


def test_the_file_wins_over_the_environment(tmp_path):
    path = tmp_path / ".env"
    envfile.set_values(path, {"LLM_MODEL": "from-file"})
    settings = Settings.load(path, {"LLM_MODEL": "from-env", "CARTESIA_API_KEY": "k"})
    assert settings.llm_model == "from-file"
    assert settings.cartesia_api_key == "k"


def test_missing_keys_and_ollama_needs_no_model_key(tmp_path):
    path = tmp_path / ".env"
    assert Settings.load(path, {}).missing() == ["CARTESIA_API_KEY", "LLM_API_KEY"]
    ollama = Settings.load(path, {"CARTESIA_API_KEY": "k", "LLM_BASE_URL": "http://localhost:11434"})
    assert ollama.llm_provider == "ollama" and ollama.missing() == []


def test_language_shapes_the_prompt(tmp_path):
    path = tmp_path / ".env"
    auto = Settings.load(path, {})
    assert auto.multilingual and auto.system_prompt.startswith(DEFAULT_SYSTEM_PROMPT)
    hindi = Settings.load(path, {"LANGUAGE_CODE": "hi", "SYSTEM_PROMPT": "Be a pirate."})
    assert hindi.system_prompt.startswith("Be a pirate. Everything you write is spoken aloud")
    assert hindi.system_prompt.endswith("Always reply in Hindi, even if the user's words are unclear.")
    assert hindi.tts_language == "hi"


def test_desktop_without_a_pin_stays_on_this_computer(tmp_path):
    path = tmp_path / ".env"
    assert Settings.load(path, {"EVERYTHING_AGENT_DESKTOP": "1"}).web_host == "127.0.0.1"
    assert Settings.load(path, {"EVERYTHING_AGENT_DESKTOP": "1", "WEB_PIN": "1234"}).web_host == "0.0.0.0"
    assert Settings.load(path, {}).web_host == "0.0.0.0"


def test_history_keeps_recent_lines_and_starts_on_the_user(tmp_path):
    history = History("Be nice.", tmp_path / "c.json", keep=4)
    for i in range(3):
        history.add("user", f"q{i}")
        history.add("assistant", f"a{i}")
    history.save()
    again = History("Be nice.", tmp_path / "c.json", keep=4)
    assert [m["content"] for m in again.messages] == ["q1", "a1", "q2", "a2"]
    model = again.for_model()
    assert model[0]["role"] == "system" and model[0]["content"].startswith("Be nice.\n\nRight now it is")


def test_pins_are_hashed_and_wrong_ones_lock_out(tmp_path):
    stored = hash_pin("2468")
    assert pin_matches("2468", stored) and not pin_matches("1357", stored)
    auth = Auth(stored, "", "", tmp_path / ".env")
    assert auth.login("2468", "a") is not None
    for _ in range(5):
        assert auth.login("0000", "b") is None
    with pytest.raises(LockedOut):
        auth.login("2468", "b")


def test_setting_a_pin_saves_only_its_hash(tmp_path):
    path = tmp_path / ".env"
    auth = Auth("", "", "", path)
    session = auth.set_pin("9876")
    assert auth.session_ok(session)
    saved = envfile.read_values(path)
    assert "9876" not in path.read_text(encoding="utf-8") and pin_matches("9876", saved["WEB_PIN_HASH"])


def test_saved_values_are_never_expanded(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setenv("SECRET_TOKEN", "leaked")
    envfile.set_values(path, {"CARTESIA_API_KEY": "real-key", "LLM_MODEL": "${CARTESIA_API_KEY}", "SYSTEM_PROMPT": "a $SECRET_TOKEN b"})
    values = envfile.read_values(path)
    assert values["LLM_MODEL"] == "${CARTESIA_API_KEY}" and values["SYSTEM_PROMPT"] == "a $SECRET_TOKEN b"
