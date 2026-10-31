"""The conversation loop: listen, decide when the user has finished, reply out loud, repeat."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

import numpy as np

from .. import mute
from ..audio.barge_in import BargeInDetector
from ..audio.dsp import Resampler, float_to_pcm16, rms, to_mono
from ..audio.mic import MicReader
from ..audio.speaker import AudioOut, Speaker
from ..events import Events
from ..settings import Settings
from ..tools import Tool, ToolCall, ToolContext, available
from ..voice import tts as tts_module
from ..voice.stt import SttSession
from .history import History
from .sentences import SentenceSplitter, speakable
from .turn_taking import end_of_turn_silence_s

logger = logging.getLogger(__name__)

_SPEECH_HANGOVER_S = 0.5
_MIC_STALL_S = 3.0
_MIC_RESTART_COOLDOWN_S = 5.0
_STT_CONNECT_GIVE_UP_S = 6.0
_PLAYBACK_CHUNK_S = 0.1
_SPEAKING_GRACE_S = 0.6
_DUCK_GAIN = 0.25
_MAX_HELD_UTTERANCES = 3
_MODEL_WARM_INTERVAL_S = 20.0
_GATED_TAIL_S = 1.0
_PREROLL_MARGIN_S = 0.3
_MAX_TOOL_ROUNDS = 3
_FALLBACK_LINE = "Sorry, I couldn't come up with an answer just now. Could you say that again?"
_INTERRUPTED_NOTE = " … [the user interrupted before Reachy finished]"


class Robot(Protocol):
    input_rate: int
    media_lock: threading.Lock
    out: AudioOut

    def read_mic(self) -> np.ndarray | None: ...
    def restart_recording(self) -> None: ...
    def go_to_sleep(self) -> None: ...
    def wake_up(self) -> None: ...


class Voice(Protocol):
    voice_id: str

    def stream(self, text: str) -> AsyncIterator[np.ndarray]: ...
    async def prewarm(self) -> None: ...
    async def close(self) -> None: ...


@dataclass
class Providers:
    """The cloud services, swappable so the loop can be tested without them."""

    connect_stt: Callable[[int], Awaitable[SttSession]]
    stream_reply: Callable[[list[dict[str, Any]], list[dict[str, Any]] | None], AsyncIterator[str | ToolCall]]
    voice: Voice
    warm_up: Callable[[], Awaitable[None]]


def cloud_providers(settings: Settings) -> Providers:
    from ..voice import llm, stt

    return Providers(
        connect_stt=lambda rate: stt.connect(settings.cartesia_api_key, settings.stt_model, rate),
        stream_reply=lambda messages, tools: llm.stream_reply(settings, messages, tools),
        voice=tts_module.CartesiaTTS(
            settings.cartesia_api_key, settings.tts_model, settings.voice_id,
            settings.tts_language, settings.multilingual,
        ),
        warm_up=lambda: llm.warm_up(settings),
    )


@dataclass
class _Turn:
    text: str
    spoken: bool
    task: asyncio.Task | None = None
    started: float = field(default_factory=time.monotonic)
    committed: bool = False
    withdrawn: bool = False


class _SpeechRun:
    """The current run of loud microphone frames."""

    def __init__(self) -> None:
        self.started: float | None = None
        self.last: float | None = None

    def update(self, loud: bool, now: float) -> None:
        if loud:
            if self.started is None:
                self.started = now
            self.last = now
        elif self.last is not None and now - self.last > _SPEECH_HANGOVER_S:
            self.reset()

    def reset(self) -> None:
        self.started = self.last = None


class Conversation:
    def __init__(
        self,
        settings: Settings,
        robot: Robot,
        events: Events,
        providers: Providers | None = None,
        history: History | None = None,
        tools: list[Tool] | None = None,
    ) -> None:
        self.settings = settings
        self.robot = robot
        self.events = events
        self.providers = providers or cloud_providers(settings)
        self.history = history or History(settings.system_prompt)
        self.tools = available(settings) if tools is None else tools
        self._tool_context = ToolContext(announce=self.announce, spawn=self._spawn)
        self.speaker = Speaker(robot.out, settings.prebuffer_ms / 1000.0)
        self._barge = BargeInDetector(settings.barge_in_threshold)
        self._resampler = Resampler(tts_module.SAMPLE_RATE, robot.out.sample_rate)

        robot_asleep = getattr(robot, "asleep", None)
        self.asleep = bool(robot_asleep is not None and robot_asleep.is_set())
        self._turn_lock = asyncio.Lock()
        self._turn: _Turn | None = None
        self._gated = False
        self._barge_in = False
        self._replay_tail = False
        self._held: list[str] = []

        self._stt: SttSession | None = None
        self._stt_reader: asyncio.Task | None = None
        self._utterance = ""
        self._voice_at: float | None = None
        self._finalize_sent = False
        self._last_activity = time.monotonic()

        self._mic_level = 0.0
        self._mic_frame_at: float | None = None
        self._warmed_at = 0.0
        self._started_at = time.monotonic()
        self._background: set[asyncio.Task] = set()

    async def run(self, stop: asyncio.Event) -> None:
        await asyncio.gather(self.providers.voice.prewarm(), self.providers.warm_up())
        tasks = [asyncio.create_task(self._listen(), name="listen"), asyncio.create_task(self._watch_idle(), name="idle")]
        stopper = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task is not stopper:
                    task.result()
        finally:
            for task in [*tasks, stopper, *self._background]:
                task.cancel()
            if self._turn is not None and self._turn.task is not None:
                self._turn.task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.speaker.finish(interrupt=True)
            await self._drop_stt()
            await self.providers.voice.close()

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        audible = now < self.speaker.audible_until + self.settings.echo_tail_ms / 1000.0 + _SPEAKING_GRACE_S
        if self.asleep:
            phase = "asleep"
        elif audible:
            phase = "speaking"
        elif self._turn_lock.locked():
            phase = "thinking"
        elif self._stt is not None:
            phase = "listening"
        else:
            phase = "idle"
        muted = mute.read()
        return {
            "session": "running",
            "phase": phase,
            "asleep": self.asleep,
            "listening": self._stt is not None,
            "in_turn": self._turn_lock.locked(),
            "mic_muted": muted.mic,
            "speaker_muted": muted.speaker,
            "mic_level": round(self._mic_level, 4),
            "speaker_level": round(self.speaker.level, 4) if audible else 0.0,
            "mic_threshold": self.settings.vad_threshold,
            "mic_frame_age_s": round(now - self._mic_frame_at, 1) if self._mic_frame_at is not None else None,
            "uptime_s": round(now - self._started_at, 1),
        }

    async def say(self, text: str) -> None:
        if self.asleep:
            await self.wake()
        self._start_turn(text, spoken=False)

    async def sleep(self) -> None:
        if self.asleep:
            return
        self.asleep = True
        if self._turn is not None and self._turn.task is not None:
            self._turn.task.cancel()
        await asyncio.get_running_loop().run_in_executor(None, self.robot.go_to_sleep)
        await self._drop_stt()
        self.events.publish("sleep")
        logger.info("Reachy is asleep")

    async def wake(self) -> None:
        if not self.asleep:
            return
        await asyncio.get_running_loop().run_in_executor(None, self.robot.wake_up)
        self.asleep = False
        self._last_activity = time.monotonic()
        self.events.publish("wake")
        logger.info("Reachy is awake")

    def announce(self, text: str) -> None:
        """Say something unprompted, once any reply in progress is over."""
        self._spawn(self._say_aloud(text))

    def set_voice(self, voice_id: str) -> None:
        self.providers.voice.voice_id = voice_id

    def clear_history(self) -> None:
        self.history.clear()

    def _start_turn(self, text: str, spoken: bool) -> None:
        text = " ".join(text.split())
        if not text:
            return
        if self._turn_lock.locked():
            self._held.append(text)
            del self._held[:-_MAX_HELD_UTTERANCES]
            logger.info("Holding %r until the current reply finishes", text)
            if len(self._held) == 1:
                self._spawn(self._reply_to_held())
            return
        self.events.publish("transcript", role="user", text=text)
        logger.info("You: %s", text)
        turn = _Turn(text=text, spoken=spoken)
        turn.task = asyncio.create_task(self._reply(turn, spoke_until=self._voice_at if spoken else None))
        turn.task.add_done_callback(_log_failure)

    async def _reply_to_held(self) -> None:
        while self._turn_lock.locked():
            await asyncio.sleep(0.05)
        texts, self._held = self._held, []
        if texts and not self.asleep:
            self._start_turn(" ".join(texts), spoken=True)

    def _withdraw(self, turn: _Turn) -> None:
        turn.withdrawn = True
        if turn.task is not None:
            turn.task.cancel()
        self._utterance = f"{turn.text} {self._utterance}".strip()
        self.events.publish("withdrawn", text=turn.text)
        logger.info("You carried on before Reachy answered %r; waiting for the rest", turn.text)

    async def _reply(self, turn: _Turn, spoke_until: float | None) -> None:
        async with self._turn_lock:
            self._turn = turn
            heard_at = time.monotonic()
            entry = self.history.add("user", turn.text)
            self.history.save()
            timing: dict[str, float] = {}
            sentences: asyncio.Queue[str | None] = asyncio.Queue()
            self._begin_playback()
            voice_task = asyncio.create_task(self._speak(sentences, timing))
            try:
                splitter = SentenceSplitter()
                said: list[str] = []
                try:
                    try:
                        await self._compose(turn, splitter, sentences, said, timing)
                    except Exception as exc:
                        logger.error("The model didn't answer: %s", exc)
                        self.events.publish("problem", text=f"The AI model didn't answer: {exc}")
                    reply = "".join(said)
                    tail = splitter.flush()
                    if tail and not self._barge_in:
                        turn.committed = True
                        sentences.put_nowait(tail)
                    if not reply.strip():
                        reply = _FALLBACK_LINE
                        turn.committed = True
                        sentences.put_nowait(reply)
                finally:
                    sentences.put_nowait(None)
                    await voice_task
                interrupted = self._barge_in
                await self._end_playback()
            except asyncio.CancelledError:
                if not turn.committed:
                    self.history.remove(entry)
                    self.history.save()
                voice_task.cancel()
                raise
            finally:
                self._gated = False
                self._turn = None
                if self.speaker.playing:
                    await self.speaker.finish(interrupt=True)

            self._record_reply(reply.strip() + (_INTERRUPTED_NOTE if interrupted else ""), speakable(reply) or reply.strip())
            _log_timing(heard_at, spoke_until, timing)

    async def _compose(
        self, turn: _Turn, splitter: SentenceSplitter, sentences: asyncio.Queue[str | None],
        said: list[str], timing: dict[str, float],
    ) -> None:
        messages = self.history.for_model()
        schemas = [tool.schema() for tool in self.tools] or None

        def say(text: str) -> None:
            said.append(text)
            for sentence in splitter.feed(text):
                turn.committed = True
                sentences.put_nowait(sentence)

        for round_ in range(_MAX_TOOL_ROUNDS):
            text, calls = "", []
            offered = schemas if round_ < _MAX_TOOL_ROUNDS - 1 else None
            async for item in self.providers.stream_reply(messages, offered):
                if isinstance(item, ToolCall):
                    calls.append(item)
                    continue
                timing.setdefault("first_words", time.monotonic())
                text += item
                say(item)
                if self._barge_in:
                    return
            if not calls:
                return
            results = [await self._run_tool(call) for call in calls]
            if not any(tool is not None and tool.follow_up for tool, _ in results):
                if not "".join(said).strip():
                    say(next((tool.ack for tool, _ in results if tool is not None and tool.ack), ""))
                return
            messages = [
                *messages,
                {"role": "assistant", "content": text or None, "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments or "{}"}}
                    for c in calls
                ]},
                *({"role": "tool", "tool_call_id": c.id, "content": result} for c, (_, result) in zip(calls, results)),
            ]

    async def _run_tool(self, call: ToolCall) -> tuple[Tool | None, str]:
        tool = next((t for t in self.tools if t.name == call.name), None)
        if tool is None:
            logger.warning("The model asked for a tool that doesn't exist: %s", call.name)
            return None, f"There is no tool called {call.name}."
        logger.info("Using %s %s", call.name, call.arguments)
        self.events.publish("tool", name=call.name)
        try:
            return tool, await tool.run(call.args(), self._tool_context)
        except Exception as exc:
            logger.exception("%s failed", call.name)
            return tool, f"That didn't work: {exc}"

    async def _say_aloud(self, text: str) -> None:
        async with self._turn_lock:
            if not self.asleep:
                self._begin_playback()
                sentences: asyncio.Queue[str | None] = asyncio.Queue()
                splitter = SentenceSplitter()
                for sentence in [*splitter.feed(text), splitter.flush()]:
                    if sentence:
                        sentences.put_nowait(sentence)
                sentences.put_nowait(None)
                try:
                    await self._speak(sentences, {})
                    await self._end_playback()
                finally:
                    self._gated = False
                    if self.speaker.playing:
                        await self.speaker.finish(interrupt=True)
            self._record_reply(text, speakable(text) or text)

    def _begin_playback(self) -> None:
        self._gated = True
        self._resampler.reset()
        self.speaker.begin(asyncio.get_running_loop())

    def _record_reply(self, text: str, shown: str) -> None:
        self.history.add("assistant", text)
        self.history.save()
        self.events.publish("transcript", role="assistant", text=shown)
        self._last_activity = time.monotonic()
        logger.info("Reachy: %s", shown)

    async def _speak(self, sentences: asyncio.Queue[str | None], timing: dict[str, float]) -> None:
        """Synthesize queued sentences one at a time; the voice socket has a single reader."""
        chunk_samples = int(self.robot.out.sample_rate * _PLAYBACK_CHUNK_S)
        while (sentence := await sentences.get()) is not None:
            sentence = speakable(sentence)
            if self._barge_in or not sentence:
                continue
            pending = np.zeros(0, dtype=np.float32)
            try:
                async for audio in self.providers.voice.stream(sentence):
                    if self._barge_in:
                        break
                    pending = np.concatenate([pending, self._resampler.process(audio)])
                    while pending.size >= chunk_samples:
                        timing.setdefault("first_sound", time.monotonic())
                        self.speaker.put(pending[:chunk_samples])
                        pending = pending[chunk_samples:]
            except Exception as exc:
                logger.error("Couldn't speak a sentence: %s", exc)
                self.events.publish("problem", text=f"The voice didn't work: {exc}")
                continue
            if pending.size and not self._barge_in:
                timing.setdefault("first_sound", time.monotonic())
                self.speaker.put(pending)

    async def _end_playback(self) -> None:
        interrupted = self._barge_in
        self.speaker.duck_gain = 1.0
        await self.speaker.finish(interrupt=interrupted)
        if not interrupted:
            await asyncio.sleep(self.settings.echo_tail_ms / 1000.0)
        self._barge.reset()
        self._barge_in = False

    async def _listen(self) -> None:
        settings = self.settings
        rate = self.robot.input_rate
        min_speech_s = settings.vad_min_speech_ms / 1000.0
        preroll_cap = int(max(settings.vad_preroll_ms / 1000.0, min_speech_s + _PREROLL_MARGIN_S) * rate)
        preroll: deque[np.ndarray] = deque()
        preroll_samples = 0
        gated_tail: deque[np.ndarray] = deque()
        gated_samples = 0
        gated_cap = int(_GATED_TAIL_S * rate)
        was_gated = False
        run = _SpeechRun()
        connecting: asyncio.Task | None = None
        connect_started = 0.0
        pending: list[np.ndarray] = []
        last_frame_at = time.monotonic()
        last_restart = 0.0

        reader = MicReader(self.robot.read_mic, asyncio.get_running_loop(), self.robot.media_lock)
        reader.start()
        try:
            while True:
                raw = await reader.get(0.1)
                now = time.monotonic()
                if raw is None:
                    if now - last_frame_at > _MIC_STALL_S and now - last_restart > _MIC_RESTART_COOLDOWN_S:
                        last_restart = now
                        logger.warning("No sound from the microphone for %.0fs; restarting it", now - last_frame_at)
                        try:
                            await asyncio.get_running_loop().run_in_executor(None, self.robot.restart_recording)
                        except Exception:
                            logger.exception("Restarting the microphone failed")
                    continue
                last_frame_at = now
                frame = to_mono(raw)
                if mute.read().mic:
                    frame = np.zeros_like(frame)
                level = rms(frame)
                self._mic_level = max(level, self._mic_level * 0.9)
                self._mic_frame_at = now
                if self.asleep:
                    continue

                thinking = self._turn is not None and not self._turn.committed
                if self._gated and not thinking:
                    gated_tail.append(frame)
                    gated_samples += frame.size
                    while gated_samples > gated_cap and len(gated_tail) > 1:
                        gated_samples -= gated_tail.popleft().size
                    was_gated = True
                    if settings.barge_in and not self._barge_in:
                        self._check_barge_in(level, now)
                    continue
                if was_gated:
                    was_gated = False
                    tail = list(gated_tail)
                    gated_tail.clear()
                    gated_samples = 0
                    if self._replay_tail:
                        self._replay_tail = False
                        if self._stt is not None:
                            await self._send(tail)
                        elif connecting is not None:
                            pending[:0] = tail
                        else:
                            preroll = deque(tail)
                            preroll_samples = sum(c.size for c in tail)
                            run.started = now - min_speech_s
                            run.last = now

                loud = level >= settings.vad_threshold
                run.update(loud, now)
                if loud:
                    self._voice_at = now
                    self._finalize_sent = False
                    self._last_activity = now
                    self._warm_model(now)

                turn = self._turn
                if (
                    turn is not None and thinking and turn.spoken and not turn.withdrawn
                    and run.started is not None and run.started >= turn.started
                    and now - run.started >= min_speech_s
                ):
                    self._withdraw(turn)

                if self._stt is None:
                    if connecting is not None:
                        pending.append(frame)
                        if connecting.done():
                            task, connecting = connecting, None
                            error = task.exception() if not task.cancelled() else asyncio.CancelledError()
                            if error is not None:
                                logger.error("Couldn't connect to Cartesia speech to text: %s", error)
                                self.events.publish("problem", text=f"Couldn't reach speech to text: {error}")
                                pending, run.started = [], None
                            else:
                                self._attach_stt(task.result())
                                chunks, pending = pending, []
                                await self._send(chunks)
                        elif now - connect_started > _STT_CONNECT_GIVE_UP_S:
                            logger.warning("Speech to text took over %.0fs to connect; dropping that audio", _STT_CONNECT_GIVE_UP_S)
                            connecting.cancel()
                            connecting, pending, run.started = None, [], None
                        continue
                    if run.started is not None and now - run.started >= min_speech_s:
                        pending = [*preroll, frame]
                        preroll.clear()
                        preroll_samples = 0
                        connect_started = now
                        connecting = asyncio.create_task(self.providers.connect_stt(rate))
                        self._warm_model(now)
                        continue
                    preroll.append(frame)
                    preroll_samples += frame.size
                    while preroll_samples > preroll_cap and len(preroll) > 1:
                        preroll_samples -= preroll.popleft().size
                    continue

                await self._send([frame])
                if (
                    self._stt is not None and not self._finalize_sent and self._voice_at is not None
                    and now - self._voice_at >= end_of_turn_silence_s(
                        self._utterance, settings.end_silence_ms, settings.unfinished_silence_ms,
                    )
                ):
                    self._finalize_sent = True
                    try:
                        await self._stt.finalize()
                    except Exception as exc:
                        logger.warning("Speech to text went away (%s); reconnecting on the next words", exc)
                        await self._drop_stt()
        finally:
            reader.stop()
            if connecting is not None:
                connecting.cancel()

    def _spawn(self, coro: Any) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def _warm_model(self, now: float) -> None:
        if now - self._warmed_at < _MODEL_WARM_INTERVAL_S:
            return
        self._warmed_at = now
        self._spawn(self.providers.warm_up())

    def _check_barge_in(self, level: float, now: float) -> None:
        stage = self._barge.observe(level, now)
        if stage == "stop":
            self.speaker.duck_gain = 1.0
            self.speaker.stop_now = True
            self._barge_in = True
            self._replay_tail = True
            logger.info("You talked over Reachy; stopping the reply")
            self.events.publish("barge_in")
        else:
            self.speaker.duck_gain = _DUCK_GAIN if stage == "duck" else 1.0

    async def _send(self, frames: list[np.ndarray]) -> None:
        stt = self._stt
        if stt is None:
            return
        try:
            for frame in frames:
                await stt.send_audio(float_to_pcm16(frame))
        except Exception as exc:
            logger.warning("Speech to text went away (%s); reconnecting on the next words", exc)
            await self._drop_stt()

    def _attach_stt(self, session: SttSession) -> None:
        self._stt = session
        self._utterance = ""
        self._last_activity = time.monotonic()
        self._stt_reader = asyncio.create_task(self._read_stt(session), name="stt-reader")
        logger.info("Listening (speech to text connected)")

    async def _read_stt(self, session: SttSession) -> None:
        try:
            async for kind, text in session.events():
                if kind == "text":
                    self._utterance += text
                elif kind == "flushed" and self._utterance.strip():
                    text, self._utterance = self._utterance, ""
                    self._start_turn(text, spoken=True)
        except Exception as exc:
            logger.warning("Speech to text stopped: %s", exc)
        finally:
            if self._stt is session:
                self._stt = None
                self._stt_reader = None
                self._utterance = ""
                await session.close()

    async def _drop_stt(self) -> None:
        session, reader = self._stt, self._stt_reader
        self._stt = self._stt_reader = None
        self._utterance = ""
        if reader is not None and reader is not asyncio.current_task():
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        if session is not None:
            await session.close()

    async def _watch_idle(self) -> None:
        """Close speech to text after a quiet spell, so an idle Reachy costs nothing."""
        while True:
            await asyncio.sleep(2.0)
            idle = time.monotonic() - self._last_activity
            if (
                self._stt is not None and not self._gated and not self._turn_lock.locked()
                and (self.asleep or idle > self.settings.stt_idle_timeout_s)
            ):
                await self._drop_stt()
                logger.info("Quiet for a while; speech to text disconnected until someone talks")


def _log_failure(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error("A reply failed", exc_info=task.exception())


def _log_timing(heard_at: float, spoke_until: float | None, timing: dict[str, float]) -> None:
    sound = timing.get("first_sound")
    words = timing.get("first_words")
    if sound is None:
        return
    parts = [f"first sound {1000 * (sound - heard_at):.0f} ms after the turn started"]
    if words is not None:
        parts.append(f"model's first words at {1000 * (words - heard_at):.0f} ms")
    if spoke_until is not None:
        parts.insert(0, f"{1000 * (sound - spoke_until):.0f} ms from your last word to Reachy's voice")
    logger.info("Timing: %s", "; ".join(parts))
