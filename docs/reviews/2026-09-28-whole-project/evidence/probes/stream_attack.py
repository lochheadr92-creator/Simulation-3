import sys, json, subprocess, shutil, os; sys.path.insert(0,'.')
from stream.run_file import read_run, RunFileError
SRC="../runs/full-7.jsonl"; D="../runs/dmg"; os.makedirs(D, exist_ok=True)
raw=open(SRC,'rb').read(); lines=raw.split(b"\n"); lines=[l for l in lines if l]
print("lines:",len(lines), "kinds:", {json.loads(l)["kind"] for l in lines})
def w(name, data):
    p=f"{D}/{name}.jsonl"; open(p,'wb').write(data); return p
def rd(p):
    try:
        r=read_run(p); return f"complete={r.complete} ticks={len(r.ticks)} problems={list(r.problems)[:2]}"
    except Exception as e: return f"{type(e).__name__}: {str(e)[:110]}"
def cli(*args):
    r=subprocess.run([sys.executable,"-B","-m","world.run",*args],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip().splitlines()[-1][:140] if (r.stdout+r.stderr).strip() else ""
cases={}
cases["truncated_midline"]=w("trunc", b"\n".join(lines[:150])+b"\n"+lines[150][:len(lines[150])//2])
cases["bad_utf8_suffix"]=w("utf8", b"\n".join(lines[:150])+b"\n"+b"\xff\xfe{garbage\n")
mid=bytearray(lines[100]); i=mid.find(b'"hunger"'); mid[i+12]^=1 if i>0 else 0
cases["bitflip_tick100"]=w("flip", b"\n".join(lines[:100]+[bytes(mid)]+lines[101:])+b"\n")
cases["dup_tick150"]=w("dup", b"\n".join(lines[:151]+[lines[150]]+lines[151:])+b"\n")
cases["swap_150_151"]=w("swap", b"\n".join(lines[:150]+[lines[151],lines[150]]+lines[152:])+b"\n")
cases["second_header_mid"]=w("hdr2", b"\n".join(lines[:150]+[lines[0]]+lines[150:])+b"\n")
h=json.loads(lines[0]); h["scenario"]["hunger_rate"]=2
cases["header_config_edit"]=w("hdrcfg", (json.dumps(h,separators=(",",":"),sort_keys=True)).encode()+b"\n"+b"\n".join(lines[1:])+b"\n")
cases["missing_end"]=w("noend", b"\n".join(lines[:-1])+b"\n")
cases["no_header"]=w("nohdr", b"\n".join(lines[1:])+b"\n")
cases["end_moved_early"]=w("earlyend", b"\n".join(lines[:150]+[lines[-1]]+lines[150:-1])+b"\n")
cases["empty"]=w("empty", b"")
cases["crlf"]=w("crlf", raw.replace(b"\n",b"\r\n"))
cases["trailing_blank_lines"]=w("blank", raw+b"\n\n\n")
cases["cut_clean_150"]=w("cut150", b"\n".join(lines[:151])+b"\n")
for k,p in cases.items():
    print(f"{k:22s} read: {rd(p)}")
    print(f"{'':22s} replay: {cli('--replay',p)}")
print("\n-- recovery from clean cut at tick 150 (active trips/casts likely) --")
out=f"{D}/recovered150.jsonl"
if os.path.exists(out): os.remove(out)
print("recover:", cli("--recover",cases["cut_clean_150"],"--out",out))
if os.path.exists(out):
    ref=read_run(SRC); rec=read_run(out)
    same = [a==b for a,b in zip(ref.ticks, rec.ticks)]
    print("recovered ticks:",len(rec.ticks),"identical to reference:",all(same), "first diff:", same.index(False) if False in same else None)
    print("replay recovered:", cli("--replay",out))
print("\n-- recovery from damaged files (should use sealed prefix only) --")
for k in ["truncated_midline","bitflip_tick100","bad_utf8_suffix","dup_tick150"]:
    o=f"{D}/rec_{k}.jsonl"
    if os.path.exists(o): os.remove(o)
    print(k, "recover:", cli("--recover",cases[k],"--out",o))
    if os.path.exists(o):
        rec=read_run(o); ref=read_run(SRC)
        print("   ticks",len(rec.ticks),"identical:", all(a==b for a,b in zip(ref.ticks,rec.ticks)), "replay:", cli("--replay",o))
