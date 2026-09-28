"""Bounded diagnostic: only the departure estimate differs; routing stays on.

Run from the source root: python PATH/f1_departures.py --out FILE.json
This does not write a normal saved world under a misleading rule description.
It changes one function in each worker's memory, never files on disk.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path.cwd()))
from kernel import Engine
from world.config import WorldConfig, genesis
from world.run import world_step
from stream.run_file import code_identity


def pair(job):
    seed, horizon = job
    decision = importlib.import_module('world.decide')
    native = decision.food_travel_ticks
    cfg = WorldConfig(seed=seed)
    assert cfg.route_around and cfg.terrain_on and cfg.plan_trips
    cases = {}
    for mode in ('current', 'old_departure_only'):
        ledger, world = genesis(cfg)
        cases[mode] = dict(engine=Engine(ledger), world=world, stats=dict(
            helped_decisions=0, gifts=0, memory_person_ticks=0,
            memory_changes_help_target_before_need_priority=0,
            starving_person_ticks=0, choices_when_memory_could_change_target={}, samples=[]))
    first = None
    try:
        for tick in range(horizon):
            steps = {}
            for mode, case in cases.items():
                decision.food_travel_ticks = native if mode == 'current' else lambda ob, config: decision.steps_to_source(ob)
                step = world_step(case['engine'], case['world'], cfg)
                stats = case['stats']
                for actor, choice in step.decisions.items():
                    ob = step.views[actor]
                    stats['memory_person_ticks'] += bool(ob.food_memory)
                    stats['starving_person_ticks'] += ob.hunger >= cfg.emergency_at
                    if ob.food_memory:
                        potential = (
                            decision.someone_to_help(ob, cfg) !=
                            decision.someone_to_help(replace(ob, food_memory=()), cfg))
                        stats['memory_changes_help_target_before_need_priority'] += potential
                        if potential:
                            kinds=stats['choices_when_memory_could_change_target']
                            kinds[choice.kind]=kinds.get(choice.kind,0)+1
                    if choice.helped_at is not None:
                        stats['helped_decisions'] += 1
                        if len(stats['samples']) < 10:
                            stats['samples'].append(dict(decision_tick=tick, actor=actor,
                                target=choice.target, helped_at=choice.helped_at, kind=choice.kind,
                                native_reason=choice.reason))
                stats['gifts'] += sum(o.accepted and o.operation == 'transfer' for o in step.record.outcomes)
                case['engine'], case['world'] = step.engine, step.processed.overlay
                steps[mode] = step
            if first is None:
                a, b = steps.values()
                if a.processed.overlay.digest() != b.processed.overlay.digest() or a.engine.state.digest() != b.engine.state.digest():
                    changes = []
                    for actor in sorted(set(a.decisions) & set(b.decisions)):
                        if a.decisions[actor] != b.decisions[actor]:
                            ob = a.views[actor]
                            changes.append(dict(actor=actor, same_observation=ob == b.views[actor],
                                hunger=ob.hunger, food=ob.food, position=ob.position, source=ob.source,
                                current_travel=native(ob,cfg), old_travel=decision.steps_to_source(ob),
                                current=a.decisions[actor].canonical(), old=b.decisions[actor].canonical()))
                    first = dict(decision_tick=tick, changes=changes)
        for case in cases.values():
            case['stats']['living_final'] = len(case['world'].living)
            case['stats']['final_world_digest'] = case['world'].digest()
            case['stats']['final_ledger_digest'] = case['engine'].state.digest()
        return dict(seed=seed, horizon=horizon, first_divergence=first,
                    cases={mode:case['stats'] for mode,case in cases.items()})
    finally:
        decision.food_travel_ticks = native


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args=parser.parse_args()
    started=time.monotonic()
    jobs=[(s,horizon) for horizon in (400,780) for s in range(1,36)] + [(14,650)]
    results=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(pair,job):job for job in jobs}
        for future in as_completed(futures):
            result=future.result()
            results.append(result)
            print(json.dumps(dict(seed=result['seed'], horizon=result['horizon'],
                helped={m:s['helped_decisions'] for m,s in result['cases'].items()})),flush=True)
    results.sort(key=lambda x:(x['horizon'],x['seed']))
    summary={}
    for horizon in (400,780):
        summary[horizon]={}
        for mode in ('current','old_departure_only'):
            sweep=[r['cases'][mode] for r in results if r['horizon']==horizon]
            choices={}
            for stats in sweep:
                for kind,count in stats['choices_when_memory_could_change_target'].items():
                    choices[kind]=choices.get(kind,0)+count
            summary[horizon][mode]=dict(seeds=35, ticks_per_seed=horizon,
                activated_seeds=sum(s['helped_decisions']>0 for s in sweep),
                helped_decisions=sum(s['helped_decisions'] for s in sweep),
                gifts=sum(s['gifts'] for s in sweep),
                memory_person_ticks=sum(s['memory_person_ticks'] for s in sweep),
                potential_target_changes=sum(s['memory_changes_help_target_before_need_priority'] for s in sweep),
                choices_when_memory_could_change_target=choices)
    output=dict(diagnostic='old nominal steps_to_source departure estimate only; routing and every other rule stay current',
        baseline_formula_source='22ffe2748dc4c5ee14c71295ff33810c7f456a7c:world/decide.py:trip_due',
        source_code_identity=code_identity(), seconds=round(time.monotonic()-started,2),
        summary=summary, results=results)
    args.out.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
