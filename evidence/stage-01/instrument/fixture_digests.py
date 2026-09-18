"""Concrete canonical results for the two declared Stage 1a fixtures.

A reviewer can run this and compare the printed digests with the ones recorded
in `evidence/stage-01/RECORD.md`. Nothing here recomputes an expected answer by
a second route: it prints what the engine produced.

Run from the repository root:

    py -3 evidence/stage-01/instrument/fixture_digests.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from kernel import (  # noqa: E402
    ENGINE_VERSION,
    SCHEMA_VERSION,
    CollectingDiagnostics,
    Engine,
    Source,
    WorldState,
    claim,
    consume,
    transfer,
)


def show(title: str, lines: list[str]) -> None:
    print(f"\n{title}")
    for line in lines:
        print(f"  {line}")


def contention_fixture(tick: int) -> tuple[str, str, list[str]]:
    state = WorldState.genesis(
        tick=tick,
        balances={"A": 0, "B": 0},
        sources={"S": Source(stock=1, authorised=("A", "B"))},
    )
    engine = Engine(state)
    record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )
    lines = [
        f"rotated roster   {record.rotated_roster}",
        f"outcomes         {[(o.proposal_id, o.reason) for o in record.outcomes]}",
        f"balances         {dict(engine.state.balances)}",
        f"source S         {engine.state.sources['S'].stock}",
        f"total before     {state.total()}",
        f"total after      {engine.state.total()}",
        f"record digest    {record.digest()}",
        f"state digest     {engine.state.digest()}",
    ]
    return record.digest(), engine.state.digest(), lines


def credit_fixture(tick: int) -> tuple[str, str, list[str]]:
    state = WorldState.genesis(tick=tick, balances={"A": 1, "B": 0}, sources={})
    engine = Engine(state)
    first = engine.tick(
        [
            transfer("a_gives", "A", 0, to="B", amount=1),
            consume("a_spends_again", "A", 1, amount=1),
            consume("b_spends_early", "B", 0, amount=1),
        ]
    )
    after_first = dict(engine.state.balances)
    second = engine.tick([consume("b_spends_later", "B", 0, amount=1)])
    lines = [
        f"rotated roster   {first.rotated_roster}",
        f"tick {tick} outcomes  {[(o.proposal_id, o.reason) for o in first.outcomes]}",
        f"tick {tick} balances  {after_first}",
        f"tick {tick + 1} outcomes  {[(o.proposal_id, o.reason) for o in second.outcomes]}",
        f"tick {tick + 1} balances  {dict(engine.state.balances)}",
        f"consumed         {engine.state.consumed}",
        f"total before     {state.total()}",
        f"total after      {engine.state.total()}",
        f"tick {tick} digest    {first.digest()}",
        f"tick {tick + 1} digest    {second.digest()}",
        f"state digest     {engine.state.digest()}",
    ]
    return first.digest(), engine.state.digest(), lines


def main() -> int:
    print(f"engine {ENGINE_VERSION}   schema {SCHEMA_VERSION}")

    for tick in (0, 1):
        _, _, lines = contention_fixture(tick)
        show(f"A1 contention, one unit, two authorised claimants, tick {tick}", lines)

    for tick in (0, 1):
        _, _, lines = credit_fixture(tick)
        show(f"A6 roadmap credit fixture, A to B then consume, starting at tick {tick}", lines)

    quiet_record, quiet_state, _ = contention_fixture(0)
    sink = CollectingDiagnostics()
    engine = Engine(
        WorldState.genesis(
            tick=0,
            balances={"A": 0, "B": 0},
            sources={"S": Source(stock=1, authorised=("A", "B"))},
        ),
        diagnostics=sink,
    )
    noisy_record = engine.tick(
        [
            claim("pA", "A", 0, sources={"S": 1}),
            claim("pB", "B", 0, sources={"S": 1}),
        ]
    )
    show(
        "A8 diagnostics on against diagnostics off, same fixture",
        [
            f"diagnostics off record  {quiet_record}",
            f"diagnostics on record   {noisy_record.digest()}",
            f"diagnostics off state   {quiet_state}",
            f"diagnostics on state    {engine.state.digest()}",
            f"sink events captured    {len(sink.events)}",
            f"identical               {quiet_record == noisy_record.digest() and quiet_state == engine.state.digest()}",
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
