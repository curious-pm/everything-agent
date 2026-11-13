import asyncio
import os

from everything_agent import tools
from everything_agent.settings import Settings
from everything_agent.tools import ask_claude, claude


class FakeBackend:
    def __init__(self, name, parts=(), error=None, after=0):
        self.name = name
        self.parts = parts
        self.error = error
        self.after = after
        self.asked = []

    async def answer(self, question):
        self.asked.append(question)
        for part in self.parts[: self.after or len(self.parts)]:
            yield part
        if self.error:
            raise claude.ClaudeError(self.error)
        for part in self.parts[self.after or len(self.parts):]:
            yield part


def tool_with(*backends, timeout_s=5.0):
    tool = ask_claude.AskClaude(Settings(anthropic_api_key="k", claude_timeout_s=timeout_s))
    tool.backends = list(backends)
    return tool


async def spoken(tool, question="Who won?"):
    return "".join([part async for part in tool.answer(question)])


def test_claude_is_offered_only_when_on_and_signed_in():
    assert tools.available(Settings()) == []
    assert tools.available(Settings(claude=False, anthropic_api_key="k")) == []
    assert [t.name for t in tools.available(Settings(claude_setup_token="t"))] == ["ask_claude"]


def test_the_chosen_way_in_goes_first_and_the_other_is_the_backup():
    both = {"anthropic_api_key": "k", "claude_setup_token": "t"}
    assert [b.name for b in claude.backends(Settings(**both))] == ["Anthropic API key", "Claude setup token"]
    assert [b.name for b in claude.backends(Settings(**both, claude_auth="setup_token"))] == ["Claude setup token", "Anthropic API key"]
    assert [b.name for b in claude.backends(Settings(claude_setup_token="t", claude_auth="api_key"))] == ["Claude setup token"]


def test_the_choice_is_read_from_the_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=k\nCLAUDE_CODE_OAUTH_TOKEN=t\nCLAUDE_AUTH=setup_token\n")
    settings = Settings.load(env, environ={})
    assert (settings.anthropic_api_key, settings.claude_setup_token, settings.claude_auth) == ("k", "t", "setup_token")
    assert Settings.load(tmp_path / "none", environ={"CLAUDE_AUTH": "nonsense"}).claude_auth == "api_key"


async def test_a_failure_before_any_words_falls_back_to_the_other():
    first = FakeBackend("key", error="The Anthropic API key was rejected.")
    second = FakeBackend("token", parts=("Spain won. ", "It was close."))
    assert await spoken(tool_with(first, second)) == "Spain won. It was close."
    assert first.asked == second.asked == ["Who won?"]


async def test_a_failure_mid_answer_doesnt_start_again():
    first = FakeBackend("key", parts=("Spain won. ", "More"), error="Claude ran into a problem.", after=1)
    second = FakeBackend("token", parts=("Something else.",))
    assert await spoken(tool_with(first, second)) == "Spain won. "
    assert second.asked == []


async def test_when_nothing_works_reachy_says_why():
    tool = tool_with(FakeBackend("key", error="Claude has reached its usage limit for now."))
    assert await spoken(tool) == "Sorry, I couldn't get an answer from Claude. Claude has reached its usage limit for now."
    assert tool.busy is False


async def test_a_slow_answer_gives_up():
    class Slow(FakeBackend):
        async def answer(self, question):
            await asyncio.sleep(1)
            yield "late"

    assert await spoken(tool_with(Slow("key"), timeout_s=0.1)) == "Sorry, I couldn't get an answer from Claude. Claude took longer than 0 seconds."


def test_the_setup_token_agent_only_searches_and_cant_see_this_apps_keys(monkeypatch):
    monkeypatch.setenv("CARTESIA_API_KEY", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "would-win-over-the-token")
    monkeypatch.setenv("SOMETHING_ELSE", "kept")
    options = claude.SetupTokenClaude("tok", "claude-haiku-5-5").options()
    assert options.env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert options.env["CARTESIA_API_KEY"] == "" and options.env["ANTHROPIC_API_KEY"] == ""
    assert "SOMETHING_ELSE" not in options.env and os.environ["SOMETHING_ELSE"] == "kept"
    assert options.tools == ["WebSearch"] and options.permission_mode == "dontAsk"
    assert options.setting_sources == [] and options.strict_mcp_config
    assert options.model == "claude-haiku-5-5"
