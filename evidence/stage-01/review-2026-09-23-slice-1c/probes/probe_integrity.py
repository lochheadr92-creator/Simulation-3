from common import *
import hashlib, copy, statistics, traceback
from dataclasses import asdict
from kernel.canonical import canonical_bytes, digest
from stream.run_file import read_run
from stream.replay import replay_scenario
from stream.recover import recover_scenario
from world.recover import recover_world

def wire(value):
    return canonical_bytes(value) + b'\n'

def reseal(rows):
    # Independent implementation of declaration item 3. No stream seal helpers.
    rows=copy.deepcopy(rows); prev=None; trail=hashlib.sha256()
    for row in rows:
        if row['kind']=='header':
            row.pop('seal',None); prev=digest(row); row['seal']=prev
        elif row['kind']=='tick':
            row.pop('seal',None); prev=digest({'prev':prev,'tick':digest(row)}); row['seal']=prev
            trail.update(wire(row))
        elif row['kind']=='end':
            row['final_seal']=prev; row['trail_digest']=trail.hexdigest()
    return b''.join(wire(row) for row in rows)

def inspect(path):
    try:
        r=read_run(path)
        return dict(complete=r.complete,last_sealed_tick=r.last_sealed_tick,first_break_line=r.first_break_line,problems=r.problems,header_run_id=r.header.get('run_id'))
    except Exception as exc:
        return dict(exception=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())

def attempt_recover(label,source,module='stream'):
    dest=DATA/(label+'-recovered.jsonl')
    rc=run(label,['-m',module+'.run','--recover',str(source),'--out',str(dest)])
    return dict(returncode=rc,output_exists=dest.exists(),content_equal=dest.exists() and content(dest)==content(reference('scenario' if module=='stream' else 'world')))

