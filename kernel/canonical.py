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


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        canonicalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
