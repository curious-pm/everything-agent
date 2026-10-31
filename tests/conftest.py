import pytest


@pytest.fixture(autouse=True)
def app_home(tmp_path, monkeypatch):
    monkeypatch.setenv("EVERYTHING_AGENT_HOME", str(tmp_path))
    for key in ("CARTESIA_API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "WEB_PIN", "WEB_PIN_HASH",
                "EVERYTHING_AGENT_DESKTOP", "EVERYTHING_AGENT_DESKTOP_TOKEN", "LANGUAGE_CODE"):
        monkeypatch.delenv(key, raising=False)
    return tmp_path
