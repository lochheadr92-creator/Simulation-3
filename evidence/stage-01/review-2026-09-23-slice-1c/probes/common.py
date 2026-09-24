from pathlib import Path
import os, sys, subprocess, json, datetime, time
PACKAGE = Path(__file__).resolve().parents[1]
BASE = PACKAGE.parents[1]
REPO = Path(os.environ.get('SIM3_REVIEW_REPO', BASE / 'work/run/03-Living-World-V3'))
PRISTINE = BASE / 'work/pristine/03-Living-World-V3'
OUT = PACKAGE / 'outputs'
DATA = OUT / 'artifacts'
DATA.mkdir(exist_ok=True)
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))

def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    print(name + ': ' + json.dumps(value, ensure_ascii=False), flush=True)

def run(name, args, env=None):
    argv = [sys.executable, '-B'] + args
    t = time.monotonic()
    with (OUT / (name + '.stdout.txt')).open('wb') as stdout, (OUT / (name + '.stderr.txt')).open('wb') as stderr:
        p = subprocess.run(argv, cwd=REPO, env=env, stdout=stdout, stderr=stderr)
    meta = dict(argv=argv, cwd=str(REPO), returncode=p.returncode, seconds=time.monotonic()-t,
                utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(name + '.command', meta)
    return p.returncode

def content(path):
    return [line for line in path.read_bytes().splitlines() if json.loads(line).get('kind') != 'timing']

def reference(kind):
    return REPO / f'evidence/stage-01/slice-1c/{kind}-seed7-ticks120.jsonl'
