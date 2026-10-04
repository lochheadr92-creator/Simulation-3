"""An independent per-account audit of a saved run's ledger.

The kernel already refuses unbalanced settlement, and `read_run` re-derives each
tick's produced state from the production entries. This audit asks a different
question: is every change to every account explained?

For each tick it starts from the previous tick's final state, applies only the
effects of ACCEPTED outcomes, and requires the result to equal the committed
state that tick recorded, account by account (actors, shared sources, consumption
sinks, named-resource holdings). It then applies the recorded production and
requires every difference in a resource total to be accounted for by an entry:
renewal adds to a named source, a birth adds an empty account, a created source
starts empty. Aggregate totals alone cannot show that an individual transaction
was valid; this reads the accounts one at a time.

Written against the canonical JSON of the file, not the kernel's objects, so it
is not a second use of the code it checks.
"""

from __future__ import annotations

import json
from typing import Any

from stream.run_file import apply_production


def _parse(account: str) -> tuple[str, str | None, str]:
    """(kind, resource, name) for `actor:p01`, `actor@water:p01`, `source:food`,
    `sink:consumed`, `sink@water:consumed`."""
    if account.startswith("actor@"):
        resource, _, name = account[len("actor@"):].partition(":")
        return "actor", resource, name
    if account.startswith("actor:"):
        return "actor", None, account[len("actor:"):]
    if account.startswith("sink@"):
        resource, _, name = account[len("sink@"):].partition(":")
        return "sink", resource, name
    if account == "sink:consumed":
        return "sink", None, "consumed"
    if account.startswith("source:"):
        return "source", None, account[len("source:"):]
    raise AssertionError(f"unrecognised account {account!r}")


def _copy(state: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(state))


def _apply_effect(state: dict[str, Any], account: str, delta: int) -> None:
    kind, resource, name = _parse(account)
    if kind == "actor":
        if resource is None:
            state["balances"][name] += delta
        else:
            state["holdings"][resource][name] += delta
    elif kind == "sink":
        if resource is None:
            state["consumed"] += delta
        else:
            state["consumed_by"][resource] += delta
    else:
        state["sources"][name]["stock"] += delta


def resource_totals(state: dict[str, Any]) -> dict[str | None, int]:
    """Conserved total of every resource: held, in a source of it, consumed."""
    totals: dict[str | None, int] = {
        None: sum(state["balances"].values()) + state["consumed"]
              + sum(s["stock"] for s in state["sources"].values() if "resource" not in s)}
    for resource, amounts in (state.get("holdings") or {}).items():
        totals[resource] = (sum(amounts.values()) + state["consumed_by"][resource]
                            + sum(s["stock"] for s in state["sources"].values() if s.get("resource") == resource))
    return totals


