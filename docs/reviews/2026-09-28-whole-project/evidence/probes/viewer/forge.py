"""Forge a sealed run: rename an actor to an HTML payload, re-digest and re-seal every line.
Shows whether the seal chain is a tamper check (it has no secret, so it is not)."""
import json, sys, hashlib
from pathlib import Path
from kernel.canonical import canonical_bytes, digest
from stream.run_file import header_seal, tick_seal, apply_production, read_run

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
VICTIM = "p01"
EVIL = sys.argv[3] if len(sys.argv) > 3 else '<img src=x onerror="window.__pwned=7">'

def deep(o):
    if isinstance(o, dict): return {deep(k): deep(v) for k, v in o.items()}
    if isinstance(o, list): return [deep(x) for x in o]
    if isinstance(o, str): return o.replace(VICTIM, EVIL) if VICTIM in o else o
    return o

lines = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines()]
out = []
trail = hashlib.sha256()
seal = None; prev_chain = None
for ev in lines:
    kind = ev["kind"]
    if kind == "header":
        h = deep(ev)
        h["genesis_digest"] = digest(h["genesis"]); h["world_digest"] = digest(h["world"])
        h["config_identity"] = digest(h["scenario"])
        h["seal"] = header_seal(h); seal = h["seal"]; prev_chain = h["genesis_digest"]
        raw = json.dumps(h, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        out.append(raw); continue
    if kind == "tick":
        t = deep(ev)
        # kill the victim at the last tick so the deaths list is exercised
        if ev is lines[-2] or ev.get("tick") == max(x.get("tick",-1) for x in lines if x["kind"]=="tick"):
            t["world"]["died_at"][EVIL] = t["tick"]
        t["record"]["prior_state_digest"] = prev_chain
        t["state_digest"] = digest(t["state"]); t["record"]["next_state_digest"] = t["state_digest"]
        t["record_digest"] = digest(t["record"]); t["world_digest"] = digest(t["world"])
        if "production" in t:
            t["produced_state_digest"] = digest(apply_production(t["state"], t["production"]))
            prev_chain = t["produced_state_digest"]
        else:
            prev_chain = t["state_digest"]
        t.pop("seal", None); t["seal"] = tick_seal(seal, t); seal = t["seal"]
        raw = canonical_bytes(t) + b"\n"; trail.update(raw); out.append(raw); continue
    if kind == "end":
        e = dict(ev); e["trail_digest"] = trail.hexdigest(); e["final_seal"] = seal
        out.append(json.dumps(e, sort_keys=True, separators=(",", ":")).encode() + b"\n"); continue
    out.append(json.dumps(ev, sort_keys=True, separators=(",", ":")).encode() + b"\n")
OUT.write_bytes(b"".join(out))
r = read_run(OUT)
print("forged file complete (verifies):", r.complete, "| problems:", list(r.problems)[:3])
