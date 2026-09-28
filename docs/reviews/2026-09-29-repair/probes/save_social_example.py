"""Save an example selected transparently from the fixed F1 sweep, not a new test oracle."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()))
from world.config import WorldConfig
from world.run import run_world
from world.replay import replay_world
from world.recover import recover_world
from world.viewer import render_html
from world.viewer_index import build_index
from stream.run_file import read_run

out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=True)
path=out/'seed29-current.jsonl'
run_world(WorldConfig(seed=29),780,path)
run=read_run(path)
assert run.complete and replay_world(path).identical
path.with_suffix('.html').write_text(render_html(run),encoding='utf-8')
gift=run.ticks[559]
returned=run.ticks[713]
assert any(o['actor']=='p19' and o['operation']=='transfer' and o['accepted']
           and {'account':'actor:p27','delta':1} in o['effects'] for o in gift['record']['outcomes'])
assert returned['decisions']['p27']['helped_at']==560
assert any(o['actor']=='p27' and o['operation']=='transfer' and o['accepted']
           and {'account':'actor:p19','delta':1} in o['effects'] for o in returned['record']['outcomes'])
lines=path.read_bytes().splitlines(keepends=True)
cut_at=next(i for i,b in enumerate(lines) if json.loads(b).get('kind')=='tick' and json.loads(b)['tick']==708)
cut=out/'seed29-cut.jsonl'; cut.write_bytes(b''.join(lines[:cut_at+1]))
recovered=out/'seed29-recovered.jsonl'
recover_world(cut,recovered)
assert read_run(recovered).ticks==run.ticks and replay_world(recovered).identical
summary=dict(seed=29,horizon=780,selection='First current-mode seed with an OFFER carrying helped_at in the fixed 1-35, 780-tick sweep',
    code_identity=run.header['code_identity'],complete=run.complete,replay_identical=True,
    recovery_cut_after_decision_tick=708,recovery_identical=True,recovered_replay_identical=True,
    original_gift=dict(decision_tick=559,world_tick=560,donor='p19',recipient='p27',accepted=True),
    return_gift=dict(decision_tick=713,world_tick=714,donor='p27',recipient='p19',accepted=True),
    remembered_helper_events=[e for e in build_index(run)['events'] if e['kind']=='remembered_helper'])
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('code_identity','remembered_helper_events')},indent=2))
