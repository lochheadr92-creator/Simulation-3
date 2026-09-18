"""World state, account addressing, and the read-only views handed to observers.

State is immutable. A tick does not edit a world; it produces the next one. That
is what makes observation inert: a view or a state taken earlier keeps reporting
what it reported, because the object it points at is never written to again.

Three account kinds exist. `actor:<id>` is an actor's exclusive holding.
`source:<id>` is a shared source with a declared set of authorised claimants.
`sink:consumed` is the single declared consumption sink, which is credit only:
consumed units leave circulation but stay inside the conserved total, so loss
can never be confused with leakage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from kernel.canonical import digest as canonical_digest
from kernel.units import is_integer, is_valid_balance
from kernel.version import SCHEMA_VERSION

ACTOR_PREFIX = "actor:"
SOURCE_PREFIX = "source:"
SINK_ACCOUNT = "sink:consumed"


def actor_account(actor_id: str) -> str:
    return ACTOR_PREFIX + actor_id


def source_account(source_id: str) -> str:
    return SOURCE_PREFIX + source_id


def is_actor_account(account: str) -> bool:
    return account.startswith(ACTOR_PREFIX)


def is_source_account(account: str) -> bool:
    return account.startswith(SOURCE_PREFIX)


def actor_of(account: str) -> str:
    return account[len(ACTOR_PREFIX) :]


def source_of(account: str) -> str:
    return account[len(SOURCE_PREFIX) :]


@dataclass(frozen=True)
class Effect:
    """One signed movement against one account. Never applied on its own."""

    account: str
    delta: int

    def __post_init__(self) -> None:
        if not isinstance(self.account, str) or not self.account:
            raise ValueError("an effect needs a non-empty account address")
        if not is_integer(self.delta):
            raise ValueError(f"an effect delta must be an integer, got {self.delta!r}")

    def canonical(self) -> dict[str, Any]:
        return {"account": self.account, "delta": self.delta}


@dataclass(frozen=True)
class Source:
    """A shared source, claimable only by the actors named in `authorised`."""

    stock: int
    authorised: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not is_valid_balance(self.stock):
            raise ValueError(f"a source stock must be an integer of zero or more, got {self.stock!r}")
        authorised = frozenset(self.authorised)
        for actor_id in authorised:
            if not isinstance(actor_id, str) or not actor_id:
                raise ValueError("an authorised claimant needs a non-empty identity")
        object.__setattr__(self, "authorised", authorised)

    def permits(self, actor_id: str) -> bool:
        return actor_id in self.authorised

    def canonical(self) -> dict[str, Any]:
        return {"stock": self.stock, "authorised": sorted(self.authorised)}


@dataclass(frozen=True)
class SourceView:
    """What an observer is told about a source."""

    source_id: str
    stock: int
    authorised: tuple[str, ...]

    def permits(self, actor_id: str) -> bool:
        return actor_id in self.authorised


@dataclass(frozen=True)
class WorldView:
    """One actor's read-only view of the tick-start state.

    Slice 1a gives every actor the whole boundary, because there is no geometry
    or perception to bound it with yet. Stage 2 narrows this to a bounded view;
    the type exists now so that decisions are already taken against a frozen
    boundary rather than against live state.
    """

    actor: str
    tick: int
    balances: Mapping[str, int]
    sources: Mapping[str, SourceView]
    roster: tuple[str, ...]

    @property
    def own_balance(self) -> int:
        return self.balances[self.actor]


@dataclass(frozen=True)
class WorldState:
    """The whole canonical world at one tick boundary."""

    tick: int
    balances: Mapping[str, int]
    sources: Mapping[str, Source]
    consumed: int = 0

    def __post_init__(self) -> None:
        if not is_integer(self.tick) or self.tick < 0:
            raise ValueError(f"a tick must be an integer of zero or more, got {self.tick!r}")
        if not is_valid_balance(self.consumed):
            raise ValueError(f"the consumption sink must hold an integer of zero or more, got {self.consumed!r}")

        raw_balances = dict(self.balances)
        for actor_id in raw_balances:
            if not isinstance(actor_id, str) or not actor_id:
                raise ValueError("an actor needs a non-empty identity")
        balances = {actor_id: raw_balances[actor_id] for actor_id in sorted(raw_balances)}
        for actor_id, amount in balances.items():
            if not is_valid_balance(amount):
                raise ValueError(f"the balance of {actor_id!r} must be an integer of zero or more, got {amount!r}")

        raw_sources = dict(self.sources)
        for source_id in raw_sources:
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("a source needs a non-empty identity")
        sources = {source_id: raw_sources[source_id] for source_id in sorted(raw_sources)}
        for source_id, source in sources.items():
            if not isinstance(source, Source):
                raise ValueError(f"{source_id!r} is not a Source")

        object.__setattr__(self, "balances", MappingProxyType(balances))
        object.__setattr__(self, "sources", MappingProxyType(sources))

    @classmethod
    def genesis(
        cls,
        *,
        tick: int = 0,
        balances: Mapping[str, int] | None = None,
        sources: Mapping[str, Source] | None = None,
        consumed: int = 0,
    ) -> "WorldState":
        return cls(
            tick=tick,
            balances=dict(balances or {}),
            sources=dict(sources or {}),
            consumed=consumed,
        )

    @property
    def roster(self) -> tuple[str, ...]:
        """The tick-start actor identities, sorted."""
        return tuple(sorted(self.balances))

    def total(self) -> int:
        """The conserved total: everything held, everything in a source, everything consumed."""
        return (
            sum(self.balances.values())
            + sum(source.stock for source in self.sources.values())
            + self.consumed
        )

    def view_for(self, actor_id: str) -> WorldView:
        if actor_id not in self.balances:
            raise KeyError(f"no such actor: {actor_id!r}")
        return WorldView(
            actor=actor_id,
            tick=self.tick,
            balances=MappingProxyType(dict(self.balances)),
            sources=MappingProxyType(
                {
                    source_id: SourceView(
                        source_id=source_id,
                        stock=source.stock,
                        authorised=tuple(sorted(source.authorised)),
                    )
                    for source_id, source in self.sources.items()
                }
            ),
            roster=self.roster,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tick": self.tick,
            "balances": dict(self.balances),
            "sources": {source_id: source.canonical() for source_id, source in self.sources.items()},
            "consumed": self.consumed,
        }

    def digest(self) -> str:
        return canonical_digest(self.canonical())
