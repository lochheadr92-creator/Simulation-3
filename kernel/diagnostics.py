"""The optional, inert diagnostics channel.

Settlement cannot import this module, and the engine only reaches it after a
tick's canonical results are already fixed and committed. A sink is handed a
fresh canonical copy, returns nothing the engine reads, and cannot reach any
live object. Optional capture therefore cannot change canonical history.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from kernel.canonical import canonical_bytes


class DiagnosticsSink(Protocol):
    def record(self, event: str, payload: Mapping[str, Any]) -> None: ...


class NullDiagnostics:
    """Discards everything. The default behaviour, written down."""

    def record(self, event: str, payload: Mapping[str, Any]) -> None:
        return None


class CollectingDiagnostics:
    """Keeps the canonical bytes of what it was handed. For inspection and tests."""

    def __init__(self) -> None:
        self.events: list[tuple[str, bytes]] = []

    def record(self, event: str, payload: Mapping[str, Any]) -> None:
        self.events.append((event, canonical_bytes(payload)))
