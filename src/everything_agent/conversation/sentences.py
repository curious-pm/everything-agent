"""Splits a streamed reply into sentences, so Reachy starts speaking before the reply is complete."""

from __future__ import annotations

import re
import unicodedata

_MIN_CHARS = 12
_BOUNDARIES = ".!?…。！？"
_CJK_BOUNDARIES = "。！？"
_ABBREVIATIONS = frozenset({
    "dr", "mr", "mrs", "ms", "prof", "st", "vs", "etc", "approx", "e.g", "i.e", "u.s", "a.m", "p.m",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
})


def _word_before(text: str, i: int) -> str:
    """The run of letters and dots just before index ``i``, e.g. "Dr" or "U.S"."""
    k = i
    while k > 0 and (text[k - 1].isalpha() or text[k - 1] == "."):
        k -= 1
    return text[k:i]


class SentenceSplitter:
    def __init__(self) -> None:
        self._buf = ""

    def _can_split(self, i: int, j: int) -> bool:
        """Whether ``buf[i:j]`` ends a sentence; decimals, URLs and abbreviations don't."""
        buf = self._buf
        if not all(c == "." for c in buf[i:j]):
            return True
        before = buf[i - 1] if i > 0 else ""
        after = buf[j]
        if before.isdigit() or after.isdigit() or not after.isspace():
            return False
        return _word_before(buf, i).lower() not in _ABBREVIATIONS

    def feed(self, text: str) -> list[str]:
        """Complete sentences found so far; the rest waits for more text."""
        self._buf += text
        buf = self._buf
        sentences: list[str] = []
        start = i = 0
        while i < len(buf):
            if buf[i] not in _BOUNDARIES:
                i += 1
                continue
            j = i + 1
            while j < len(buf) and buf[j] in _BOUNDARIES:
                j += 1
            if j < len(buf) and self._can_split(i, j):
                sentence = buf[start:j].strip()
                if sentence and (buf[j - 1] in _CJK_BOUNDARIES or len(sentence) >= _MIN_CHARS):
                    sentences.append(sentence)
                    start = j
            i = j
        self._buf = buf[start:]
        return sentences

    def flush(self) -> str | None:
        tail, self._buf = self._buf.strip(), ""
        return tail or None


_EMOJI_JOINERS = {chr(0xFE0F), chr(0x200D)}
_MARKUP = re.compile(r"[*_`#>|~]+|^\s*[-•]\s+", re.MULTILINE)


def speakable(text: str) -> str:
    """The sentence without emoji or markdown symbols; "" if nothing sayable is left."""
    kept = "".join(c for c in text if unicodedata.category(c) not in ("So", "Cs", "Co") and c not in _EMOJI_JOINERS)
    kept = " ".join(_MARKUP.sub(" ", kept).split())
    return kept if any(c.isalnum() for c in kept) else ""
