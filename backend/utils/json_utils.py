from __future__ import annotations

import json
from typing import Any


def to_pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def parse_json_from_text(raw_text: str) -> Any:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty JSON content")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = _unwrap_markdown_fence(text)
    if fenced != text:
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            text = fenced

    candidate = _extract_first_json_value(text)
    if candidate:
        return json.loads(candidate)

    raise ValueError("No valid JSON object found in model response")


def _unwrap_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped
    first_line = lines[0].strip().lower()
    if first_line not in {"```", "```json"}:
        return stripped
    if lines[-1].strip() != "```":
        return stripped
    return "\n".join(lines[1:-1]).strip()


def _extract_first_json_value(text: str) -> str:
    object_start = text.find("{")
    array_start = text.find("[")
    if object_start == -1 and array_start == -1:
        return ""

    if object_start == -1:
        start = array_start
    elif array_start == -1:
        start = object_start
    else:
        start = min(object_start, array_start)

    opening = text[start]
    closing = "}" if opening == "{" else "]"

    depth = 0
    in_string = False
    escaping = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaping:
                escaping = False
                continue
            if char == "\\":
                escaping = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == opening:
            depth += 1
            continue
        if char == closing:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return ""
