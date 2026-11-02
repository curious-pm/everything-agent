import asyncio
import threading
import time

import numpy as np
import pytest

from everything_agent.conversation.engine import Conversation, Providers
from everything_agent.conversation.history import History
from everything_agent.events import Events
from everything_agent.settings import Settings
from everything_agent.tools import Tool, ToolCall

SAMPLE_RATE = 16000
FRAME = SAMPLE_RATE // 50


class FakeOut:
    sample_rate = SAMPLE_RATE

    def __init__(self):
        self.pushed = 0
        self.cleared = False

    def begin_playback(self):
        pass

    def push(self, chunk):
        self.pushed += chunk.size

    def clear_playback(self):
        self.cleared = True

    def end_playback(self):
        pass


class FakeRobot:
    input_rate = SAMPLE_RATE

    def __init__(self, talking=()):
        self.media_lock = threading.Lock()
        self.asleep = threading.Event()
        self.out = FakeOut()
        self.talking = list(talking)
        self.t0 = time.monotonic()

    def read_mic(self):
        time.sleep(FRAME / SAMPLE_RATE)
        t = time.monotonic() - self.t0
        loud = any(start <= t < end for start, end in self.talking)
        return np.full(FRAME, 0.1 if loud else 0.0, dtype=np.float32)

    def restart_recording(self):
        pass

    def go_to_sleep(self):
        self.asleep.set()

    def wake_up(self):
        self.asleep.clear()


class FakeStt:
    def __init__(self, words):
        self.words = words
        self.audio_bytes = 0
        self.queue: asyncio.Queue = asyncio.Queue()

    async def send_audio(self, pcm):
        self.audio_bytes += len(pcm)

    async def finalize(self):
        if self.audio_bytes:
            await self.queue.put(("text", self.words))
        await self.queue.put(("flushed", ""))

    async def close(self):
        await self.queue.put(None)

    async def events(self):
        while (item := await self.queue.get()) is not None:
            yield item


class FakeVoice:
    voice_id = "test"

    def __init__(self):
        self.spoken = []

    async def stream(self, text):
        self.spoken.append(text)
        for _ in range(3):
            await asyncio.sleep(0.01)
            yield np.full(2400, 0.05, dtype=np.float32)

    async def prewarm(self):
        pass

    async def close(self):
        pass


def make(robot, reply=("Hi there, nice to meet you. ", "How is your day going?"), words="hello robot"):
    stt_sessions = []
    voice = FakeVoice()
    seen_messages = []

    async def connect(rate):
        session = FakeStt(words)
        stt_sessions.append(session)
        return session

    async def stream_reply(messages, tools=None):
        seen_messages.append(messages)
        for part in reply:
            await asyncio.sleep(0.02)
            yield part

    async def warm_up():
        pass

    settings = Settings(cartesia_api_key="c", llm_api_key="l", echo_tail_ms=50, prebuffer_ms=50, end_silence_ms=400)
    events = Events()
    conversation = Conversation(
        settings, robot, events, Providers(connect, stream_reply, voice, warm_up), History("Be brief."), tools=[],
    )
    return conversation, events, voice, stt_sessions, seen_messages


async def run_until(conversation, events, predicate, timeout=10.0):
    stop = asyncio.Event()
    task = asyncio.create_task(conversation.run(stop))
    deadline = time.monotonic() + timeout
    try:
        while not predicate(events.since(0)[1]):
            assert time.monotonic() < deadline, f"timed out; events: {events.since(0)[1]}"
            assert not task.done(), task.exception()
            await asyncio.sleep(0.05)
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)


def transcripts(events, role):
    return [e["text"] for e in events if e["kind"] == "transcript" and e["role"] == role]


async def test_spoken_question_gets_a_spoken_reply():
    robot = FakeRobot(talking=[(0.3, 1.1)])
    conversation, events, voice, sessions, seen = make(robot)
    await run_until(conversation, events, lambda ev: transcripts(ev, "assistant"))

    all_events = events.since(0)[1]
    assert transcripts(all_events, "user") == ["hello robot"]
    assert transcripts(all_events, "assistant") == ["Hi there, nice to meet you. How is your day going?"]
    assert voice.spoken == ["Hi there, nice to meet you.", "How is your day going?"]
    assert robot.out.pushed > 0
    speech_before_the_socket_opened_was_kept = sessions[0].audio_bytes >= 2 * SAMPLE_RATE * 0.6
    assert speech_before_the_socket_opened_was_kept
    assert seen[0][0]["role"] == "system" and seen[0][-1] == {"role": "user", "content": "hello robot"}
    assert [m["role"] for m in conversation.history.messages] == ["user", "assistant"]


async def test_typed_message_is_answered_and_wakes_reachy():
    robot = FakeRobot()
    conversation, events, voice, _, _ = make(robot, reply=("Sure thing, here you go.",))
    robot.asleep.set()
    conversation.asleep = True

    stop = asyncio.Event()
    task = asyncio.create_task(conversation.run(stop))
    await asyncio.sleep(0.1)
    await conversation.say("  what time   is it ")
    deadline = time.monotonic() + 5
    while not transcripts(events.since(0)[1], "assistant"):
        assert time.monotonic() < deadline
        await asyncio.sleep(0.05)
    stop.set()
    await task

    assert not conversation.asleep and not robot.asleep.is_set()
    assert transcripts(events.since(0)[1], "user") == ["what time is it"]
    assert voice.spoken == ["Sure thing, here you go."]


