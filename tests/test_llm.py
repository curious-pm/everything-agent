import json

import httpx
import pytest

from everything_agent.settings import Settings
from everything_agent.voice import llm


def sse(*parts: str) -> bytes:
    events = [{"choices": [{"delta": {"content": p}}]} for p in parts]
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode() + b"data: [DONE]\n\n"


@pytest.fixture
def server(monkeypatch):
    calls: list[dict] = []
    replies: list[httpx.Response] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return replies.pop(0)

    monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(llm.asyncio, "sleep", _no_wait)
    llm._thinking_required.clear()
    return calls, replies


async def _no_wait(_seconds):
    return None


async def collect(settings: Settings) -> str:
    return "".join([t async for t in llm.stream_reply(settings, [{"role": "user", "content": "hi"}])])


async def test_streams_text_and_turns_thinking_off_on_openrouter(server):
    calls, replies = server
    replies.append(httpx.Response(200, content=sse("Hello", " there.")))
    assert await collect(Settings(llm_api_key="k")) == "Hello there."
    assert calls[0]["reasoning"] == {"enabled": False} and calls[0]["stream"] is True


async def test_a_rate_limit_is_retried_once(server):
    calls, replies = server
    replies += [httpx.Response(429, json={"error": "busy"}), httpx.Response(200, content=sse("Ok."))]
    assert await collect(Settings(llm_api_key="k")) == "Ok."
    assert len(calls) == 2


async def test_models_that_must_think_are_let_think(server):
    calls, replies = server
    replies += [httpx.Response(400, json={"error": "reasoning is mandatory"}), httpx.Response(200, content=sse("Fine."))]
    assert await collect(Settings(llm_api_key="k")) == "Fine."
    assert "reasoning" in calls[0] and "reasoning" not in calls[1]


async def test_a_bad_key_is_reported(server):
    _, replies = server
    replies.append(httpx.Response(401, json={"error": "no such key"}))
    with pytest.raises(llm.ReplyError, match="401"):
        await collect(Settings(llm_api_key="bad"))


async def test_tool_calls_arrive_whole_after_the_text(server):
    calls, replies = server
    pieces = [
        {"choices": [{"delta": {"content": "Let me check."}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "ask_claude", "arguments": '{"quest'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'ion": "news?"}'}}]}}]},
    ]
    body = "".join(f"data: {json.dumps(p)}\n\n" for p in pieces).encode() + b"data: [DONE]\n\n"
    replies.append(httpx.Response(200, content=body))
    tools = [{"type": "function", "function": {"name": "ask_claude", "parameters": {}}}]
    items = [i async for i in llm.stream_reply(Settings(llm_api_key="k"), [], tools)]
    assert items[0] == "Let me check."
    call = items[1]
    assert (call.id, call.name, call.args()) == ("c1", "ask_claude", {"question": "news?"})
    assert calls[0]["tools"] == tools


async def test_a_model_without_tools_still_answers(server):
    calls, replies = server
    replies += [httpx.Response(404, json={"error": "No endpoints found that support tool use"}), httpx.Response(200, content=sse("Hi."))]
    tools = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
    assert [i async for i in llm.stream_reply(Settings(llm_api_key="k"), [], tools)] == ["Hi."]
    assert "tools" in calls[0] and "tools" not in calls[1]
