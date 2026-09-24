from common import *
import hashlib, xml.etree.ElementTree as ET, difflib
FILES=['tests/test_sealed_stream.py','tests/test_replay.py','tests/test_recovery.py','tests/test_reference_results.py','tests/test_dependency_direction.py','tests/test_stream.py','tests/test_world.py','tests/test_world_view.py']
mutations=[
('drop-prev','stream/run_file.py','return digest({"prev": previous, "tick": digest(without_seal(payload))})','return digest({"tick": digest(without_seal(payload))})'),
('prefix-extra-line','stream/recover.py','prefix=b"".join(kept))','prefix=b"".join(kept + lines[len(kept):len(kept)+1]))'),
('shared-mapping','stream/recover.py','return Engine(restored_state(run.header, run.ticks[tick - genesis_tick]))','state = restored_state(run.header, run.ticks[tick - genesis_tick])\n    if hasattr(restore_engine, "_review_shared_balances"):\n        object.__setattr__(state, "balances", restore_engine._review_shared_balances)\n    else:\n        restore_engine._review_shared_balances = state.balances\n    return Engine(state)'),
('skip-generator-check','stream/recover.py','if canonical_bytes([encode_input(p) for p in proposals]) != canonical_bytes(payload["inputs"]):','if False:'),
('timing-in-trail','stream/run_file.py','self._write({"kind": "timing", "tick": record.tick, "elapsed_ns": int(elapsed_ns)})','self._trail.update(self._write({"kind": "timing", "tick": record.tick, "elapsed_ns": int(elapsed_ns)}))'),
('prefix-extra-tick','stream/recover.py','prefix=b"".join(kept))','prefix=b"".join(kept + next(([raw] for raw in lines[len(kept):] if b\'"kind":"tick"\' in raw), [])))'),
]
initial=json.loads((OUT/'initial-file-manifest.json').read_text())
def mismatches():
    current={p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in REPO.rglob('*') if p.is_file() and '.git' not in p.relative_to(REPO).parts}
    pristine={p.relative_to(PRISTINE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PRISTINE.rglob('*') if p.is_file() and '.git' not in p.relative_to(PRISTINE).parts}
    assert pristine==initial,'Pristine altered'
    return [k for k in initial.keys()|current.keys() if initial.get(k)!=current.get(k)]
assert not mismatches()
run('P8-baseline',['-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(BASE/'work/pytest-P8-baseline'),'--junitxml',str(OUT/'P8-baseline.xml')]+FILES)
summary=[]
for name,filename,old,new in mutations:
    path=REPO/filename; original=(PRISTINE/filename).read_bytes(); text=original.decode();assert text.count(old)==1,(name,text.count(old))
    modified=text.replace(old,new)
    (OUT/(f'P8-{name}.patch')).write_text(''.join(difflib.unified_diff(text.splitlines(True),modified.splitlines(True),fromfile=filename,tofile=filename)),encoding='utf-8')
    try:
        path.write_bytes(modified.encode())
        rc=run('P8-'+name,['-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(BASE/f'work/pytest-P8-{name}'),'--junitxml',str(OUT/(f'P8-{name}.xml'))]+FILES)
        xml=ET.parse(OUT/(f'P8-{name}.xml'));failed=[];counts={'passed':0,'failed':0,'errors':0,'skipped':0}
        for case in xml.iter('testcase'):
            key='passed'
            if case.find('failure') is not None:key='failed'
            elif case.find('error') is not None:key='errors'
            elif case.find('skipped') is not None:key='skipped'
            counts[key]+=1
            if key in ('failed','errors'):failed.append(case.attrib['classname']+'::'+case.attrib['name'])
        summary.append(dict(name=name,file=filename,returncode=rc,counts=counts,failed_tests=failed))
    finally:
        path.write_bytes(original)
        restored=mismatches();assert not restored,restored
        save('P8-'+name+'-restoration',dict(all_268_files_equal=True,pristine_equal_initial=True))
save('P8-mutations',summary)
run('P8-restored-tests',['-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(BASE/'work/pytest-P8-restored'),'--junitxml',str(OUT/'P8-restored.xml')]+FILES)
assert not mismatches()
