"""The tick loop: freeze the boundary, settle, commit, publish.

The engine holds the current state and nothing else. It hands settlement a
frozen boundary, replaces its state with the one settlement produced, and only
then reaches the optional diagnostics channel. Nothing a sink does can reach a
decision, because by the time it is called every decision is already committed.
"""

from __future__ import annotations

from collections.abc import Iterable

from kernel.diagnostics import DiagnosticsSink
from kernel.outcomes import TickRecord
from kernel.proposals import Proposal
from kernel.settlement import settle
from kernel.state import WorldState, WorldView


class Engine:
    def __init__(self, state: WorldState, diagnostics: DiagnosticsSink | None = None) -> None:
        if not isinstance(state, WorldState):
            raise TypeError(f"an engine needs a WorldState, got {type(state).__name__}")
        self._state = state
        self._diagnostics = diagnostics
        self._diagnostics_failures = 0

    @property
    def state(self) -> WorldState:
        """The current tick-start state. Immutable, and replaced rather than edited."""
        return self._state

    @property
    def diagnostics_failures(self) -> int:
        """How often the optional sink raised. Counted rather than hidden."""
        return self._diagnostics_failures

    def view_for(self, actor_id: str) -> WorldView:
        return self._state.view_for(actor_id)

    def tick(self, proposals: Iterable[Proposal] = ()) -> TickRecord:
        boundary = self._state
        settlement = settle(boundary, proposals)
        record = TickRecord(
            tick=boundary.tick,
            prior_state_digest=boundary.digest(),
            next_state_digest=settlement.next_state.digest(),
            rotated_roster=settlement.rotated_roster,
            outcomes=settlement.outcomes,
        )
        self._state = settlement.next_state
        self._publish(record)
        return record

    def _publish(self, record: TickRecord) -> None:
        sink = self._diagnostics
        if sink is None:
            return
        try:
            sink.record("tick", record.canonical())
        except Exception:
            # A diagnostics failure must not change canonical history, and must
            # not be silent either.
            self._diagnostics_failures += 1