async def test_a_failed_model_still_answers_out_loud():
    robot = FakeRobot()
    conversation, events, voice, _, _ = make(robot)

    async def broken(messages, tools=None):
        raise RuntimeError("HTTP 401 from the model")
        yield ""  # pragma: no cover

    conversation.providers.stream_reply = broken
    stop = asyncio.Event()
    task = asyncio.create_task(conversation.run(stop))
    await conversation.say("hello")
    deadline = time.monotonic() + 5
    while not transcripts(events.since(0)[1], "assistant"):
        assert time.monotonic() < deadline
        await asyncio.sleep(0.05)
    stop.set()
    await task
    kinds = [e["kind"] for e in events.since(0)[1]]
    assert "problem" in kinds
    assert voice.spoken and "Sorry" in voice.spoken[0]


async def test_speech_during_a_reply_is_answered_after_it():
    robot = FakeRobot()
    conversation, events, voice, _, _ = make(robot, reply=("One moment please, thinking.",))
    stop = asyncio.Event()
    task = asyncio.create_task(conversation.run(stop))
    await conversation.say("first question")
    await asyncio.sleep(0.05)
    await conversation.say("second question")
    deadline = time.monotonic() + 8
    while len(transcripts(events.since(0)[1], "assistant")) < 2:
        assert time.monotonic() < deadline
        await asyncio.sleep(0.05)
    stop.set()
    await task
    assert transcripts(events.since(0)[1], "user") == ["first question", "second question"]


@pytest.mark.parametrize("muted", [True])
async def test_muted_microphone_hears_nothing(muted):
    from everything_agent import mute

    mute.set_mute(mic=muted)
    robot = FakeRobot(talking=[(0.2, 1.0)])
    conversation, events, _, sessions, _ = make(robot)
    stop = asyncio.Event()
    task = asyncio.create_task(conversation.run(stop))
    await asyncio.sleep(1.8)
    stop.set()
    await task
    assert sessions == [] and conversation.status()["mic_muted"] is True


class LookUp(Tool):
    name = "look_up"
    follow_up = False
    ack = "Let me look into that."

    async def run(self, args, ctx):
        async def later():
            await asyncio.sleep(0.2)
            ctx.announce(f"The answer about {args['topic']} is forty two.")

        ctx.spawn(later())
        return "working on it"


class Clock(Tool):
    name = "clock"

    async def run(self, args, ctx):
        return "It is noon."


async def wait_for_replies(conversation, events, count, timeout=8):
    stop = asyncio.Event()
    task = asyncio.create_task(conversation.run(stop))
    await conversation.say("tell me something hard")
    deadline = time.monotonic() + timeout
    while len(transcripts(events.since(0)[1], "assistant")) < count:
        assert time.monotonic() < deadline, events.since(0)[1]
        await asyncio.sleep(0.05)
    stop.set()
    await task


async def test_a_background_tool_is_acknowledged_then_answers_out_loud():
    robot = FakeRobot()
    conversation, events, voice, _, _ = make(robot)
    offered = []

    async def calls_tool(messages, tools=None):
        offered.append(tools)
        yield ToolCall("c1", "look_up", '{"topic": "life"}')

    conversation.providers.stream_reply = calls_tool
    conversation.tools = [LookUp()]
    await wait_for_replies(conversation, events, 2)

    said = ["Let me look into that.", "The answer about life is forty two."]
    assert transcripts(events.since(0)[1], "assistant") == said
    assert voice.spoken == said
    assert offered[0][0]["function"]["name"] == "look_up"
    assert [m["role"] for m in conversation.history.messages] == ["user", "assistant", "assistant"]


async def test_a_quick_tool_result_goes_back_to_the_model():
    robot = FakeRobot()
    conversation, events, voice, _, _ = make(robot)
    rounds = []

    async def model(messages, tools=None):
        rounds.append(messages)
        if len(rounds) == 1:
            yield ToolCall("c1", "clock", "{}")
        else:
            yield "It's noon right now."

    conversation.providers.stream_reply = model
    conversation.tools = [Clock()]
    await wait_for_replies(conversation, events, 1)

    assert rounds[1][-1] == {"role": "tool", "tool_call_id": "c1", "content": "It is noon."}
    assert rounds[1][-2]["tool_calls"][0]["function"]["name"] == "clock"
    assert voice.spoken == ["It's noon right now."]
    assert [m["role"] for m in conversation.history.messages] == ["user", "assistant"]


class StreamedLookUp(Tool):
    name = "look_up"
    follow_up = False
    ack = "Let me look into that."

    def __init__(self):
        self.sent_second_sentence_at = None

    async def run(self, args, ctx):
        async def answer():
            await asyncio.sleep(0.2)
            yield "Canberra is the capital. "
            await asyncio.sleep(0.6)
            self.sent_second_sentence_at = time.monotonic()
            yield "It was a compromise."

        ctx.announce_stream(answer())
        return "working on it"


async def test_a_streamed_answer_is_spoken_sentence_by_sentence():
    robot = FakeRobot()
    conversation, events, voice, _, _ = make(robot)
    tool = StreamedLookUp()
    first_spoken_at = []
    stream = voice.stream

    async def timed(text):
        if text.startswith("Canberra"):
            first_spoken_at.append(time.monotonic())
        async for audio in stream(text):
            yield audio

    async def calls_tool(messages, tools=None):
        yield ToolCall("c1", "look_up", "{}")

    voice.stream = timed
    conversation.providers.stream_reply = calls_tool
    conversation.tools = [tool]
    await wait_for_replies(conversation, events, 2)

    assert voice.spoken == ["Let me look into that.", "Canberra is the capital.", "It was a compromise."]
    assert first_spoken_at[0] < tool.sent_second_sentence_at
    assert transcripts(events.since(0)[1], "assistant")[-1] == "Canberra is the capital. It was a compromise."
