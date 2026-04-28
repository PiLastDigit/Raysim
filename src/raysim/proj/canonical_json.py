"""Canonical JSON serialization — Phase A.6.

Bit-identical reproducibility requires a fixed serialization. Python's
``json`` with ``sort_keys=True`` handles key ordering, but float formatting
varies between platforms (and across Python releases) for edge cases.

This module emits floats with ``%.17g`` — the shortest round-trippable
representation for IEEE-754 double — and renders ``NaN``/``+Inf``/``-Inf``
as quoted strings (``"NaN"``/``"Infinity"``/``"-Infinity"``) rather than the
non-JSON literals stdlib emits by default. Engine output never produces
non-finite floats; the quoted-string fallback only protects against accidental
regressions and makes the output strictly RFC 8259 compliant.

Tuples are serialized as JSON arrays; this matches the engine's use of
``tuple`` for frozen sequences (see ``raysim.proj.schema``).

Inputs are dict/list/tuple/str/int/float/bool/None trees — generally produced
by ``BaseModel.model_dump()``. Pydantic ``BaseModel`` instances are accepted
and ``model_dump``ed automatically.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

_INDENT = "  "


def dumps(obj: Any, *, indent: bool = True) -> str:
    """Serialize ``obj`` to canonical JSON.

    With ``indent=True`` (default), nested objects/arrays are pretty-printed
    with a 2-space indent and sorted keys — the format ``run.json`` ships in.
    With ``indent=False``, output is dense (no whitespace) — used for hashing.
    """
    parts: list[str] = []
    _emit(_normalize(obj), parts, level=0, indent=indent)
    return "".join(parts)


def _normalize(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return _normalize(obj.model_dump())
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def _emit(obj: Any, parts: list[str], *, level: int, indent: bool) -> None:
    if obj is None:
        parts.append("null")
    elif isinstance(obj, bool):
        parts.append("true" if obj else "false")
    elif isinstance(obj, int):
        parts.append(str(obj))
    elif isinstance(obj, float):
        parts.append(_format_float(obj))
    elif isinstance(obj, str):
        parts.append(_format_string(obj))
    elif isinstance(obj, dict):
        _emit_dict(obj, parts, level=level, indent=indent)
    elif isinstance(obj, list):
        _emit_list(obj, parts, level=level, indent=indent)
    else:
        raise TypeError(f"canonical_json: unsupported type {type(obj).__name__}")


def _emit_dict(obj: dict[str, Any], parts: list[str], *, level: int, indent: bool) -> None:
    if not obj:
        parts.append("{}")
        return
    keys = sorted(obj.keys())
    if indent:
        parts.append("{\n")
        inner = _INDENT * (level + 1)
        for i, k in enumerate(keys):
            parts.append(inner)
            parts.append(_format_string(k))
            parts.append(": ")
            _emit(obj[k], parts, level=level + 1, indent=True)
            if i < len(keys) - 1:
                parts.append(",")
            parts.append("\n")
        parts.append(_INDENT * level)
        parts.append("}")
    else:
        parts.append("{")
        for i, k in enumerate(keys):
            if i:
                parts.append(",")
            parts.append(_format_string(k))
            parts.append(":")
            _emit(obj[k], parts, level=level + 1, indent=False)
        parts.append("}")


def _emit_list(obj: list[Any], parts: list[str], *, level: int, indent: bool) -> None:
    if not obj:
        parts.append("[]")
        return
    if indent:
        parts.append("[\n")
        inner = _INDENT * (level + 1)
        for i, v in enumerate(obj):
            parts.append(inner)
            _emit(v, parts, level=level + 1, indent=True)
            if i < len(obj) - 1:
                parts.append(",")
            parts.append("\n")
        parts.append(_INDENT * level)
        parts.append("]")
    else:
        parts.append("[")
        for i, v in enumerate(obj):
            if i:
                parts.append(",")
            _emit(v, parts, level=level + 1, indent=False)
        parts.append("]")


def _format_float(x: float) -> str:
    if math.isnan(x):
        return '"NaN"'
    if math.isinf(x):
        return '"Infinity"' if x > 0 else '"-Infinity"'
    # %.17g gives the shortest round-trippable form for IEEE-754 double.
    s = f"{x:.17g}"
    # Make integer-valued floats explicit ("1.0" not "1") so the JSON type round-trips.
    if "." not in s and "e" not in s and "E" not in s and "n" not in s:
        s += ".0"
    return s


def _format_string(s: str) -> str:
    # Restrict escape table to RFC 8259-required characters; otherwise use the
    # raw character (UTF-8). Stdlib's ``json.dumps(ensure_ascii=False)`` would
    # also work but its quoting differs subtly from ``%.17g``-style output.
    out = ['"']
    for ch in s:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)
