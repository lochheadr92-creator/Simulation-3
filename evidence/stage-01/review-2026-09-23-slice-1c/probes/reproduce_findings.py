"""Minimal F1/F2 reproductions. Set SIM3_REVIEW_REPO to an unmodified target.
Writes only new run-file copies under this review bundle's outputs/artifacts.
Does not edit repository code, tests, or frozen references.
"""
from common import *
import tempfile, hashlib, traceback
from kernel.canonical import canonical_bytes
from stream.run_file import read_run
from stream.recover import recover_scenario
from world.recover import recover_world

folder=Path(tempfile.mkdtemp(prefix='minimal-findings-',dir=DATA))
results=[]
for kind,recover in [('scenario',recover_scenario),('world',recover_world)]:
    original=reference(kind).read_bytes().splitlines(keepends=True)
    idx=next(i for i,line in enumerate(original) if json.loads(line).get('kind')=='tick' and json.loads(line)['tick']==57)
    for fault in ('one-bad-utf8-byte','bad-timing-value','unsealed-header-horizon'):
        lines=original.copy()
        if fault=='one-bad-utf8-byte':
            buf=bytearray(lines[idx]);offset=buf.index(b'"seal":"')+8;buf[offset]=255;lines[idx]=bytes(buf)
        elif fault=='bad-timing-value':
            row=json.loads(lines[idx+1]);row['elapsed_ns']='broken';lines[idx+1]=canonical_bytes(row)+b'\n'
        else:
            header=json.loads(lines[0]);header['horizon']=121
            # Deliberately leave the copied seal invalid: suffix is untrusted.
            lines[idx]=canonical_bytes(header)+b'\n'
        source=folder/f'{kind}-{fault}.jsonl';dest=folder/f'{kind}-{fault}-recovered.jsonl'
        source.write_bytes(b''.join(lines));item=dict(kind=kind,fault=fault,source=str(source),output=str(dest),expected_last_good_tick=57 if fault=='bad-timing-value' else 56)
        try:
            r=read_run(source);item['reader']=dict(last_sealed_tick=r.last_sealed_tick,first_break_line=r.first_break_line,header_horizon=r.header['horizon'])
        except Exception as exc:item['reader']=dict(exception=type(exc).__name__,message=str(exc))
        try:
            r=recover(source,dest);item['recovery']=dict(resumed=r.resumed,last_sealed_tick=r.last_sealed_tick)
        except Exception as exc:item['recovery']=dict(exception=type(exc).__name__,message=str(exc))
        item['output_exists']=dest.exists()
        if dest.exists():
            check=read_run(dest);item['output']=dict(complete=check.complete,ticks=len(check.ticks),header_horizon=check.header['horizon'],end_ticks=check.end['ticks'],problems=check.problems,content_equal=content(dest)==content(reference(kind)))
        results.append(item)
save('minimal-findings',results)
