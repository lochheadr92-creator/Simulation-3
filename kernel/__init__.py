"""The V3 kernel, slice 1a.

Immutable state, validated proposals, deterministic resolution, atomic
settlement and immutable observation. There are no reservations, no multi-tick
actions, no replay platform, no needs, movement, memory, social behaviour,
construction, viewer, plugins or general scheduler here. Those belong to later
slices and stages.
"""

from __future__ import annotations

from kernel.canonical import CanonicalError, canonical_bytes, canonicalise, digest
from kernel.diagnostics import CollectingDiagnostics, DiagnosticsSink, NullDiagnostics
from kernel.engine import Engine
from kernel.ordering import actor_ranks, rotated_roster, sorted_roster
from kernel.outcomes import ProposalOutcome, TickRecord
from kernel.proposals import Proposal, claim, consume, transfer
from kernel.settlement import IntegrityError, Settlement, effects_are_balanced, settle
from kernel.state import Effect, Source, SourceView, WorldState, WorldView
from kernel.units import RESOURCE_UNIT
from kernel.version import ENGINE_VERSION, SCHEMA_VERSION

# Bound after the imports above have loaded every submodule, so that
# `from kernel import reasons` and friends resolve without a partial package.
from kernel import (  # noqa: E402
    canonical,
    diagnostics,
    engine,
    ordering,
    outcomes,
    proposals,
    reasons,
    settlement,
    state,
    units,
    version,
)

Reason = reasons

__all__ = [
    "CanonicalError",
    "CollectingDiagnostics",
    "DiagnosticsSink",
    "ENGINE_VERSION",
    "Effect",
    "Engine",
    "IntegrityError",
    "NullDiagnostics",
    "Proposal",
    "ProposalOutcome",
    "RESOURCE_UNIT",
    "Reason",
    "SCHEMA_VERSION",
    "Settlement",
    "Source",
    "SourceView",
    "TickRecord",
    "WorldState",
    "WorldView",
    "actor_ranks",
    "canonical",
    "canonical_bytes",
    "canonicalise",
    "claim",
    "consume",
    "diagnostics",
    "digest",
    "effects_are_balanced",
    "engine",
    "ordering",
    "outcomes",
    "proposals",
    "reasons",
    "rotated_roster",
    "settle",
    "settlement",
    "sorted_roster",
    "state",
    "transfer",
    "units",
    "version",
]
