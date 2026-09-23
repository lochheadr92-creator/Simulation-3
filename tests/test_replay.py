"""Slice 1c: canonical reconstruction and replay against the file
(declaration items 5 and 6).

Replay re-executes from the header genesis with the recorded inputs (scenario
runs) or with recomputed decisions (world runs) and compares every tick line,
without its seal, byte for byte. A file edited and then re-sealed is exactly
what the seal cannot catch, so that is what replay is tested against.
World runs are the declaration's optional targets.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kernel import (Effect, Engine, Reservation, Source, WorldState, canonical_bytes, claim, complete, consume,
                    digest, reserve, transfer)
from stream.replay import ReplayError, replay_scenario
from stream.run import main as stream_main
from stream.run import run_scenario
from stream.run_file import header_seal, read_run, tick_seal
from stream.scenario import ProposalGenerator, Scenario
from world.config import WorldConfig
from world.overlay import Overlay
from world.replay import replay_world
from world.run import main as world_main
from world.run import run_world


def reseal(path: Path) -> None:
    """Recompute every seal, the trail and the end line after an edit, as a
    forger or a changed engine would: the seals then vouch for the edit."""
    out: list[bytes] = []
    trail = hashlib.sha256()
    seal = None
    for raw in path.read_bytes().splitlines(keepends=True):
        payload = json.loads(raw)
        if payload["kind"] == "header":
            payload["seal"] = header_seal(payload)
            seal = payload["seal"]
        elif payload["kind"] == "tick":
            payload["seal"] = tick_seal(seal, payload)
            seal = payload["seal"]
            raw = canonical_bytes(payload) + b"\n"
            trail.update(raw)
            out.append(raw)
            continue
        elif payload["kind"] == "end":
            payload["trail_digest"] = trail.hexdigest()
            payload["final_seal"] = seal
        out.append(canonical_bytes(payload) + b"\n")
    path.write_bytes(b"".join(out))


def edit_tick(path: Path, tick: int, change) -> None:
    lines = path.read_bytes().splitlines(keepends=True)
    for index, raw in enumerate(lines):
        payload = json.loads(raw)
        if payload["kind"] == "tick" and payload["tick"] == tick:
            change(payload)
            lines[index] = canonical_bytes(payload) + b"\n"
    path.write_bytes(b"".join(lines))
    reseal(path)
    assert read_run(path).complete, "the resealed edit should verify; only replay can catch it"


# --- reconstruction --------------------------------------------------------------

def scenario_states(ticks: int) -> list[WorldState]:
    scenario = Scenario(seed=7)
    engine = Engine(scenario.genesis())
    generator = ProposalGenerator(scenario)
    states = [engine.state]
    for _ in range(ticks):
        live = {action: held.actor for action, held in engine.state.reservations.items()}
        engine.tick(generator.tick(engine.state.tick, live))
        states.append(engine.state)
    return states


def fixture_states() -> list[WorldState]:
    """The 1a contention and credit fixtures and a 1b reserve-then-complete
    lifecycle, as states, built through the kernel's own operations."""
    states: list[WorldState] = []
    contention = Engine(WorldState.genesis(balances={"A": 0, "B": 0}, sources={"s": Source(1, frozenset({"A", "B"}))}))
    states.append(contention.state)
    contention.tick([claim("pA", "A", 0, sources={"s": 1}), claim("pB", "B", 0, sources={"s": 1})])
    states.append(contention.state)
    credit = Engine(WorldState.genesis(balances={"A": 1, "B": 0}))
    credit.tick([transfer("t", "A", 0, to="B", amount=1), consume("c", "B", 0, amount=1)])
    states.append(credit.state)
    credit.tick([consume("c2", "B", 0, amount=1)])
    states.append(credit.state)
    holds = Engine(WorldState.genesis(balances={"A": 2, "B": 0}, sources={"s": Source(3, frozenset({"A"}))}))
    record = holds.tick([reserve("r", "A", 0, operation="claim", params={"sources": {"s": 2}})])
    states.append(holds.state)
    action = next(outcome.action_id for outcome in record.outcomes if outcome.action_id)
    holds.tick([complete("k", "A", 0, action_id=action)])
    states.append(holds.state)
    assert any(state.reservations for state in states)
    return states


@pytest.mark.parametrize("source", ["fixtures", "scenario-200"])
def test_every_state_rebuilds_to_its_own_canonical_bytes(source: str):
    states = fixture_states() if source == "fixtures" else scenario_states(200)
    assert any(state.reservations for state in states)
    for state in states:
        rebuilt = WorldState.from_canonical(state.canonical())
        assert canonical_bytes(rebuilt.canonical()) == canonical_bytes(state.canonical())
        assert rebuilt.digest() == state.digest()
        for held in state.reservations.values():
            assert Reservation.from_canonical(held.canonical()) == held
            for effect in held.effects:
                assert Effect.from_canonical(effect.canonical()) == effect
        for pool in state.sources.values():
            assert Source.from_canonical(pool.canonical()) == pool
    # a stored (JSON) copy rebuilds too, not only the live dicts
    last = states[-1]
    assert WorldState.from_canonical(json.loads(canonical_bytes(last.canonical()))).digest() == last.digest()


