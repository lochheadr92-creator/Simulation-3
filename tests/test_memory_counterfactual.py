"""One ordinary donor-memory decision, forked through the real world step."""
import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from kernel import Engine
from stream.recover import restored_state, sealed_prefix, resume_writer
from stream.run_file import read_run, tick_payload
from world.config import WorldConfig
from world.decide import decide
from world.observe import observe
from world.overlay import Overlay
from world.replay import replay_world
from world.run import run_world, world_step
from world.viewer import render_html


@pytest.mark.long_run
def test_ordinary_donor_memory_changes_a_real_continuation(tmp_path):
    cfg = WorldConfig(seed=29)
    ordinary = tmp_path / 'seed29-ordinary.jsonl'
    run_world(cfg, 780, ordinary)
    run = read_run(ordinary)
    assert replay_world(ordinary).identical
    ordinary.with_suffix('.html').write_text(render_html(run), encoding='utf-8')
    # Locate a real memory-influenced choice; do not inject a remembered donor.
    candidates = [(i, actor) for i, tick in enumerate(run.ticks)
                  for actor, decision in tick['decisions'].items()
                  if decision.get('helped_at') is not None]
    assert candidates
    chosen = None
    for at, actor in candidates:
        ledger = restored_state(run.header, run.ticks[at - 1])
        overlay = Overlay.from_canonical(run.ticks[at - 1]['world'])
        view = observe(actor, ledger, overlay, cfg)
        visible, hidden = decide(view, cfg), decide(replace(view, food_memory=()), cfg)
        if (visible.kind, visible.target) != (hidden.kind, hidden.target):
            chosen = (at, actor, ledger, overlay, visible, hidden)
            break
    assert chosen is not None, 'Memory rationale alone is not a changed physical choice'
    at, actor, ledger, overlay, visible, hidden = chosen
    before = (ledger.canonical(), overlay.canonical())
    lines = ordinary.read_bytes().splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines)
               if (data := json.loads(line)).get('kind') == 'tick' and data['tick'] == at - 1)
    cut = tmp_path / 'same-state-prefix.jsonl'
    cut.write_bytes(b''.join(lines[:end + 1]))
    prefix = sealed_prefix(cut)
    branch = tmp_path / 'seed29-CONTROLLED-memory-hidden-once.jsonl'
    mask_calls = []
    def hidden_observation(person, state, world, config, available=None):
        result = observe(person, state, world, config, available)
        if person == actor and state.tick == at:
            mask_calls.append((person, state.tick))
            return replace(result, food_memory=())
        return result
    control_engine, masked_engine = Engine(ledger), Engine(ledger)
    control_world = masked_world = overlay
    differences, transfers = [], {'ordinary': [], 'masked': []}
    first_masked = None
    with resume_writer(branch, prefix) as writer:
        for offset in range(max(100, 780 - at)):
            control = world_step(control_engine, control_world, cfg)
            with patch('world.run.observe', hidden_observation):
                masked = world_step(masked_engine, masked_world, cfg)
            if offset == 0:
                first_masked = tick_payload(masked.record, masked.committed,
                                            inputs=masked.proposals, **masked.line_fields())
                assert masked.decisions[actor] == hidden
                assert control.decisions[actor] == visible
                for other in control.views:
                    if other != actor:
                        assert control.views[other] == masked.views[other]
                assert replace(control.views[actor], food_memory=()) == masked.views[actor]
            if at + offset < 780:
                expected = dict(run.ticks[at + offset])
                expected.pop('seal')
                assert tick_payload(control.record, control.committed,
                                    inputs=control.proposals, **control.line_fields()) == expected
                writer.record(masked.record, masked.committed,
                              inputs=masked.proposals, **masked.line_fields())
            for name, step in [('ordinary', control), ('masked', masked)]:
                for outcome in step.record.outcomes:
                    if outcome.accepted and outcome.operation == 'transfer':
                        decision = step.decisions[outcome.actor]
                        transfers[name].append({'completed_tick': at + offset + 1,
                                                'giver': outcome.actor, 'recipient': decision.target})
            # Exclude descriptions and memory: these are physical consequences.
            if (control.engine.state != masked.engine.state or
                control.processed.overlay.positions != masked.processed.overlay.positions or
                control.processed.overlay.hunger != masked.processed.overlay.hunger or
                control.processed.overlay.died_at != masked.processed.overlay.died_at):
                differences.append(at + offset)
            control_engine, control_world = control.engine, control.processed.overlay
            masked_engine, masked_world = masked.engine, masked.processed.overlay
    assert mask_calls == [(actor, at)]
    assert differences and differences[0] == at
    assert (ledger.canonical(), overlay.canonical()) == before
    # Repeating the single intervention from the unchanged initial state is exact.
    with patch('world.run.observe', hidden_observation):
        repeated = world_step(Engine(ledger), overlay, cfg)
    assert tick_payload(repeated.record, repeated.committed,
                        inputs=repeated.proposals, **repeated.line_fields()) == first_masked
    assert read_run(branch).complete
    # A controlled intervention is deliberately NOT an ordinary replay.
    replay = replay_world(branch)
    assert not replay.identical
    html = render_html(read_run(branch))
    notice = f'<p role="note">CONTROLLED COUNTERFACTUAL: {actor} donor memory hidden for decision {at} only. This is not an ordinary replay.</p>'
    branch.with_suffix('.html').write_text(html.replace('<body>', '<body>' + notice), encoding='utf-8')
    summary = {'seed': 29, 'decision_tick': at, 'completed_tick': at + 1, 'actor': actor,
               'ordinary': visible.canonical(), 'masked': hidden.canonical(),
               'initial_memory': overlay.food_memory[actor], 'continuation_ticks': max(100, 780 - at),
               'first_physical_difference': differences[0], 'last_physical_difference': differences[-1],
               'ordinary_replay': 'identical', 'intervened_replay': str(replay),
               'ordinary_final_living': sorted(control_world.living),
               'masked_final_living': sorted(masked_world.living), 'transfers': transfers,
               'code_identity': run.header['code_identity']['digest']}
    (tmp_path / 'memory-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