def main():
    results={}
    files={p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for directory in ('kernel','stream','world') for p in sorted((REPO/directory).rglob('*.py'))}
    for kind in ('scenario','world'):
        raw=reference(kind).read_bytes(); lines=raw.splitlines(keepends=True); rows=[json.loads(x) for x in lines]
        h=rows[0]; ticks=[x for x in rows if x['kind']=='tick']; end=rows[-1]
        prev=digest({k:v for k,v in h.items() if k!='seal'}); checks=[prev==h['seal']]; trail=hashlib.sha256()
        for line,row in zip(lines,rows):
            if row['kind']!='tick': continue
            prev=digest({'prev':prev,'tick':digest({k:v for k,v in row.items() if k!='seal'})})
            checks.append(prev==row['seal']); trail.update(line)
        changed=copy.deepcopy(rows)
        for row in changed:
            if row['kind']=='timing': row['elapsed_ns']=987654321
        original_content=[wire(r) for r in rows if r['kind']!='timing']
        resealed_content=[x for x in reseal(changed).splitlines(keepends=True) if json.loads(x)['kind']!='timing']
        shares={k:statistics.mean(len(canonical_bytes(t[k]))/len(wire(t))*100 for t in ticks) for k in ('state','record','inputs')}
        results[kind]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),header_seal=h['seal'],every_seal_matches=all(checks),checked_seals=len(checks),final_seal=prev,final_matches=prev==end['final_seal'],trail_digest=trail.hexdigest(),trail_matches=trail.hexdigest()==end['trail_digest'],ticks=len(ticks),horizon=h['horizon'],end_ticks=end['ticks'],timing_count=sum(r['kind']=='timing' for r in rows),timing_outside_seals_and_trail=original_content==resealed_content,code_file_count=len(files),code_digest=digest(files),code_matches=h['code_identity']=={'files':files,'digest':digest(files)},config_matches=h['config_identity']==digest(h['scenario']),header_keys=sorted(h),header_provenance_keys=[k for k in h if any(w in k for w in ('git','host','clock','time','path'))],relative_code_paths=all(not Path(p).is_absolute() and '\\' not in p for p in files),bytes_per_tick=len(raw)/len(ticks),mean_tick_line_bytes=statistics.mean(len(wire(t)) for t in ticks),mean_field_share_percent=shares,timing_ms_mean=statistics.mean(r['elapsed_ns'] for r in rows if r['kind']=='timing')/1e6,input_count=sum(len(t['inputs']) for t in ticks),typed_input_count=sum('params_typed' in i for t in ticks for i in t['inputs']),empty_ticks=sum(not t['inputs'] for t in ticks),max_live_holds=max(len(t['state']['reservations']) for t in ticks),released_unique_ids=len(set().union(*(set(a['state']['reservations'])-set(b['state']['reservations']) for a,b in zip(ticks,ticks[1:])))))
    save('P1-P2-R7-independent',results)

    lines=reference('scenario').read_bytes().splitlines(keepends=True); rows=[json.loads(x) for x in lines]
    indices={r['tick']:i for i,r in enumerate(rows) if r['kind']=='tick'}; target=57; idx=indices[target]
    variants={}
    flip=lines.copy(); buf=bytearray(flip[idx]); n=buf.index(b'"seal":"')+8; buf[n]=ord('0') if buf[n]!=ord('0') else ord('1'); flip[idx]=bytes(buf)
    variants['seal-byte']=(flip,56,idx+1)
    edit=lines.copy(); h=copy.deepcopy(rows[0]);h['run_id']='edited';edit[0]=wire(h);variants['header-edit']=(edit,-1,1)
    deletion=lines.copy();del deletion[idx];variants['delete-tick']=(deletion,56,indices[58])
    swap=lines.copy();swap[idx],swap[indices[58]]=swap[indices[58]],swap[idx];variants['swap-ticks']=(swap,56,idx+1)
    variants['partial-line']=(lines[:idx]+[lines[idx][:len(lines[idx])//2]],56,idx+1)
    timing=lines.copy();row=copy.deepcopy(rows[idx+1]);row['elapsed_ns']=123456789;timing[idx+1]=wire(row);variants['timing-edit']=(timing,119,None)
    variants['trailing-junk']=(lines+[b'not JSON\n'],119,len(lines)+1)
    # Additional adversarial suffixes: valid prefix must survive arbitrary unreadable suffixes.
    malformed=lines.copy();row=copy.deepcopy(rows[idx]);row['record']=[];malformed[idx]=wire(row);variants['record-wrong-type']=(malformed,56,idx+1)
    invalid=lines.copy(); invalid[idx]=b'\xff\n';variants['non-utf8']=(invalid,56,idx+1)
    invalidtime=lines.copy();row=copy.deepcopy(rows[idx+1]);row['elapsed_ns']='broken';invalidtime[idx+1]=wire(row);variants['timing-wrong-type']=(invalidtime,57,idx+2)
    second=lines.copy(); h2=copy.deepcopy(rows[0]);h2['run_id']='untrusted suffix header';second[idx]=wire(h2);variants['second-header']=(second,56,idx+1)
    checks={}
    for name,(data,last,brk) in variants.items():
        path=DATA/('P3-'+name+'.jsonl');path.write_bytes(b''.join(data));actual=inspect(path)
        checks[name]=dict(expected_last=last,expected_break=brk,actual=actual,matches=actual.get('last_sealed_tick')==last and actual.get('first_break_line')==brk and 'exception' not in actual)
        if name in ('record-wrong-type','non-utf8','timing-wrong-type','second-header'):
            checks[name]['recovery']=attempt_recover('P3-'+name,path)
    save('P3-reader',checks)

    forged=copy.deepcopy(rows); tick=forged[indices[37]]; tick['availability'][sorted(tick['availability'])[0]]+=1
    path=DATA/'P4-forged-availability.jsonl';path.write_bytes(reseal(forged)); replay=replay_scenario(path)
    save('P4-forgery',dict(reader=inspect(path),replay={**asdict(replay),'path':str(replay.path)},expected_tick=37,expected_field='availability'))
    run('P4-replay',['-m','stream.run','--replay',str(path)])

    ticks=[r for r in rows if r['kind']=='tick']; holds=lambda t:t['state']['reservations']
    created=next(t['tick'] for t in ticks[10:-1] if any(h['created_tick']==t['tick'] for h in holds(t).values()))
    released=next(a['tick'] for a,b in zip(ticks[20:-1],ticks[21:]) if set(holds(a))-set(holds(b)))
    chosen=list(dict.fromkeys([created,released,73])); assert len(chosen)==3 and all(holds(ticks[t]) for t in chosen)
    recovery={}
    for t in chosen:
        path=DATA/f'P5-cut{t}.jsonl';path.write_bytes(b''.join(lines[:indices[t]+1])); recovery[str(t)]=dict(holds=len(holds(ticks[t])),created_on_tick=[k for k,v in holds(ticks[t]).items() if v['created_tick']==t],released_next_tick=sorted(set(holds(ticks[t]))-set(holds(ticks[t+1]))),**attempt_recover(f'P5-cut{t}',path))
    broken=DATA/'P5-broken-middle.jsonl';broken.write_bytes(b''.join(flip));recovery['broken-middle']=attempt_recover('P5-broken-middle',broken)
    existing=DATA/'P5-never-overwrite.jsonl';existing.write_bytes(b'KEEP THIS FILE\n');before=existing.read_bytes()
    rc=run('P5-never-overwrite',['-m','stream.run','--recover',str(broken),'--out',str(existing)])
    recovery['never-overwrite']=dict(returncode=rc,unchanged=existing.read_bytes()==before)
    # Explicit refusal cases, checking file noncreation.
    refused={'complete':reference('scenario'),'broken-header':DATA/'P3-header-edit.jsonl'}
    other=copy.deepcopy(rows[:indices[40]+1]);other[0]['code_identity']['files']['kernel/state.py']='0'*64;other[0]['code_identity']['digest']=digest(other[0]['code_identity']['files'])
    path=DATA/'P5-other-code.jsonl';path.write_bytes(reseal(other));refused['other-code']=path
    altered=copy.deepcopy(rows[:indices[40]+1]);chosenrow=next(r for r in altered if r['kind']=='tick' and r['tick']>=12 and r['inputs']);chosenrow['inputs'][0]['order']+=7
    path=DATA/'P5-generator-mismatch.jsonl';path.write_bytes(reseal(altered));refused['generator-mismatch']=path
    worldlines=reference('world').read_bytes().splitlines(keepends=True);path=DATA/'P5-world-cut.jsonl';path.write_bytes(b''.join(worldlines[:82]));refused['wrong-kind']=path
    for name,path in refused.items():recovery['refusal-'+name]=attempt_recover('P5-refusal-'+name,path)
    recovery['world-wrong-kind']=attempt_recover('P5-world-wrong-kind',broken,'world')
    existingworld=DATA/'P5-world-never-overwrite.jsonl';existingworld.write_bytes(b'KEEP WORLD\n')
    rc=run('P5-world-never-overwrite',['-m','world.run','--recover',str(refused['wrong-kind']),'--out',str(existingworld)])
    recovery['world-never-overwrite']=dict(returncode=rc,unchanged=existingworld.read_bytes()==b'KEEP WORLD\n')
    save('P5-recovery',recovery)

if __name__=='__main__': main()
