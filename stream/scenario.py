"""A named, versioned, seeded input generator for checkpoint runs.

The engine uses no runtime randomness. This module is the declared input side:
given a seed it produces the same genesis and the same proposals every time
(CPython's `random.Random` is stable across platforms for a fixed version). It
exercises everything the kernel has so far: claims, transfers, consumption,
reservations, completion and cancellation, plus enough invalid submissions
that the record shows denials with their reasons. It is exploration input, not
a world model: nothing here is a need, a place or a behaviour.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from kernel import Proposal, Source, WorldState

SCENARIO_NAME = "contention-and-holds"
SCENARIO_VERSION = "v3.scenario.contention-and-holds.1"


@dataclass(frozen=True)
class Scenario:
    seed: int
    actors: int = 6
    sources: int = 2
    starting_balance: int = 3
    source_stock: int = 60  # the second source holds half; nothing is produced, so every run eventually starves
    max_proposals_per_tick: int = 8

    def describe(self) -> dict[str, Any]:
        return {
            "name": SCENARIO_NAME, "version": SCENARIO_VERSION, "seed": self.seed,
            "actors": self.actors, "sources": self.sources,
            "starting_balance": self.starting_balance, "source_stock": self.source_stock,
            "max_proposals_per_tick": self.max_proposals_per_tick,
        }

    def actor_ids(self) -> list[str]:
        return [f"p{index + 1}" for index in range(self.actors)]

    def source_ids(self) -> list[str]:
        return [f"s{index + 1}" for index in range(self.sources)]

    def genesis(self) -> WorldState:
        """Every actor may claim from every source; sources alternate stock so
        contention differs between them."""
        actors = self.actor_ids()
        sources = {
            name: Source(self.source_stock if index % 2 == 0 else self.source_stock // 2, tuple(actors))
            for index, name in enumerate(self.source_ids())
        }
        return WorldState.genesis(balances={actor: self.starting_balance for actor in actors}, sources=sources)


class ProposalGenerator:
    """Stateful only in its seeded PRNG and in the reservation IDs it has seen."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.rng = random.Random(scenario.seed)
        self.actors = scenario.actor_ids()
        self.sources = scenario.source_ids()

    def tick(self, tick: int, live_actions: dict[str, str]) -> list[Proposal]:
        """Proposals for one tick. `live_actions` maps action ID to owner, from
        the previous committed state, so terminal requests can target real holds."""
        rng = self.rng
        proposals: list[Proposal] = []
        count = rng.randrange(0, self.scenario.max_proposals_per_tick + 1)
        orders: dict[str, int] = {}
        for index in range(count):
            actor = rng.choice(self.actors)
            order = orders.get(actor, 0)
            orders[actor] = order + 1
            if rng.random() < 0.04:  # a deliberate duplicate order, denied for both
                order = max(order - 1, 0)
            proposal_id = f"t{tick}-{index}"
            amount = rng.choice([1, 1, 1, 2, 2, 3])
            kind = rng.choices(
                ["claim", "transfer", "consume", "reserve", "close", "bad"],
                weights=[30, 20, 20, 15, 10, 5],
            )[0]
            if kind == "close":
                owned = [action for action, owner in live_actions.items() if owner == actor]
                if owned and rng.random() < 0.9:
                    action = rng.choice(sorted(owned))
                else:
                    action = rng.choice(sorted(live_actions) or ["action:none"])  # a foreign or stale ID
                operation = "complete" if rng.random() < 0.7 else "cancel"
                proposals.append(Proposal(proposal_id, actor, order, operation, {"action_id": action}))
                continue
            if kind == "bad":
                bad = rng.choice([
                    ("consume", {"amount": 0}), ("consume", {"amount": True}),
                    ("transfer", {"to": actor, "amount": 1}), ("transfer", {"to": "nobody", "amount": 1}),
                    ("claim", {"sources": {"missing": 1}}), ("dance", {"amount": 1}),
                ])
                proposals.append(Proposal(proposal_id, actor, order, bad[0], bad[1]))
                continue
            if kind in ("claim", "reserve") and (kind == "claim" or rng.random() < 0.5):
                chosen = rng.sample(self.sources, rng.randrange(1, len(self.sources) + 1))
                inner, params = "claim", {"sources": {source: amount for source in chosen}}
            elif kind == "transfer" or (kind == "reserve" and rng.random() < 0.5):
                target = rng.choice([other for other in self.actors if other != actor])
                inner, params = "transfer", {"to": target, "amount": amount}
            else:
                inner, params = "consume", {"amount": amount}
            if kind == "reserve":
                proposals.append(Proposal(proposal_id, actor, order, "reserve", {"operation": inner, "params": params}))
            else:
                proposals.append(Proposal(proposal_id, actor, order, inner, params))
        return proposals
