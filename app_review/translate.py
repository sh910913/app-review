"""Translate review text with Google's free endpoint.

The GET form of this endpoint is often rate-limited. POST still returns
Google's normal translation, with no API key.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request

LANGUAGES: dict[str, str] = {
    "zh-TW": "繁體中文",
    "zh-CN": "简体中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "pt": "Português",
    "vi": "Tiếng Việt",
    "th": "ไทย",
    "id": "Bahasa Indonesia",
    "it": "Italiano",
    "ru": "Русский",
    "ar": "العربية",
}

_MARKER = "\n⟦⟧\n"
_BATCH_CHARS = 3500
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_cache: dict[tuple[str, str], str] = {}
_cache_lock = threading.Lock()


class TranslateError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def translate_texts(texts: list[str], target: str) -> list[str]:
    if target not in LANGUAGES:
        raise TranslateError("unsupported")
    if len(texts) > 80:
        raise TranslateError("too_many")
    for text in texts:
        if len(text) > 5000:
            raise TranslateError("too_long")

    results: list[str | None] = [None] * len(texts)
    missing: list[int] = []
    with _cache_lock:
        for index, text in enumerate(texts):
            if not text:
                results[index] = ""
                continue
            cached = _cache.get((target, text))
            if cached is None:
                missing.append(index)
            else:
                results[index] = cached

    pending = [texts[index] for index in missing]
    translated = _translate_missing(pending, target)
    for index, value in zip(missing, translated, strict=True):
        results[index] = value
        with _cache_lock:
            _cache[(target, texts[index])] = value
    return [value or "" for value in results]


def translation_from_payload(payload: object) -> str:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise TranslateError("bad_format")
    parts: list[str] = []
    for chunk in payload[0]:
        if isinstance(chunk, list) and chunk and isinstance(chunk[0], str):
            parts.append(chunk[0])
    if not parts:
        raise TranslateError("empty")
    return "".join(parts)


def split_translation(translated: str, count: int) -> list[str] | None:
    parts = [part.strip() for part in translated.split("⟦⟧")]
    if len(parts) != count:
        return None
    return parts


def _translate_missing(texts: list[str], target: str) -> list[str]:
    if not texts:
        return []
    output: list[str] = []
    for batch in _batches(texts):
        cleaned = [_without_marker(text) for text in batch]
        try:
            joined = _request(_MARKER.join(cleaned), target)
        except TranslateError:
            output.extend(_request(text, target) for text in cleaned)
            continue
        parts = split_translation(joined, len(cleaned))
        if parts is None:
            output.extend(_request(text, target) for text in cleaned)
        else:
            output.extend(parts)
    return output


def _batches(texts: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    size = 0
    for text in texts:
        extra = len(text) + len(_MARKER)
        if current and size + extra > _BATCH_CHARS:
            batches.append(current)
            current = []
            size = 0
        current.append(text)
        size += extra
    if current:
        batches.append(current)
    return batches


def _without_marker(text: str) -> str:
    return text.replace("⟦⟧", "")


def _request(text: str, target: str) -> str:
    if not text:
        return ""
    body = urllib.parse.urlencode(
        [("client", "gtx"), ("sl", "auto"), ("tl", target), ("dt", "t"), ("q", text)]
    ).encode()
    request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single",
        data=body,
        headers={
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise TranslateError("busy") from error
        raise TranslateError("down") from error
    except urllib.error.URLError as error:
        raise TranslateError("unreachable") from error
    except json.JSONDecodeError as error:
        raise TranslateError("bad_format") from error
    return translation_from_payload(payload)
