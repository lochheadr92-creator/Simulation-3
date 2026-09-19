"""Canonical form and content identity.

Identity must not depend on incidental object order, wall-clock timing, or
platform-specific number formatting. Canonical bytes are therefore JSON with
sorted keys and no insignificant whitespace, over integers and strings only.
Floating-point values and booleans are refused rather than formatted, so no
number-formatting decision can ever reach a digest.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


class CanonicalError(TypeError):
    """A value has no canonical form and must not enter an identity."""


def canonicalise(value: Any) -> Any:
    """Return a JSON-safe copy of `value`, refusing anything without a canonical form."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        raise CanonicalError("booleans have no canonical form; the kernel carries integers")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise CanonicalError("floating point values have no canonical form")
    if isinstance(value, Mapping):
        canonical_map = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError(f"mapping keys must be strings, found {type(key).__name__}")
            canonical_map[key] = canonicalise(item)
        return canonical_map
    if isinstance(value, (list, tuple)):
        return [canonicalise(item) for item in value]
    raise CanonicalError(f"{type(value).__name__} has no canonical form")


def _integer_text(value: int) -> str:
    """Decimal JSON digits without the process-wide int-to-string limit."""
    negative = value < 0
    remaining = abs(value)
    chunks = []
    while remaining >= 1_000_000_000:
        remaining, chunk = divmod(remaining, 1_000_000_000)
        chunks.append(f"{chunk:09d}")
    return ("-" if negative else "") + str(remaining) + "".join(reversed(chunks))


def _encode(value: Any) -> str:
    """Encode the already validated canonical value with unchanged JSON syntax."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, int):
        return _integer_text(value)
    if isinstance(value, list):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    return "{" + ",".join(
        _encode(key) + ":" + _encode(value[key])
        for key in sorted(value)
    ) + "}"


def canonical_bytes(value: Any) -> bytes:
    return _encode(canonicalise(value)).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