def _explain_difference(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Every account whose value differs between two canonical states."""
    problems: list[str] = []
    for actor in sorted(set(before["balances"]) | set(after["balances"])):
        if before["balances"].get(actor) != after["balances"].get(actor):
            problems.append(f"actor:{actor} {before['balances'].get(actor)} -> {after['balances'].get(actor)}")
    for source in sorted(set(before["sources"]) | set(after["sources"])):
        was = before["sources"].get(source, {}).get("stock")
        now = after["sources"].get(source, {}).get("stock")
        if was != now:
            problems.append(f"source:{source} {was} -> {now}")
    if before["consumed"] != after["consumed"]:
        problems.append(f"sink:consumed {before['consumed']} -> {after['consumed']}")
    for resource in sorted(set(before.get("holdings") or {}) | set(after.get("holdings") or {})):
        was_map = (before.get("holdings") or {}).get(resource, {})
        now_map = (after.get("holdings") or {}).get(resource, {})
        for actor in sorted(set(was_map) | set(now_map)):
            if was_map.get(actor) != now_map.get(actor):
                problems.append(f"actor@{resource}:{actor} {was_map.get(actor)} -> {now_map.get(actor)}")
        was_sink = (before.get("consumed_by") or {}).get(resource)
        now_sink = (after.get("consumed_by") or {}).get(resource)
        if was_sink != now_sink:
            problems.append(f"sink@{resource}:consumed {was_sink} -> {now_sink}")
    return problems


def audit_run(run: Any) -> list[str]:
    """Problems found in a saved run's ledger history; an empty list means every
    account change was explained by an accepted outcome or recorded production."""
    problems: list[str] = []
    current = _copy(run.header["genesis"])
    for index, tick in enumerate(run.ticks):
        where = f"tick {tick.get('tick', index)}"
        expected = _copy(current)
        for outcome in tick["record"]["outcomes"]:
            if outcome["accepted"] != (1 if outcome["reason"] == "accepted" else 0):
                problems.append(f"{where}: {outcome['proposal_id']} accepted flag disagrees with its reason")
            if not outcome["accepted"]:
                if outcome["effects"]:
                    problems.append(f"{where}: refused {outcome['proposal_id']} still carries effects")
                continue
            if sum(e["delta"] for e in outcome["effects"]) != 0 and outcome["operation"] != "reserve":
                problems.append(f"{where}: accepted {outcome['proposal_id']} does not sum to zero")
            for effect in outcome["effects"]:
                _apply_effect(expected, effect["account"], effect["delta"])
        committed = tick["state"]
        for actor, amount in committed["balances"].items():
            if amount < 0:
                problems.append(f"{where}: actor:{actor} is negative")
        # settlement never adds or removes a person or a source
        if set(committed["balances"]) != set(current["balances"]) or set(committed["sources"]) != set(current["sources"]):
            problems.append(f"{where}: settlement changed the roster or the sources")
        for difference in _explain_difference(expected, committed):
            problems.append(f"{where}: committed state differs from the accepted effects: {difference}")
        before_totals, committed_totals = resource_totals(current), resource_totals(committed)
        if before_totals != committed_totals:
            problems.append(f"{where}: settlement changed a resource total {before_totals} -> {committed_totals}")
        production = tick.get("production") or []
        produced = apply_production(committed, production) if production else committed
        gained: dict[str | None, int] = {}
        for entry in production:
            if "amount" in entry and "source" in entry:
                resource = committed["sources"][entry["source"]].get("resource")
                gained[resource] = gained.get(resource, 0) + entry["amount"]
            elif "made" in entry:
                gained[entry["item"]] = gained.get(entry["item"], 0) + entry["amount"]
                # what a person makes was paid for in the same tick: every recipe input settled as spending
                from world.crafting import RECIPES
                if entry["item"] not in RECIPES or entry["amount"] != 1:
                    problems.append(f"{where}: {entry['made']} made {entry['amount']} {entry['item']}, which no recipe yields")
                if sum(1 for e in production if e.get("made") == entry["made"] and e.get("item") == entry["item"]) > 1:
                    problems.append(f"{where}: {entry['made']} made {entry['item']} more than once on one tick")
                spent = {(o["actor"], e["account"]): -e["delta"] for o in tick["record"]["outcomes"]
                         if o["accepted"] and o["operation"] == "consume" for e in o["effects"] if e["delta"] < 0}
                for resource, units in RECIPES.get(entry["item"], ()):
                    if spent.get((entry["made"], f"actor@{resource}:{entry['made']}")) != units:
                        problems.append(f"{where}: {entry['made']} made {entry['item']} without spending {units} {resource}")
        produced_totals = resource_totals(produced)
        for resource in sorted(set(produced_totals) | set(committed_totals), key=str):
            delta = produced_totals.get(resource, 0) - committed_totals.get(resource, 0)
            if delta != gained.get(resource, 0):
                problems.append(f"{where}: {resource or 'food'} total moved by {delta} after settlement "
                                f"but production explains {gained.get(resource, 0)}")
        for entry in production:
            if "born" in entry:
                name = entry["born"]
                if produced["balances"].get(name) != 0 or any(
                        amounts.get(name) != 0 for amounts in (produced.get("holdings") or {}).values()):
                    problems.append(f"{where}: {name} was born holding something")
            if "source_created" in entry and produced["sources"][entry["source_created"]]["stock"] != 0:
                problems.append(f"{where}: created source {entry['source_created']} did not start empty")
        current = _copy(produced)
    return problems
