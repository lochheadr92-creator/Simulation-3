"""What a named optional feature is: what it needs, its settings, and its rule text.

A feature is off unless a configuration lists it. Each module that owns a feature
declares it here-shaped, next to the code that implements it, so the rule text in
a run header and the behaviour cannot drift apart without somebody seeing both.
`world/registry.py` collects them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Feature:
    name: str
    summary: str                                   # one plain sentence, shown in the viewer
    rule: str                                      # how it works, written to the run header when on
    needs: tuple[str, ...] = ()                    # other features that must also be on
    levers: tuple[tuple[str, int], ...] = ()       # integer settings and their defaults
    tables: dict[str, Any] = field(default_factory=dict)   # declared names and thresholds the viewer reads from the header
