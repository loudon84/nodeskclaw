from __future__ import annotations

import re

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render_prompt_template(template: str, values: dict) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"missing prompt variable: {key}")
        return str(values[key])

    return _VAR_RE.sub(_replace, template)


def map_rpa_output_to_input(output: dict, input_schema: dict) -> dict:
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    allowed = set(properties.keys()) if isinstance(properties, dict) else set()
    if not allowed and isinstance(input_schema, dict):
        allowed = {key for key in input_schema.keys() if isinstance(key, str)}
    mapped: dict = {}
    source = output if isinstance(output, dict) else {}
    for key in sorted(allowed):
        if key in source:
            mapped[key] = source[key]
    return mapped
