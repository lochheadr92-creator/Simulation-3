"""Deterministic integer draws from a seed and a few named parts.

Anything that must look random but may never differ between a run, its replay and a
recovery draws from here: the same parts always give the same integer, on every
platform, with no generator state to save or lose.
"""

from __future__ import annotations

import hashlib


def draw(*parts: object) -> int:
    """A large non-negative integer fixed by `parts`. Use `% n` to choose among n."""
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")
