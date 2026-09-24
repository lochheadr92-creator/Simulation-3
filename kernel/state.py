"""World state, account addressing, and the read-only views handed to observers.

State is immutable. A tick does not edit a world; it produces the next one. That
is what makes observation inert: a view or a state taken earlier keeps reporting
what it reported, because the object it points at is never written to again.

Three account kinds exist. `actor:<id>` is an actor's exclusive holding.
`source:<id>` is a shared source with a declared set of authorised claimants.
`sink:consumed` is the single declared consumption sink, which is credit only:
consumed units leave circulation but stay inside the conserved total, so loss
can never be confused with leakage.

Named resources (2026-09-25) sit beside that base resource. A world declares
them in `holdings` (every actor's amount of each) and `consumed_by` (one sink
each). Their accounts are `actor@<resource>:<id>` and `sink@<resource>:consumed`,
and a Source says which resource it holds. A world that declares none has
exactly the canonical form it had before.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from kernel.canonical import digest as canonical_digest
from kernel.units import is_integer, is_valid_balance
from kernel.version import SCHEMA_VERSION

ACTOR_PREFIX = "actor:"
SOURCE_PREFIX = "source:"
SINK_ACCOUNT = "sink:consumed"
NAMED_ACTOR_PREFIX = "actor@"
NAMED_SINK_PREFIX = "sink@"
_RESOURCE_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


def is_resource_name(name: Any) -> bool:
    """A named resource: lower-case letters, digits and underscores, starting
    with a letter, at most 32 characters. The base resource has no name (None)."""
    return isinstance(name, str) and _RESOURCE_NAME.match(name) is not None


def actor_account(actor_id: str, resource: str | None = None) -> str:
    """`actor:<id>` holds the base resource; `actor@<resource>:<id>` a named one."""
    if resource is None:
        return ACTOR_PREFIX + actor_id
    return f"{NAMED_ACTOR_PREFIX}{resource}:{actor_id}"


def sink_account(resource: str | None = None) -> str:
    return SINK_ACCOUNT if resource is None else f"{NAMED_SINK_PREFIX}{resource}:consumed"


def source_account(source_id: str) -> str:
    return SOURCE_PREFIX + source_id


def _named_parts(account: str, prefix: str) -> tuple[str, str] | None:
    """(resource, rest) for `<prefix><resource>:<rest>`, else None."""
    if not account.startswith(prefix):
        return None
    resource, colon, rest = account[len(prefix):].partition(":")
    if not colon or not is_resource_name(resource):
        return None
    return resource, rest


def is_actor_account(account: str) -> bool:
    return account.startswith(ACTOR_PREFIX) or _named_parts(account, NAMED_ACTOR_PREFIX) is not None


def is_sink_account(account: str) -> bool:
    if account == SINK_ACCOUNT:
        return True
    parts = _named_parts(account, NAMED_SINK_PREFIX)
    return parts is not None and parts[1] == "consumed"


def is_source_account(account: str) -> bool:
    return account.startswith(SOURCE_PREFIX)


def actor_of(account: str) -> str:
    if account.startswith(ACTOR_PREFIX):
        return account[len(ACTOR_PREFIX):]
    parts = _named_parts(account, NAMED_ACTOR_PREFIX)
    if parts is None:
        raise ValueError(f"not an actor account: {account!r}")
    return parts[1]


def resource_of(account: str) -> str | None:
    """The named resource of an actor or sink account; None for the base
    resource. A source account's resource is its Source's, not in the name."""
    for prefix in (NAMED_ACTOR_PREFIX, NAMED_SINK_PREFIX):
        parts = _named_parts(account, prefix)
        if parts is not None:
            return parts[0]
    return None


def source_of(account: str) -> str:
    return account[len(SOURCE_PREFIX) :]


def _canonical_map(data: Any, keys: frozenset[str], what: str) -> Mapping[str, Any]:
    """Refuse anything but a mapping with exactly the canonical keys of `what`.

    The `from_canonical` constructors below rebuild objects from stored
    canonical forms (slice 1c: replay, recovery, restored instances). They
    add no rule of their own: they check the shape, then build through the
    ordinary constructors, so the same rails guard a restored object as a
    live one.
    """
    if not isinstance(data, Mapping) or set(data) != keys:
        raise ValueError(f"a canonical {what} needs exactly the keys {sorted(keys)}")
    return data


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

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Effect":
        data = _canonical_map(data, frozenset({"account", "delta"}), "effect")
        return cls(account=data["account"], delta=data["delta"])


@dataclass(frozen=True)
class Source:
    """A shared source, claimable only by the actors named in `authorised`."""

    stock: int
    authorised: frozenset[str] = frozenset()
    resource: str | None = None          # None: the base resource

    def __post_init__(self) -> None:
        if not is_valid_balance(self.stock):
            raise ValueError(f"a source stock must be an integer of zero or more, got {self.stock!r}")
        if self.resource is not None and not is_resource_name(self.resource):
            raise ValueError(f"a source resource needs a valid name, got {self.resource!r}")
        authorised = frozenset(self.authorised)
        for actor_id in authorised:
            if not isinstance(actor_id, str) or not actor_id:
                raise ValueError("an authorised claimant needs a non-empty identity")
        object.__setattr__(self, "authorised", authorised)

    def permits(self, actor_id: str) -> bool:
        return actor_id in self.authorised

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {"stock": self.stock, "authorised": sorted(self.authorised)}
        if self.resource is not None:
            out["resource"] = self.resource
        return out

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Source":
        named = isinstance(data, Mapping) and "resource" in data
        data = _canonical_map(data, frozenset({"stock", "authorised"} | ({"resource"} if named else set())), "source")
        if named and not is_resource_name(data["resource"]):
            raise ValueError("a canonical source names its resource or omits it")
        authorised = data["authorised"]
        if not isinstance(authorised, (list, tuple)) or any(not isinstance(actor_id, str) for actor_id in authorised):
            raise ValueError("a canonical source needs a list of claimant identities")
        if list(authorised) != sorted(set(authorised)):
            raise ValueError("a canonical source lists its claimants sorted and once each")
        return cls(stock=data["stock"], authorised=frozenset(authorised), resource=data.get("resource"))


@dataclass(frozen=True)
class SourceView:
    """What an observer is told about a source."""

    source_id: str
    stock: int
    authorised: tuple[str, ...]
    reserved: int = 0
    resource: str | None = None

    @property
    def available_stock(self) -> int:
        return self.stock - self.reserved

    def permits(self, actor_id: str) -> bool:
        return actor_id in self.authorised


@dataclass(frozen=True)
class Reservation:
    """A frozen balanced plan; its debits are held inside existing accounts."""

    action_id: str
    actor: str
    created_tick: int
    operation: str
    effects: tuple[Effect, ...]

    def __post_init__(self) -> None:
        for value in (self.action_id, self.actor, self.operation):
            if not isinstance(value, str) or not value:
                raise ValueError("a reservation needs non-empty identities and operation")
        if not is_integer(self.created_tick) or self.created_tick < 0:
            raise ValueError("a reservation creation tick must be a nonnegative integer")
        effects = tuple(self.effects)
        if not effects or any(not isinstance(effect, Effect) for effect in effects):
            raise ValueError("a reservation needs effects")
        if sum(effect.delta for effect in effects) != 0 or not any(effect.delta < 0 for effect in effects):
            raise ValueError("a reservation needs a balanced plan with debits")
        object.__setattr__(self, "effects", tuple(sorted(effects, key=lambda e: (e.account, e.delta))))

    def held(self) -> dict[str, int]:
        amounts: dict[str, int] = {}
        for effect in self.effects:
            if effect.delta < 0:
                amounts[effect.account] = amounts.get(effect.account, 0) - effect.delta
        return amounts

    def canonical(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id, "actor": self.actor,
            "created_tick": self.created_tick, "operation": self.operation,
            "effects": [effect.canonical() for effect in self.effects],
        }

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "Reservation":
        data = _canonical_map(
            data, frozenset({"action_id", "actor", "created_tick", "operation", "effects"}), "reservation")
        effects = data["effects"]
        if not isinstance(effects, (list, tuple)):
            raise ValueError("a canonical reservation needs a list of effects")
        return cls(action_id=data["action_id"], actor=data["actor"], created_tick=data["created_tick"],
                   operation=data["operation"], effects=tuple(Effect.from_canonical(effect) for effect in effects))


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
    reservations: Mapping[str, Reservation] = field(default_factory=lambda: MappingProxyType({}))
    holdings: Mapping[str, Mapping[str, int]] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def own_balance(self) -> int:
        return self.balances[self.actor]

    def own_available_of(self, resource: str | None = None) -> int:
        """Free units of one resource: holding minus this actor's own holds."""
        held = self.balances[self.actor] if resource is None else self.holdings[resource][self.actor]
        account = actor_account(self.actor, resource)
        return held - sum(reservation.held().get(account, 0) for reservation in self.reservations.values())

    @property
    def own_available(self) -> int:
        return self.own_balance - sum(
            reservation.held().get(actor_account(self.actor), 0)
            for reservation in self.reservations.values()
        )


