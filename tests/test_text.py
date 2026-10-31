import pytest

from everything_agent.conversation.sentences import SentenceSplitter
from everything_agent.conversation.turn_taking import end_of_turn_silence_s, looks_unfinished
from everything_agent.voice.language import detect_language


def split_all(chunks):
    splitter = SentenceSplitter()
    out = []
    for chunk in chunks:
        out += splitter.feed(chunk)
    tail = splitter.flush()
    return out + ([tail] if tail else [])


def test_sentences_come_out_as_soon_as_they_end():
    splitter = SentenceSplitter()
    assert splitter.feed("Hello there, my friend. How") == ["Hello there, my friend."]
    assert splitter.feed(" are you today? I'm") == ["How are you today?"]
    assert splitter.flush() == "I'm"


@pytest.mark.parametrize("text", [
    "It costs 3.50 dollars today.",
    "Ask Dr. Smith about it tomorrow.",
    "See example.com for the details.",
])
def test_dots_that_dont_end_a_sentence(text):
    assert split_all([text[:10], text[10:]]) == [text]


def test_short_fragments_merge_forward():
    assert split_all(["Oh. Okay then, let's start."]) == ["Oh. Okay then, let's start."]


def test_japanese_sentences_split_without_spaces():
    assert split_all(["こんにちは。元気ですか？はい"]) == ["こんにちは。", "元気ですか？", "はい"]


@pytest.mark.parametrize("text, unfinished", [
    ("I want to tell you about", True),
    ("so I went there and", True),
    ("hmm, let me think,", True),
    ("What's the time?", False),
    ("Tell me a joke", False),
    ("", False),
])
def test_unfinished_sentences_get_more_time(text, unfinished):
    assert looks_unfinished(text) is unfinished
    assert end_of_turn_silence_s(text, 700, 1600) == (1.6 if unfinished else 0.7)


@pytest.mark.parametrize("text, language", [
    ("Hello, how are you today?", "en"),
    ("नमस्ते, आप कैसे हैं?", "hi"),
    ("Bonjour, je suis content de vous voir.", "fr"),
    ("¿Qué hora es?", "es"),
    ("今日はいい天気ですね。", "ja"),
    ("Okay!", "en"),
])
def test_reply_language_for_the_voice(text, language):
    assert detect_language(text, fallback="en") == language


@pytest.mark.parametrize("text, spoken", [
    ("Did you know octopuses have **three** hearts? 🐙", "Did you know octopuses have three hearts?"),
    ("✨", ""),
    ("- First, preheat the oven.", "First, preheat the oven."),
    ("नमस्ते! 😊", "नमस्ते!"),
])
def test_what_the_voice_is_given(text, spoken):
    from everything_agent.conversation.sentences import speakable

    assert speakable(text) == spoken
