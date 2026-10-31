"""Guess the language of a reply so the TTS voice pronounces it correctly."""

from __future__ import annotations

import re
import unicodedata

TTS_LANGUAGES = frozenset(
    "en de es fr ja pt zh hi ko it nl pl ru sv tr tl bg ro ar cs el fi hr ms sk da ta uk "
    "hu no vi bn th he ka id te gu kn ml mr pa".split()
)

_SCRIPTS = (
    ("HIRAGANA", "ja"), ("KATAKANA", "ja"), ("HANGUL", "ko"), ("CJK", "zh"),
    ("DEVANAGARI", "hi"), ("BENGALI", "bn"), ("GURMUKHI", "pa"), ("GUJARATI", "gu"),
    ("TAMIL", "ta"), ("TELUGU", "te"), ("KANNADA", "kn"), ("MALAYALAM", "ml"),
    ("THAI", "th"), ("HEBREW", "he"), ("GEORGIAN", "ka"), ("ARABIC", "ar"),
    ("GREEK", "el"), ("CYRILLIC", "ru"),
)

_MARATHI_WORDS = {"आहे", "आहेत", "आणि", "नाही", "मला", "तुम्ही", "काय", "होते", "पण"}

_LATIN_WORDS: dict[str, set[str]] = {
    "en": {"the", "and", "is", "are", "you", "to", "of", "it", "that", "what", "this", "i", "can", "with", "have", "do"},
    "es": {"el", "la", "los", "las", "es", "que", "y", "de", "en", "un", "una", "por", "para", "con", "hola", "gracias", "está", "puedo"},
    "fr": {"le", "la", "les", "est", "et", "je", "vous", "tu", "une", "des", "pour", "avec", "pas", "bonjour", "merci", "c'est", "oui"},
    "de": {"der", "die", "das", "und", "ist", "ich", "nicht", "sie", "ein", "eine", "mit", "auf", "für", "hallo", "danke", "ja", "du"},
    "pt": {"o", "os", "as", "é", "que", "e", "não", "um", "uma", "para", "com", "você", "olá", "obrigado", "obrigada", "sim", "está"},
    "it": {"il", "lo", "gli", "è", "che", "e", "non", "un", "una", "per", "con", "sono", "ciao", "grazie", "sì", "della"},
    "nl": {"de", "het", "een", "en", "is", "niet", "ik", "je", "dat", "van", "met", "voor", "hallo", "dank", "ja"},
    "sv": {"och", "är", "jag", "inte", "det", "en", "ett", "att", "med", "för", "hej", "tack", "ja", "du"},
    "da": {"og", "er", "jeg", "ikke", "det", "en", "et", "at", "med", "for", "hej", "tak", "du"},
    "no": {"og", "er", "jeg", "ikke", "det", "en", "et", "å", "med", "for", "hei", "takk", "du"},
    "pl": {"i", "jest", "nie", "to", "się", "na", "że", "w", "z", "dzień", "dobry", "dziękuję", "tak", "czy"},
    "cs": {"a", "je", "není", "to", "se", "na", "že", "v", "s", "dobrý", "děkuji", "ano", "jak"},
    "sk": {"a", "je", "nie", "to", "sa", "na", "že", "v", "s", "dobrý", "ďakujem", "áno", "ako"},
    "ro": {"și", "este", "nu", "eu", "un", "o", "pentru", "cu", "bună", "mulțumesc", "da", "ce"},
    "hu": {"a", "az", "és", "nem", "van", "egy", "hogy", "igen", "köszönöm", "szia", "mit"},
    "fi": {"ja", "on", "ei", "minä", "sinä", "se", "että", "kiitos", "hei", "mitä", "kyllä"},
    "tr": {"ve", "bir", "bu", "değil", "ben", "sen", "için", "ile", "merhaba", "teşekkürler", "evet", "ne"},
    "id": {"dan", "yang", "ini", "itu", "tidak", "saya", "anda", "untuk", "dengan", "terima", "kasih", "ya", "apa"},
    "ms": {"dan", "yang", "ini", "itu", "tidak", "saya", "awak", "untuk", "dengan", "terima", "kasih", "ya", "apa"},
    "tl": {"ang", "ng", "sa", "na", "ako", "ikaw", "ito", "hindi", "salamat", "oo", "po", "mga"},
    "hr": {"i", "je", "nije", "to", "se", "na", "da", "u", "s", "hvala", "bok", "što"},
    "vi": {"và", "là", "không", "tôi", "bạn", "của", "có", "cảm", "ơn", "xin", "chào"},
}

_LATIN_LETTERS = {
    "ñ": "es", "¿": "es", "¡": "es", "ß": "de", "ã": "pt", "õ": "pt", "ł": "pl", "ą": "pl",
    "ę": "pl", "ś": "pl", "ź": "pl", "ż": "pl", "ř": "cs", "ě": "cs", "ů": "cs", "ğ": "tr",
    "ş": "tr", "ı": "tr", "ő": "hu", "ű": "hu", "ă": "ro", "ș": "ro", "ț": "ro", "ø": "no",
    "æ": "da", "đ": "vi", "ơ": "vi", "ư": "vi",
}

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)


def _script_language(text: str) -> str | None:
    counts: dict[str, int] = {}
    for char in text:
        if not char.isalpha() or char.isascii():
            continue
        name = unicodedata.name(char, "")
        for prefix, language in _SCRIPTS:
            if name.startswith(prefix):
                counts[language] = counts.get(language, 0) + 1
                break
    if not counts:
        return None
    if counts.get("ja"):
        return "ja"
    best = max(counts, key=counts.get)
    if best == "hi" and _MARATHI_WORDS & set(text.split()):
        return "mr"
    if best == "ru":
        if any(c in text for c in "іїєґІЇЄҐ"):
            return "uk"
        if "ъ" in text and not any(c in text for c in "ыэЫЭ"):
            return "bg"
    return best


def _latin_language(text: str) -> str | None:
    lowered = text.lower()
    words = _WORD.findall(lowered)
    if not words:
        return None
    scores = {language: sum(word in vocab for word in words) for language, vocab in _LATIN_WORDS.items()}
    for letter, language in _LATIN_LETTERS.items():
        if letter in lowered:
            scores[language] += 2
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def detect_language(text: str, fallback: str = "en") -> str:
    """Best guess at the language of *text*, limited to what the TTS can speak."""
    guess = _script_language(text) or _latin_language(text)
    return guess if guess in TTS_LANGUAGES else fallback
