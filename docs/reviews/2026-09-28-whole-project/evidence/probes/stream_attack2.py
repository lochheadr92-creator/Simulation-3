import sys, json, subprocess, os; sys.path.insert(0,'.')
from stream.run_file import read_run
SRC="../runs/full-7.jsonl"; D="../runs/dmg"
raw=open(SRC,'rb').read(); lines=[l for l in raw.split(b"\n") if l]
ticks=[i for i,l in enumerate(lines) if json.loads(l)["kind"]=="tick"]
timing=[i for i,l in enumerate(lines) if json.loads(l)["kind"]=="timing"]
print("tick lines", len(ticks), "timing lines", len(timing))
def w(name,ls): p=f"{D}/{name}.jsonl"; open(p,'wb').write(b"\n".join(ls)+b"\n"); return p
def rd(p):
    r=read_run(p); return f"complete={r.complete} ticks={len(r.ticks)} problems={list(r.problems)[:2]}"
def cli(*a):
    r=subprocess.run([sys.executable,"-B","-m","world.run",*a],capture_output=True,text=True); s=(r.stdout+r.stderr).strip(); return r.returncode, s.splitlines()[-1][:150] if s else ""
c={}
t=ticks[100]; L=list(lines); obj=json.loads(L[t]); 
# semantic edit: change a hunger value inside world state, re-serialize canonically (sorted, compact) so only content differs
who=next(iter(obj["world"]["hunger"])); obj["world"]["hunger"][who]+=1
L[t]=json.dumps(obj,separators=(",",":"),sort_keys=True,ensure_ascii=False).encode()
c["edit_world_hunger_t100"]=w("edit_hunger",L)
L=list(lines); obj=json.loads(L[t]); o=obj["record"]["outcomes"][0]; o["accepted"]= not o["accepted"]
L[t]=json.dumps(obj,separators=(",",":"),sort_keys=True,ensure_ascii=False).encode(); c["flip_outcome_t100"]=w("flip_outcome",L)
L=list(lines); obj=json.loads(L[t]); a=next(iter(obj["state"]["balances"])); obj["state"]["balances"][a]+=1
L[t]=json.dumps(obj,separators=(",",":"),sort_keys=True,ensure_ascii=False).encode(); c["edit_balance_t100"]=w("edit_balance",L)
L=list(lines); L.insert(ticks[150]+1, lines[ticks[150]]); c["dup_tick150"]=w("dup_tick",L)
L=list(lines); L[ticks[150]],L[ticks[151]]=L[ticks[151]],L[ticks[150]]; c["swap_ticks_150_151"]=w("swap_tick",L)
L=list(lines); del L[ticks[150]]; c["delete_tick150"]=w("del_tick",L)
L=[l for i,l in enumerate(lines) if i not in timing]; c["timing_stripped"]=w("no_timing",L)
L=list(lines); obj=json.loads(L[timing[10]]); obj["elapsed_ms"]=999999 if "elapsed_ms" in obj else obj.get(list(obj)[-1]); L[timing[10]]=json.dumps(obj,separators=(",",":"),sort_keys=True).encode(); c["timing_edited"]=w("timing_edit",L)
# replace last 100 ticks with a re-run of a different seed's ticks? (splice)  — skip; instead splice tick 200.. from seed 11 file
other=[l for l in open("../runs/full-11.jsonl",'rb').read().split(b"\n") if l]; oticks=[l for l in other if json.loads(l)["kind"]=="tick"]
L=lines[:ticks[200]]+oticks[200:]+[lines[-1]]; c["splice_other_seed_from_200"]=w("splice",L)
# truncate mid tick 150 then recover: compare
L=lines[:ticks[150]]; L.append(lines[ticks[150]][:200]); c["cut_mid_tick150"]=w("cut_mid",L)
for k,p in c.items():
    print(f"{k:26s} read: {rd(p)}")
    print(f"{'':26s} replay: {cli('--replay',p)}")
o=f"{D}/rec_cutmid.jsonl"; os.path.exists(o) and os.remove(o)
print("recover cut_mid:", cli("--recover",c["cut_mid_tick150"],"--out",o))
if os.path.exists(o):
    ref=read_run(SRC); rec=read_run(o); print("  identical to reference:", ref.ticks==rec.ticks, "replay:", cli("--replay",o))
o=f"{D}/rec_edit.jsonl"; os.path.exists(o) and os.remove(o)
print("recover edited tick100 file:", cli("--recover",c["edit_world_hunger_t100"],"--out",o))
if os.path.exists(o):
    ref=read_run(SRC); rec=read_run(o); print("  ticks",len(rec.ticks),"identical:", ref.ticks==rec.ticks)
