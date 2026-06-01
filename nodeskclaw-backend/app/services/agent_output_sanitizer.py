"""Utilities for removing model reasoning blocks from agent output."""

from __future__ import annotations

import re

_OPEN_TAG_RE = re.compile(r"<\s*think\b[^>]*>", re.IGNORECASE | re.DOTALL)
_CLOSE_TAG_RE = re.compile(r"</\s*think\s*>", re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(
    r"<\s*think\b[^>]*>.*?(?:</\s*think\s*>|$)",
    re.IGNORECASE | re.DOTALL,
)
_MAX_TAG_TAIL = 64


def strip_think_blocks(text: str) -> str:
    if not text:
        return text
    if not _OPEN_TAG_RE.search(text) and not _CLOSE_TAG_RE.search(text):
        return text

    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _CLOSE_TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()


def _partial_open_suffix(text: str) -> str:
    start = max(0, len(text) - _MAX_TAG_TAIL)
    for index in range(start, len(text)):
        suffix = text[index:]
        if _looks_like_partial_open_tag(suffix):
            return suffix
    return ""


def _looks_like_partial_open_tag(suffix: str) -> bool:
    if not suffix.startswith("<") or ">" in suffix:
        return False

    body = suffix[1:].lstrip().lower()
    if not body:
        return True
    if "think".startswith(body):
        return True
    if body.startswith("think"):
        if len(body) == len("think"):
            return True
        return not (body[len("think")].isalnum() or body[len("think")] in "_-")
    return False


class ThinkBlockStreamSanitizer:
    def __init__(self) -> None:
        self._buffer = ""
        self._inside_think = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buffer += chunk
        return self._drain(final=False)

    def flush(self) -> str:
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> str:
        output: list[str] = []

        while self._buffer:
            if self._inside_think:
                close_match = _CLOSE_TAG_RE.search(self._buffer)
                if not close_match:
                    if final:
                        self._buffer = ""
                        self._inside_think = False
                    else:
                        self._buffer = self._buffer[-_MAX_TAG_TAIL:]
                    break
                self._buffer = self._buffer[close_match.end():]
                self._inside_think = False
                continue

            open_match = _OPEN_TAG_RE.search(self._buffer)
            if open_match:
                output.append(self._buffer[:open_match.start()])
                self._buffer = self._buffer[open_match.end():]
                self._inside_think = True
                continue

            keep = _partial_open_suffix(self._buffer)
            if keep:
                output.append(self._buffer[:-len(keep)])
                self._buffer = "" if final else keep
            else:
                output.append(self._buffer)
                self._buffer = ""
            break

        return "".join(output)
