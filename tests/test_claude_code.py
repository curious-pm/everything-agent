import json

from everything_agent import envfile, paths, tools
from everything_agent.settings import Settings
from everything_agent.tools import claude_code


def test_the_answer_is_read_from_claudes_json():
    out = '{"type":"result","subtype":"success","is_error":false,"result":"It is sunny in Pune today."}'
    assert claude_code.parse(out).text == "It is sunny in Pune today."


def test_failures_become_a_short_spoken_reason():
    answer = claude_code.parse('{"type":"result","is_error":true,"result":"Not logged in · Please run /login"}')
    assert not answer.text
    assert claude_code.describe(answer.error) == "Claude Code isn't signed in on this computer."
    assert claude_code.parse("").error


def test_claude_only_looks_things_up():
    argv = claude_code.command_line("claude", ["/home/me/Notes"])
    tools_ = argv[argv.index("--tools") + 1].split(",")
    assert "Bash" not in tools_ and "Write" not in tools_ and "WebSearch" in tools_
    assert "--restricted" in argv and "--strict-mcp-config" in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--add-dir") + 1] == "/home/me/Notes"
    denied = argv[argv.index("--disallowedTools") + 1]
    assert "Read(//**/.env)" in denied and "Grep(//**/.aws/**)" in denied


def test_sources_are_left_out_of_the_spoken_answer():
    text = "Rust 1.99 is the latest.\n\nSources:\n- [rust-lang.org](https://www.rust-lang.org/)"
    assert claude_code.parse(json.dumps({"result": text})).text == "Rust 1.99 is the latest."


def test_this_apps_keys_are_hidden_from_claude(monkeypatch):
    envfile.set_values(paths.env_path(), {"CARTESIA_API_KEY": "secret"})
    monkeypatch.setenv("CARTESIA_API_KEY", "secret")
    monkeypatch.setenv("SOMETHING_ELSE", "kept")
    monkeypatch.setenv("LLM_API_KEY", "only-in-the-environment")
    monkeypatch.setenv("EVERYTHING_AGENT_CORE_TOKEN", "t")
    env = claude_code._environment()
    assert "CARTESIA_API_KEY" not in env and "LLM_API_KEY" not in env and "EVERYTHING_AGENT_CORE_TOKEN" not in env
    assert env["SOMETHING_ELSE"] == "kept"


def test_asking_claude_is_offered_only_when_installed_and_on():
    assert tools.available(Settings(claude_code=False)) == []
    assert tools.available(Settings(claude_code_command="no-such-claude-here")) == []
