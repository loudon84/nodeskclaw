"""Legacy YAML subset loader/dumper (mappings, lists, scalars).

v2.1.6: Production Managed Config serialization uses PyYAML safe_dump.
This module remains a compatibility reader/helper and quoting hotfix for
legacy paths; it is not the Release Config Validity Oracle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# YAML plain-scalar characters that cannot start an unquoted token (FR-216-01).
_PLAIN_SCALAR_FORBIDDEN_START = frozenset("?-:,[]{}#&*!|>'\"%@`")


def load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    value, _ = _parse_block(lines, 0, 0)
    if value is None:
        raise ValueError(f"empty yaml: {path}")
    return value


def dump_yaml(data: Any) -> str:
    """Legacy deterministic YAML subset: sorted map keys, stable 2-space indent.

    Prefer yaml.safe_dump for production managed.defaults.yaml writes.
    """
    lines: list[str] = []
    _dump_value(data, lines, indent=0, inline_empty=False)
    return "\n".join(lines) + "\n"


def _dump_value(value: Any, lines: list[str], *, indent: int, inline_empty: bool) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            if inline_empty and lines:
                lines[-1] = lines[-1] + " {}"
            else:
                lines.append(f"{prefix}{{}}")
            return
        for key in sorted(value.keys(), key=lambda item: str(item)):
            child = value[key]
            key_text = str(key)
            if isinstance(child, dict) and not child:
                lines.append(f"{prefix}{key_text}: {{}}")
            elif isinstance(child, list) and not child:
                lines.append(f"{prefix}{key_text}: []")
            elif isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key_text}:")
                _dump_value(child, lines, indent=indent + 2, inline_empty=True)
            else:
                lines.append(f"{prefix}{key_text}: {_format_scalar(child)}")
        return
    if isinstance(value, list):
        if not value:
            if inline_empty and lines:
                lines[-1] = lines[-1] + " []"
            else:
                lines.append(f"{prefix}[]")
            return
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                _dump_value(item, lines, indent=indent + 2, inline_empty=True)
            else:
                lines.append(f"{prefix}- {_format_scalar(item)}")
        return
    lines.append(f"{prefix}{_format_scalar(value)}")


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(value)
    text = str(value)
    if _needs_quotes(text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _needs_quotes(text: str) -> bool:
    """Return True when a string must be a quoted YAML scalar (FR-216-01)."""
    if text == "":
        return True
    if text.lower() in {"true", "false", "null", "~", "yes", "no", "on", "off"}:
        return True
    if any(ord(ch) < 32 for ch in text):
        return True
    if text[0] in _PLAIN_SCALAR_FORBIDDEN_START or text.startswith((" ", "-")):
        return True
    if text.endswith(" "):
        return True
    # Flow / comment / mapping delimiters anywhere in the token.
    if any(ch in text for ch in (":", "#", "{", "}", "[", "]", ",", '"', "'", "\\", "@", "`", "%", "&", "*", "!")):
        return True
    if "\\" in text or ("/" in text and (":" in text or text.startswith("/"))):
        return True
    if text.startswith("C:\\") or "\\\\" in text or ":\\" in text:
        return True
    if "${" in text:
        return True
    try:
        float(text)
        return True
    except ValueError:
        return False


def _needs_quotes_pre_v216(text: str) -> bool:
    """Pre-v2.1.6 quoting (missing @ and related prefixes) — for RED regression only."""
    if text == "":
        return True
    if text.lower() in {"true", "false", "null", "~"}:
        return True
    if any(ch in text for ch in (":", "#", "{", "}", "[", "]", ",", '"', "'", "\\", "\n", "\r")):
        return True
    if text.startswith((" ", "-", "?")) or text.endswith(" "):
        return True
    if "\\" in text or ("/" in text and (":" in text or text.startswith("/"))):
        return True
    if text.startswith("C:\\") or "\\\\" in text or ":\\" in text:
        return True
    try:
        float(text)
        return True
    except ValueError:
        return False


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[Any, int]:
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current = _indent(raw)
        if current < indent:
            return None, index
        stripped = raw.strip()
        if stripped.startswith("- "):
            return _parse_list(lines, index, current)
        if ":" in stripped:
            return _parse_map(lines, index, current)
        return _parse_scalar(stripped), index + 1
    return None, index


def _parse_map(lines: list[str], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current = _indent(raw)
        if current < indent:
            break
        if current > indent:
            raise ValueError(f"unexpected indent: {raw}")
        stripped = raw.strip()
        if stripped.startswith("- "):
            break
        if ":" not in stripped:
            raise ValueError(f"expected mapping: {raw}")
        key, rest = stripped.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest:
            result[key] = _parse_scalar(rest)
            continue
        value, index = _parse_block(lines, index, indent + 2)
        result[key] = {} if value is None else value
    return result, index


def _parse_list(lines: list[str], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current = _indent(raw)
        if current < indent:
            break
        stripped = raw.strip()
        if not stripped.startswith("- "):
            break
        item = stripped[2:].strip()
        index += 1
        if not item:
            value, index = _parse_block(lines, index, indent + 2)
            result.append({} if value is None else value)
            continue
        if item.endswith(":") or (":" in item and not item.startswith(("'", '"'))):
            key, rest = item.split(":", 1)
            nested: dict[str, Any] = {key.strip(): _parse_scalar(rest.strip()) if rest.strip() else {}}
            child, index = _parse_map_continuation(lines, index, indent + 2, nested)
            result.append(child)
            continue
        result.append(_parse_scalar(item))
    return result, index


def _parse_map_continuation(
    lines: list[str], index: int, indent: int, seed: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    extra, index = _parse_map(lines, index, indent)
    seed.update(extra)
    return seed, index


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_scalar(text: str) -> Any:
    if text in ("", "~", "null"):
        return None
    if text in ("{}",):
        return {}
    if text in ("[]",):
        return []
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        inner = text[1:-1]
        if text[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text
