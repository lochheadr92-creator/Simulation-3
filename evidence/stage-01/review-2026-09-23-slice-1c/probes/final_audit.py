from common import *
import hashlib, zipfile, collections, xml.etree.ElementTree as ET

# Compare pristine extraction to the original archive, including .git and wheels.
archive=Path(json.loads((OUT/'identity.json').read_text())['source'])
pristine_root=PRISTINE.parent
with zipfile.ZipFile(archive) as z:
    expected={i.filename:hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}
actual={p.relative_to(pristine_root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in pristine_root.rglob('*') if p.is_file()}
pristine_bad=[k for k in expected.keys()|actual.keys() if expected.get(k)!=actual.get(k)]
initial=json.loads((OUT/'initial-file-manifest.json').read_text())
current={p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in REPO.rglob('*') if p.is_file() and '.git' not in p.relative_to(REPO).parts}
working_bad=[k for k in current.keys()|initial.keys() if current.get(k)!=initial.get(k)]
checks={}
for label,args in [('head',['git','rev-parse','HEAD']),('status',['git','status','--short']),('fsck',['git','fsck','--full','--strict'])]:
    p=subprocess.run(args,cwd=REPO,capture_output=True)
    checks[label]=dict(argv=args,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode())
save('final-preservation',dict(pristine_files=len(expected),pristine_differences=pristine_bad,working_files=len(current),working_differences=working_bad,git=checks))
assert not pristine_bad and not working_bad

# Independent size-share denominator clarification; measurements are of retained bytes.
from kernel.canonical import canonical_bytes
shares={}
for kind in ('scenario','world'):
    rows=[json.loads(line) for line in reference(kind).read_bytes().splitlines()]
    ticks=[r for r in rows if r['kind']=='tick'];total=sum(len(canonical_bytes(t))+1 for t in ticks)
    shares[kind]={k:sum(len(canonical_bytes(t[k])) for t in ticks)/total*100 for k in ('state','record','inputs')}
save('R7-weighted-shares',shares)
errors=json.loads((OUT/'R1-partition.json').read_text())['errors']
save('R1-error-classification',dict(total=len(errors),missing_sibling_repository=sum('orchestrator-freeze' in e['message'] and 'failed on setup' in e['message'] for e in errors),os_failures=0,simulation_failures=0,classification_basis='Every setup error message names missing work/run/orchestrator-freeze; no automation diagnosis or repair performed.'))
selected=[]
for t in ET.parse(OUT/'R1-junit.xml').iter('testcase'):
    if 'test_scenario_runs_replay_identically' in t.attrib['name'] or 'test_world_runs_replay_identically' in t.attrib['name']:
        selected.append(dict(test=t.attrib['classname']+'::'+t.attrib['name'],passed=len(list(t))==0))
save('R7-seed-matrix',selected)

# Accessible source excerpts and immutable input identities used by the report.
read_paths=['AGENTS.md','ROADMAP.md','DOCTRINE.md','evidence/stage-01/RECORD.md','stream/run_file.py','stream/replay.py','stream/recover.py','stream/run.py','world/run.py','world/replay.py','world/recover.py','kernel/state.py','world/overlay.py','world/config.py','stream/scenario.py','tests/test_sealed_stream.py','tests/test_replay.py','tests/test_recovery.py','tests/test_reference_results.py','tests/test_dependency_direction.py','tests/test_stream.py','tests/test_world.py','tests/test_world_view.py','evidence/stage-01/review-2026-09-21-slice-1a/REVIEW.md','evidence/stage-01/review-2026-09-21-slice-1b/REVIEW.md','kernel/engine.py','kernel/proposals.py','kernel/outcomes.py']
capture=OUT/'inspected-source.txt'
with capture.open('w',encoding='utf-8') as f:
    for name in read_paths:
        f.write('\n===== '+name+' =====\n')
        for i,line in enumerate((PRISTINE/name).read_text(encoding='utf-8').splitlines(),1):f.write(f'{i:5d} {line}\n')
save('read-index',read_paths)
