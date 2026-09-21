"""Stage 2, first step (OD-009): a grid world on top of the kernel ledger.

The kernel stays the only authority over food units: claims, eating and
contention settle there and nothing here writes a balance. This package adds
what the kernel does not know about: where each person is, how hungry they
are, one renewable food source at a fixed place, and the world processes that
move people, advance hunger, let people die, and renew the source.

Ownership, in the order a tick runs (world/run.py):
  observe.py   the bounded tick-start view each person decides from
  decide.py    eligible candidates and the one live selection rule
  process.py   movement, hunger, death, renewal: rules applied after settlement
  config.py    the declared levers and the seeded, saved genesis
  overlay.py   the immutable world state beside the kernel state
  viewer.py    a map over time rendered from the run file alone
"""

from __future__ import annotations

from world.config import WorldConfig, genesis
from world.overlay import Overlay

__all__ = ["Overlay", "WorldConfig", "genesis"]
