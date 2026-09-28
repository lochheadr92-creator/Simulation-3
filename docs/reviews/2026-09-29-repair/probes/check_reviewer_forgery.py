import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path.cwd()))
from stream.run_file import read_run
from world.viewer import render_html

path=Path('docs/reviews/2026-09-28-whole-project/evidence/probes/viewer/forged.jsonl')
run=read_run(path)
assert run.complete,run.problems
actor=next(a for a in run.header['world']['positions'] if '<img' in a)
out=Path(sys.argv[1]).resolve(); out.mkdir(parents=True,exist_ok=True)
html=out/'claude-forged-current-viewer.html'
html.write_text(render_html(run),encoding='utf-8')
checked=subprocess.run([sys.argv[2],'tests/fixtures/viewer_security.cjs',html.as_uri(),actor],capture_output=True,text=True)
result=dict(input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),file_complete=run.complete,
            browser_exit=checked.returncode,stdout=checked.stdout,stderr=checked.stderr)
(out/'reviewer-forgery-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
assert checked.returncode==0