@pytest.mark.parametrize("damage", ["negative-balance", "unknown-reserving-actor", "string-balance", "bool-balance",
                                    "float-stock", "missing-key", "extra-key", "old-schema", "unsorted-authorised",
                                    "repeated-authorised", "list-for-balances", "string-authorised"])
def test_malformed_canonical_states_are_refused(damage: str):
    state = next(state for state in scenario_states(60) if state.reservations)
    data = json.loads(canonical_bytes(state.canonical()))
    actor = sorted(data["balances"])[0]
    source = sorted(data["sources"])[0]
    if damage == "negative-balance":
        data["balances"][actor] = -1
    elif damage == "unknown-reserving-actor":
        next(iter(data["reservations"].values()))["actor"] = "nobody"
    elif damage == "string-balance":
        data["balances"][actor] = "1"
    elif damage == "bool-balance":
        data["balances"][actor] = True
    elif damage == "float-stock":
        data["sources"][source]["stock"] = 1.0
    elif damage == "missing-key":
        del data["consumed"]
    elif damage == "extra-key":
        data["extra"] = 0
    elif damage == "old-schema":
        data["schema_version"] = "v3.kernel.1a.1"
    elif damage == "unsorted-authorised":
        data["sources"][source]["authorised"].reverse()
    elif damage == "repeated-authorised":
        data["sources"][source]["authorised"].append(data["sources"][source]["authorised"][-1])
    elif damage == "list-for-balances":
        data["balances"] = sorted(data["balances"].items())
    elif damage == "string-authorised":
        data["sources"][source]["authorised"] = "p1"
    with pytest.raises(ValueError):
        WorldState.from_canonical(data)


def test_every_overlay_of_a_world_run_rebuilds_and_malformed_ones_are_refused(tmp_path: Path):
    path = tmp_path / "w.jsonl"
    run_world(WorldConfig(seed=7), 60, path)
    run = read_run(path)
    for stored in [run.header["world"]] + [tick["world"] for tick in run.ticks]:
        overlay = Overlay.from_canonical(stored)
        assert overlay.canonical() == stored and overlay.digest() == digest(stored)
    good = run.ticks[30]["world"]
    actor = sorted(good["positions"])[0]
    for mutate in (lambda d: d["positions"].__setitem__(actor, [1, 2, 3]),
                   lambda d: d["positions"].__setitem__(actor, "ab"),
                   lambda d: d["hunger"].__setitem__(actor, -1),
                   lambda d: d["died_at"].__setitem__(actor, d["tick"] + 1),
                   lambda d: d.pop("yield_at"),
                   lambda d: d.__setitem__("homes", [])):
        broken = json.loads(json.dumps(good))
        mutate(broken)
        with pytest.raises(ValueError):
            Overlay.from_canonical(broken)


def test_scenario_and_world_descriptions_round_trip_exactly():
    for scenario in (Scenario(seed=7), Scenario(seed=11, actors=4, sources=3, max_proposals_per_tick=5)):
        assert Scenario.from_describe(json.loads(json.dumps(scenario.describe()))) == scenario
    for config in (WorldConfig(seed=7), WorldConfig(seed=11, yield_on=False, scoring_on=True, renewal_every=2),
                   WorldConfig(seed=23, yield_set=(2, 3), perception_radius=5)):
        assert WorldConfig.from_describe(json.loads(json.dumps(config.describe()))) == config


@pytest.mark.parametrize("damage", ["name", "version", "extra", "missing", "string-seed"])
def test_a_scenario_description_from_elsewhere_is_refused(damage: str):
    described = Scenario(seed=7).describe()
    if damage == "name":
        described["name"] = "other"
    elif damage == "version":
        described["version"] = "v3.scenario.contention-and-holds.2"
    elif damage == "extra":
        described["extra"] = 1
    elif damage == "missing":
        del described["actors"]
    else:
        described["seed"] = "7"
    with pytest.raises(ValueError):
        Scenario.from_describe(described)


@pytest.mark.parametrize("damage", ["generator", "name", "rule-text", "lever-type", "switch", "unhashable-switch"])
def test_a_world_description_that_is_not_this_code_is_refused(damage: str):
    described = WorldConfig(seed=7).describe()
    if damage == "generator":
        described["genesis_generator"] = "homes-uniform-v2"
    elif damage == "name":
        described["name"] = "two-source-grid"
    elif damage == "rule-text":
        described["movement"] = "two steps per tick"
    elif damage == "lever-type":
        described["width"] = 12.0
    elif damage == "switch":
        described["yield"] = "maybe"
    else:
        described["scoring"] = ["on"]
    with pytest.raises(ValueError):
        WorldConfig.from_describe(described)


# --- replay: scenario runs (essential) --------------------------------------------

