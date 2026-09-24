from pathlib import Path
import zipfile,hashlib,json,subprocess,sys,platform,datetime
base=Path.cwd(); out=base/'outputs/sim3-review-1c-output/outputs'
z=Path(r'C:\Users\RJLoc\AppData\Local\Temp\codex-file-preview-UAOB4A\sim3-1c-d14dece.zip')
b=z.read_bytes(); info={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':str(z),'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'python':sys.version,'executable':sys.executable,'os':platform.platform()}
assert len(b)==4580061 and info['sha256']=='3ad56ed18a3b05f32dcb3b6c9596879f8954326ab5f2eccc5e9b66d2b095f80b'
for name in ['pristine','run']:
 target=base/'work'/name
 assert not target.exists()
 with zipfile.ZipFile(z) as f:
  for n in f.namelist():
   assert (target/n).resolve().is_relative_to(target.resolve()),n
  f.extractall(target)
repo=base/'work/run/03-Living-World-V3'
for args in [['git','rev-parse','HEAD'],['git','status','--short'],['git','fsck','--full','--strict'],['git','log','-4','--first-parent','--format=%H'],[sys.executable,'-B','-m','pytest','--version']]:
 p=subprocess.run(args,cwd=repo,capture_output=True)
 key=' '.join(args); info[key]={'rc':p.returncode,'stdout':p.stdout.decode('utf-8','replace'),'stderr':p.stderr.decode('utf-8','replace')}
assert info['git rev-parse HEAD']['stdout'].strip()=='d14decec50d285395febb97c06d8eb7d94930b88'
assert info['git status --short']['stdout']==''
assert info['git fsck --full --strict']['rc']==0
files={str(p.relative_to(repo)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in repo.rglob('*') if p.is_file() and '.git' not in p.relative_to(repo).parts}
(out/'initial-file-manifest.json').write_text(json.dumps(files,indent=2))
(out/'identity.json').write_text(json.dumps(info,indent=2)); print(json.dumps(info,indent=2));print('Working files:',len(files))