@dataclass(frozen=True)
class WorldState:
    """The whole canonical world at one tick boundary."""

    tick: int
    balances: Mapping[str, int]
    sources: Mapping[str, Source]
    consumed: int = 0
    reservations: Mapping[str, Reservation] = field(default_factory=dict)
    holdings: Mapping[str, Mapping[str, int]] = field(default_factory=dict)   # named resource -> actor -> units
    consumed_by: Mapping[str, int] = field(default_factory=dict)             # named resource -> consumed units

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

        raw_holdings = dict(self.holdings)
        holdings: dict[str, Mapping[str, int]] = {}
        for resource in raw_holdings:
            if not is_resource_name(resource):
                raise ValueError(f"a named resource needs a valid name, got {resource!r}")
        for resource in sorted(raw_holdings):
            amounts = dict(raw_holdings[resource])
            if set(amounts) != set(balances):
                raise ValueError(f"holdings of {resource!r} must name exactly the actors")
            for actor_id, amount in amounts.items():
                if not is_valid_balance(amount):
                    raise ValueError(f"{actor_id!r} holds an invalid amount of {resource!r}: {amount!r}")
            holdings[resource] = MappingProxyType({actor_id: amounts[actor_id] for actor_id in sorted(amounts)})
        consumed_by = dict(self.consumed_by)
        if set(consumed_by) != set(holdings):
            raise ValueError("every named resource needs exactly one consumption sink")
        for resource, amount in consumed_by.items():
            if not is_valid_balance(amount):
                raise ValueError(f"the {resource!r} sink must hold an integer of zero or more, got {amount!r}")
        for source_id, source in sources.items():
            if source.resource is not None and source.resource not in holdings:
                raise ValueError(f"source {source_id!r} holds an undeclared resource {source.resource!r}")

        object.__setattr__(self, "balances", MappingProxyType(balances))
        object.__setattr__(self, "sources", MappingProxyType(sources))
        object.__setattr__(self, "holdings", MappingProxyType(holdings))
        object.__setattr__(self, "consumed_by", MappingProxyType({r: consumed_by[r] for r in sorted(consumed_by)}))
        reservations = dict(self.reservations)
        for action_id, reservation in reservations.items():
            if not isinstance(reservation, Reservation) or action_id != reservation.action_id:
                raise ValueError("reservation key must match its action identity")
            if reservation.actor not in balances or reservation.created_tick >= self.tick:
                raise ValueError("a reservation needs an existing actor and an earlier creation tick")
            for effect in reservation.effects:
                account = effect.account
                named = resource_of(account)
                if named is not None and named not in holdings:
                    raise ValueError("a reservation names an unknown resource")
                if is_sink_account(account):
                    if effect.delta < 0:
                        raise ValueError("a reservation cannot debit consumed stock")
                elif is_actor_account(account):
                    if actor_of(account) not in balances:
                        raise ValueError("a reservation names an unknown actor")
                    if effect.delta < 0 and actor_of(account) != reservation.actor:
                        raise ValueError("a reservation cannot debit another actor")
                elif is_source_account(account):
                    if source_of(account) not in sources:
                        raise ValueError("a reservation names an unknown source")
                    if effect.delta < 0 and not sources[source_of(account)].permits(reservation.actor):
                        raise ValueError("a reservation needs source authority")
                else:
                    raise ValueError("a reservation names an unknown account")
        object.__setattr__(self, "reservations", MappingProxyType(dict(sorted(reservations.items()))))
        if any(amount < 0 for amount in self.availability().values()):
            raise ValueError("reserved stock exceeds its account balance")

    @classmethod
    def genesis(
        cls,
        *,
        tick: int = 0,
        balances: Mapping[str, int] | None = None,
        sources: Mapping[str, Source] | None = None,
        consumed: int = 0,
        reservations: Mapping[str, Reservation] | None = None,
        holdings: Mapping[str, Mapping[str, int]] | None = None,
        consumed_by: Mapping[str, int] | None = None,
    ) -> "WorldState":
        return cls(
            tick=tick,
            balances=dict(balances or {}),
            sources=dict(sources or {}),
            consumed=consumed,
            reservations=dict(reservations or {}),
            holdings=dict(holdings or {}),
            consumed_by=dict(consumed_by or {}),
        )

    @classmethod
    def from_canonical(cls, data: Mapping[str, Any]) -> "WorldState":
        """Rebuild a state from `canonical()`, as replay, recovery and restored
        instances need. Only this schema version is accepted, and the result is
        built through the constructor, so every rail that guards a live state
        guards a restored one. `from_canonical(s.canonical()).digest() == s.digest()`."""
        named = isinstance(data, Mapping) and ("holdings" in data or "consumed_by" in data)
        keys = {"schema_version", "tick", "balances", "sources", "consumed", "reservations"}
        data = _canonical_map(data, frozenset(keys | ({"holdings", "consumed_by"} if named else set())), "state")
        if named:
            if not isinstance(data["holdings"], Mapping) or not isinstance(data["consumed_by"], Mapping):
                raise ValueError("a canonical state needs mappings of holdings and consumed_by")
            if not data["holdings"] or any(not isinstance(m, Mapping) for m in data["holdings"].values()):
                raise ValueError("canonical holdings are omitted when empty and map each resource to actors")
        if data["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"a canonical state of schema {data['schema_version']!r} is not {SCHEMA_VERSION}")
        for name in ("balances", "sources", "reservations"):
            if not isinstance(data[name], Mapping):
                raise ValueError(f"a canonical state needs a mapping of {name}")
        return cls(
            tick=data["tick"],
            balances=dict(data["balances"]),
            sources={source_id: Source.from_canonical(source) for source_id, source in data["sources"].items()},
            consumed=data["consumed"],
            reservations={action_id: Reservation.from_canonical(reservation)
                          for action_id, reservation in data["reservations"].items()},
            holdings={r: dict(m) for r, m in data["holdings"].items()} if named else {},
            consumed_by=dict(data["consumed_by"]) if named else {},
        )

    @property
    def roster(self) -> tuple[str, ...]:
        """The tick-start actor identities, sorted."""
        return tuple(sorted(self.balances))

    def total(self) -> int:
        """The conserved total of the base resource: held, in a source, consumed."""
        return self.totals()[None]

    def totals(self) -> dict[str | None, int]:
        """The conserved total of every resource; None is the base resource."""
        out: dict[str | None, int] = {
            None: sum(self.balances.values())
            + sum(source.stock for source in self.sources.values() if source.resource is None)
            + self.consumed
        }
        for resource, amounts in self.holdings.items():
            out[resource] = (sum(amounts.values())
                             + sum(source.stock for source in self.sources.values() if source.resource == resource)
                             + self.consumed_by[resource])
        return out

    def availability(self) -> dict[str, int]:
        """A detached account map of free stock; holds are counted only once."""
        available = {actor_account(actor): amount for actor, amount in self.balances.items()}
        for resource, amounts in self.holdings.items():
            available.update({actor_account(actor, resource): amount for actor, amount in amounts.items()})
            available[sink_account(resource)] = 0
        available.update({source_account(name): source.stock for name, source in self.sources.items()})
        available[SINK_ACCOUNT] = 0
        for reservation in self.reservations.values():
            for account, amount in reservation.held().items():
                available[account] -= amount
        return available

    def view_for(self, actor_id: str) -> WorldView:
        if actor_id not in self.balances:
            raise KeyError(f"no such actor: {actor_id!r}")
        available = self.availability()
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
                        reserved=source.stock - available[source_account(source_id)],
                        resource=source.resource,
                    )
                    for source_id, source in self.sources.items()
                }
            ),
            roster=self.roster,
            reservations=MappingProxyType(dict(self.reservations)),
            holdings=MappingProxyType({r: MappingProxyType(dict(m)) for r, m in self.holdings.items()}),
        )

    def canonical(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "tick": self.tick,
            "balances": dict(self.balances),
            "sources": {source_id: source.canonical() for source_id, source in self.sources.items()},
            "consumed": self.consumed,
            "reservations": {action_id: reservation.canonical() for action_id, reservation in self.reservations.items()},
        }
        if self.holdings:
            # Only when declared, so a base-resource world keeps its old canonical form.
            out["holdings"] = {resource: dict(amounts) for resource, amounts in self.holdings.items()}
            out["consumed_by"] = dict(self.consumed_by)
        return out

    def digest(self) -> str:
        return canonical_digest(self.canonical())