@pytest.mark.parametrize("seed", [7, 11, 23])
def test_scenario_runs_replay_identically(tmp_path: Path, seed: int):
    path = tmp_path / f"scenario-{seed}.jsonl"
    run_scenario(Scenario(seed=seed), 120, path)
    result = replay_scenario(path)
    assert result.identical and result.ticks == 120 and result.code_identity_matches


def accepted_input(payload: dict) -> dict | None:
    accepted = {o["proposal_id"] for o in payload["record"]["outcomes"] if o["accepted"]}
    for entry in payload["inputs"]:
        if entry["proposal_id"] in accepted and "params" in entry and "amount" in entry["params"]:
            return entry
    return None


def test_a_resealed_altered_input_replays_different_at_exactly_that_tick(tmp_path: Path):
    path = tmp_path / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 120, path)
    target = next(tick["tick"] for tick in read_run(path).ticks if tick["tick"] >= 20 and accepted_input(tick))

    def change(payload: dict) -> None:
        accepted_input(payload)["params"]["amount"] += 1

    edit_tick(path, target, change)
    result = replay_scenario(path)
    assert not result.identical
    assert result.divergent_tick == target and result.divergent_field == "record"


def test_a_resealed_altered_outcome_replays_different_at_exactly_that_tick(tmp_path: Path):
    path = tmp_path / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 120, path)
    target = next(tick["tick"] for tick in read_run(path).ticks if tick["tick"] >= 30 and accepted_input(tick))

    def change(payload: dict) -> None:
        outcome = next(o for o in payload["record"]["outcomes"] if o["accepted"])
        outcome["reason"] = "denied_insufficient_balance"
        outcome["accepted"] = 0
        payload["record_digest"] = digest(payload["record"])

    edit_tick(path, target, change)
    result = replay_scenario(path)
    assert not result.identical
    assert result.divergent_tick == target and result.divergent_field == "record"


def test_replay_refuses_files_it_cannot_vouch_for(tmp_path: Path):
    scenario_path = tmp_path / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 20, scenario_path)
    world_path = tmp_path / "world.jsonl"
    run_world(WorldConfig(seed=7, width=7, height=7, actors=4), 20, world_path)
    with pytest.raises(ReplayError, match="world run"):
        replay_scenario(world_path)
    with pytest.raises(ReplayError, match="not a world run"):
        replay_world(scenario_path)
    cut = tmp_path / "cut.jsonl"
    cut.write_bytes(b"".join(scenario_path.read_bytes().splitlines(keepends=True)[:-3]))
    with pytest.raises(ReplayError, match="does not verify"):
        replay_scenario(cut)


def test_a_header_whose_genesis_its_configuration_does_not_produce_is_reported(tmp_path: Path):
    path = tmp_path / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 10, path)
    lines = path.read_bytes().splitlines(keepends=True)
    header = json.loads(lines[0])
    header["scenario"]["starting_balance"] = 4   # the scenario genesis does not depend on the seed
    header["config_identity"] = digest(header["scenario"])
    lines[0] = canonical_bytes(header) + b"\n"
    path.write_bytes(b"".join(lines))
    reseal(path)
    result = replay_scenario(path)
    assert not result.identical and result.divergent_field == "genesis"


# --- replay: world runs (optional targets) -----------------------------------------

@pytest.mark.parametrize("seed", [7, 11, 23])
@pytest.mark.parametrize("yield_on", [True, False])
@pytest.mark.parametrize("scoring_on", [False, True])
def test_world_runs_replay_identically(tmp_path: Path, seed: int, yield_on: bool, scoring_on: bool):
    path = tmp_path / "world.jsonl"
    run_world(WorldConfig(seed=seed, yield_on=yield_on, scoring_on=scoring_on), 120, path)
    result = replay_world(path)
    assert result.identical and result.ticks == 120 and result.code_identity_matches


def test_a_resealed_altered_decision_replays_different_at_exactly_that_tick(tmp_path: Path):
    path = tmp_path / "world.jsonl"
    run_world(WorldConfig(seed=7), 120, path)

    def change(payload: dict) -> None:
        actor = sorted(payload["decisions"])[0]
        payload["decisions"][actor]["reason"] += " (edited)"

    edit_tick(path, 30, change)
    result = replay_world(path)
    assert not result.identical
    assert result.divergent_tick == 30 and result.divergent_field == "decisions"


# --- commands ------------------------------------------------------------------------

def test_the_runner_commands_report_replay(tmp_path: Path, capsys):
    scenario_path = tmp_path / "scenario.jsonl"
    run_scenario(Scenario(seed=7), 30, scenario_path)
    assert stream_main(["--replay", str(scenario_path)]) == 0
    assert "replay: identical" in capsys.readouterr().out
    world_path = tmp_path / "world.jsonl"
    run_world(WorldConfig(seed=7), 30, world_path)
    assert world_main(["--replay", str(world_path)]) == 0
    assert "replay: identical" in capsys.readouterr().out
    assert stream_main(["--replay", str(world_path)]) == 2
    assert stream_main(["--ticks", "5"]) == 2
