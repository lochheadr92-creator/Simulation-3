"""Reviewer rerun of the real mutation instrument on the pinned clone, with all
outputs written to the review evidence folder (never into the clone's tracked
evidence). Mirrors evidence/stage-01/repair-1/run_mutations.py."""
import contextlib, hashlib, importlib.util, json, os, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
temp = Path(sys.argv[3]).resolve()
if temp.exists():
    raise SystemExit('fresh pytest temp required')
output.mkdir(parents=True, exist_ok=True)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONHASHSEED'] = '0'
os.environ['PYTEST_ADDOPTS'] = '--basetemp="' + temp.as_posix() + '"'
spec = importlib.util.spec_from_file_location('review_mutations', root / 'evidence/stage-01/instrument/mutation_check.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
harness.RUNS = output / 'mutation-runs'
paths = sorted({root / m[2] for m in harness.MUTATIONS})
tracked = sorted(p for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts)
before_all = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
os.chdir(root)
with (output / 'mutation-output.txt').open('w', encoding='utf-8', newline='\n') as stream, contextlib.redirect_stdout(stream):
    code = harness.main()
after_all = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(q for q in root.rglob('*') if q.is_file() and '.git' not in q.relative_to(root).parts)}
result = {'exit_code': code, 'mutated_files': [str(p.relative_to(root)) for p in paths],
          'clone_files_restored_exactly': before_all == after_all,
          'changed': sorted(k for k in set(before_all) | set(after_all) if before_all.get(k) != after_all.get(k)),
          'python': sys.version}
(output / 'mutation-restoration.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'python'}))
raise SystemExit(code or int(before_all != after_all))
