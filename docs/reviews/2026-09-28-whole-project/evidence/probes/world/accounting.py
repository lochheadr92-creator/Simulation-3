"""Independent accounting sweep over saved runs (reads JSONL only, recomputes everything)."""
import sys, json, collections; sys.path.insert(0,'.')
from stream.run_file import read_run, apply_production
from kernel.canonical import digest

def totals(state):
    t = {None: sum(state["balances"].values()) + sum(s["stock"] for s in state["sources"].values() if s.get("resource") is None) + state["consumed"]}
    for res, held in (state.get("holdings") or {}).items():
        t[res] = sum(held.values()) + sum(s["stock"] for s in state["sources"].values() if s.get("resource")==res) + (state.get("consumed_by") or {}).get(res,0)
    return t

def check(path):
    run = read_run(path)
    hdr = run.header; cfg = hdr["scenario"]
    print(f"\n== {path}  complete={run.complete} ticks={len(run.ticks)} problems={getattr(run,'problems',None)}")
    prev_state = hdr["genesis"]
    prev_world = hdr.get("world")
    issues = collections.Counter(); notes=[]
    sink_prev = prev_state["consumed"]; cap = cfg.get("source_cap")
    dead_seen=set()
    for i, t in enumerate(run.ticks):
        committed = t["state"]; prod = t.get("production", [])
        # 1. settlement conserves totals vs previous processed state
        if totals(committed) != totals(prev_state):
            issues["settlement_total_changed"]+=1; notes.append((t["tick"],"settle",totals(prev_state),totals(committed)))
        # 2. produced state == committed + production (independent recompute)
        produced = apply_production(json.loads(json.dumps(committed)), prod) if prod else committed
        if prod and digest(produced) != t["produced_state_digest"]:
            issues["produced_digest_mismatch"]+=1
        # 3. production semantics
        for e in prod:
            if "born" in e:
                if produced["balances"][e["born"]]!=0: issues["born_with_food"]+=1
                for res,h in (produced.get("holdings") or {}).items():
                    if h.get(e["born"],0)!=0: issues["born_with_"+res]+=1
            elif "source_created" in e:
                if produced["sources"][e["source_created"]]["stock"]!=0: issues["cache_created_with_stock"]+=1
            elif "source" in e:
                if e["amount"]<=0: issues["nonpositive_renewal"]+=1
                st = produced["sources"][e["source"]]["stock"]
                if cap is not None and st>cap and not e["source"].startswith("store"): issues["renewal_over_cap"]+=1; notes.append((t["tick"],"cap",e,st))
        # 4. sink monotone
        if committed["consumed"] < sink_prev: issues["sink_decreased"]+=1
        sink_prev = committed["consumed"]
        # 5. dead people's balances
        world = t.get("world") or {}
        died = world.get("died_at") or {}
        for who in died:
            if who not in dead_seen:
                dead_seen.add(who)
                bal = produced["balances"].get(who,0); w=(produced.get("holdings") or {}).get("water",{}).get(who,0)
                if bal or w: issues["dead_holding_units"]+=1; notes.append((t["tick"],"dead",who,bal,w))
        # any accepted outcome where a dead actor is the proposer at a later tick?
        for o in t["record"]["outcomes"]:
            if o["actor"] in died and died[o["actor"]] < t["tick"] and o["accepted"]:
                issues["dead_actor_accepted_later"]+=1; notes.append((t["tick"],"deadact",o["actor"],o["operation"]))
            for eff in o.get("effects",[]):
                acct=eff["account"]
                if acct.startswith("actor:"):
                    a=acct.split(":")[1]
                    if a in died and died[a] < t["tick"] and eff["delta"]>0:
                        issues["credit_to_dead"]+=1; notes.append((t["tick"],"credit_dead",a,o["operation"],o["actor"]))
        # 6. reservations reference living actors
        for rid,r in (committed.get("reservations") or {}).items():
            if r["actor"] in died and died[r["actor"]] < t["tick"]:
                issues["dead_reservation_lingering"]+=1
        prev_state = produced
    stranded = sum(prev_state["balances"].get(w,0) for w in dead_seen)
    print("issues:", dict(issues) or "none")
    print("deaths:", len(dead_seen), "food stranded on the dead at end:", stranded, "final sink:", prev_state["consumed"], "final totals:", totals(prev_state))
    for n in notes[:12]: print("  ", n)

for p in sys.argv[1:]: check(p)
