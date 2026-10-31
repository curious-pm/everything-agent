"""When the user has finished speaking."""

from __future__ import annotations

import re

_CONTINUERS = {
    "and", "or", "but", "so", "because", "cause", "then", "if", "when", "while", "that", "which",
    "who", "to", "for", "with", "of", "in", "on", "at", "from", "about", "the", "a", "an", "my",
    "your", "his", "her", "their", "our", "uh", "um", "uhm", "hmm", "like", "also", "plus",
    "actually", "basically", "means", "is", "are", "was", "will", "can", "should", "please",
}
_WORD = re.compile(r"[\w']+", re.UNICODE)


def looks_unfinished(text: str) -> bool:
    """Whether a transcript seems to stop mid-thought (trailing comma, "and", "uh"...)."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped[-1] in ",;:-–—" or stripped.endswith("..."):
        return True
    if stripped[-1] in ".?!।":
        return False
    words = _WORD.findall(stripped.lower())
    return bool(words) and words[-1] in _CONTINUERS


def end_of_turn_silence_s(text: str, finished_ms: int, unfinished_ms: int) -> float:
    return (unfinished_ms if looks_unfinished(text) else finished_ms) / 1000.0
