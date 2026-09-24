from common import *
from kernel.canonical import digest
checks=[]
for seed in (None,'0','4242'):
    env=os.environ.copy()
    if seed is None: env.pop('PYTHONHASHSEED',None)
    else: env['PYTHONHASHSEED']=seed
    for kind,module in [('scenario','stream'),('world','world')]:
        label=f'P7-{kind}-hashseed-{seed or "unset"}';dest=DATA/(label+'.jsonl')
        rc=run(label,['-m',module+'.run','--seed','7','--ticks','120','--out',str(dest)],env)
        left,right=content(reference(kind)),content(dest)
        first=None
        for i,(a,b) in enumerate(zip(left,right)):
            if a!=b:
                x,y=json.loads(a),json.loads(b)
                first=dict(content_line=i+1,fields=[k for k in set(x)|set(y) if x.get(k)!=y.get(k)])
                break
        checks.append(dict(kind=kind,hashseed=seed,returncode=rc,content_equal=left==right,first_difference=first,final_seal=json.loads(right[-1])['final_seal']))
save('P7-process-determinism',checks)
