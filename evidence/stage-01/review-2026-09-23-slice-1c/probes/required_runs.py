from common import *
import hashlib
run('R1-suite', ['-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(BASE/'work/pytest-R1'),'--junitxml',str(OUT/'R1-junit.xml')])
run('R2-reproduce', ['evidence/stage-01/slice-1c/reproduce.py'])
run('R3-fixture', ['evidence/stage-01/instrument/fixture_digests.py'])
a=(OUT/'R3-fixture.stdout.txt').read_bytes(); b=(REPO/'evidence/stage-01/slice-1b/fixtures-stage1b.txt').read_bytes()
save('R3-comparison',dict(raw_equal=a==b,normalized_equal=a.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n'),output_sha256=hashlib.sha256(a).hexdigest(),reference_sha256=hashlib.sha256(b).hexdigest()))
for kind,module,cut in [('scenario','stream',40),('world','world',60)]:
    run('R4-'+kind,['-m',module+'.run','--replay',str(reference(kind))])
    lines=reference(kind).read_bytes().splitlines(keepends=True)
    i=next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick' and json.loads(line)['tick']==cut)
    prefix=b''.join(lines[:i+1]); source=DATA/f'R5-{kind}-cut{cut}.jsonl'; source.write_bytes(prefix)
    target=DATA/f'R5-{kind}-recovered.jsonl'
    rc=run('R5-'+kind,['-m',module+'.run','--recover',str(source),'--out',str(target)])
    save('R5-'+kind+'-comparison',dict(cut=cut,source_bytes=len(prefix),source_sha256=hashlib.sha256(prefix).hexdigest(),returncode=rc,content_equal=target.exists() and content(target)==content(reference(kind))))
run('R6-preflight',['automation/preflight.py'])
