"""Kernel attack probe: try to break conservation / authority / atomicity."""
import sys; sys.path.insert(0,'.')
from kernel import Engine, WorldState, transfer, consume
from kernel.proposals import Proposal, claim, deposit, OP_RESERVE, OP_COMPLETE, OP_CANCEL, OP_TRANSFER, OP_CLAIM
from kernel.state import Source
import inspect, kernel.proposals as P
print([n for n in dir(P) if not n.startswith('_')])

def fresh():
    return WorldState.genesis(tick=5, balances={"a":3,"b":0,"c":1},
        sources={"food": Source(stock=2, authorised=frozenset({"a","b","c"}))},
        holdings={"water":{"a":2,"b":0,"c":0}}, consumed_by={"water":0})

def run(label, props, state=None):
    st = state or fresh()
    e = Engine(st); t0 = st.totals()
    try:
        rec = e.tick(props)
    except Exception as ex:
        print(f"{label:45s} RAISED {type(ex).__name__}: {ex}"); return None
    outs = [(o.proposal_id, o.reason) for o in rec.outcomes]
    ok = e.state.totals()==t0
    print(f"{label:45s} totals_conserved={ok} {outs}")
    return e

run("negative amount", [transfer("x","a",0,to="b",amount=-1)])
run("zero amount", [transfer("x","a",0,to="b",amount=0)])
run("bool amount", [transfer("x","a",0,to="b",amount=True)])
run("float amount", [transfer("x","a",0,to="b",amount=1.0)])
run("huge amount", [transfer("x","a",0,to="b",amount=10**30)])
run("self transfer", [transfer("x","a",0,to="a",amount=1)])
run("to unknown actor", [transfer("x","a",0,to="zz",amount=1)])
run("from unknown actor", [transfer("x","zz",0,to="a",amount=1)])
run("overdraw", [transfer("x","a",0,to="b",amount=4)])
run("two spends sum > balance (3)", [transfer("x","a",0,to="b",amount=2), transfer("y","a",1,to="c",amount=2)])
run("credit then spend same tick", [transfer("x","a",0,to="b",amount=1), transfer("y","b",1,to="c",amount=1)])
run("dup proposal id", [transfer("x","a",0,to="b",amount=1), transfer("x","a",1,to="b",amount=1)])
run("dup actor order", [transfer("x","a",0,to="b",amount=1), transfer("y","a",0,to="b",amount=1)])
run("two claim last unit", [claim("x","a",0,sources={"food":2}), claim("y","b",0,sources={"food":2})])
run("claim unauthorised source", [claim("x","a",0,sources={"nope":1})])
run("deposit into food source", [deposit("x","a",0,source="food",amount=1)])
run("deposit water into food source", [deposit("x","a",0,source="food",amount=1,resource="water")])
run("consume more water than held", [consume("x","a",0,amount=3,resource="water")])
run("mixed resource params", [Proposal("x","a",0,OP_TRANSFER,{"to":"b","amount":1,"resource":"gold"})])
run("weird resource name", [Proposal("x","a",0,OP_TRANSFER,{"to":"b","amount":1,"resource":"actor:b"})])
run("weird target name", [Proposal("x","a",0,OP_TRANSFER,{"to":"actor:b","amount":1})])
run("target w/ colon", [Proposal("x","a",0,OP_TRANSFER,{"to":"b:water","amount":1})])
run("unknown op", [Proposal("x","a",0,"steal",{"to":"b","amount":1})])
try:
    Proposal("x","a",0,OP_TRANSFER,["to","b"])
except ValueError as ex: print("params not mapping: rejected at construction:", ex)

# reservations
e = run("reserve 2 of a", [Proposal("r","a",0,OP_RESERVE,{"operation":OP_TRANSFER,"params":{"to":"b","amount":2}})])
if e:
    aid = e.state.reservations and list(e.state.reservations)[0]
    print("  reservation:", aid, "availability a:", e.state.availability().get("actor:a"))
    st = e.state
    run("spend reserved units", [transfer("x","a",0,to="c",amount=2)], st)
    run("cancel+complete same tick", [Proposal("c","a",0,OP_CANCEL,{"action_id":aid}), Proposal("k","a",1,OP_COMPLETE,{"action_id":aid})], st)
    run("complete+cancel same tick", [Proposal("k","a",0,OP_COMPLETE,{"action_id":aid}), Proposal("c","a",1,OP_CANCEL,{"action_id":aid})], st)
    run("b completes a's reservation", [Proposal("k","b",0,OP_COMPLETE,{"action_id":aid})], st)
    run("complete twice", [Proposal("k","a",0,OP_COMPLETE,{"action_id":aid}), Proposal("k2","a",1,OP_COMPLETE,{"action_id":aid})], st)
    e2 = run("cancel then spend same tick", [Proposal("c","a",0,OP_CANCEL,{"action_id":aid}), transfer("x","a",1,to="c",amount=3)], st)
    run("complete unknown action", [Proposal("k","a",0,OP_COMPLETE,{"action_id":"action:deadbeef"})], st)
    run("complete with non-str action", [Proposal("k","a",0,OP_COMPLETE,{"action_id":5})], st)
    # reserve inside reserve
    run("reserve a reserve", [Proposal("r2","a",0,OP_RESERVE,{"operation":OP_RESERVE,"params":{"operation":OP_TRANSFER,"params":{"to":"b","amount":1}}})], st)
    run("reserve a cancel", [Proposal("r2","a",0,OP_RESERVE,{"operation":OP_CANCEL,"params":{"action_id":aid}})], st)
    # re-entry
    try:
        e.tick([]); print("re-enter same engine tick:", "allowed (tick advanced)", e.state.tick)
    except Exception as ex: print("re-enter:", type(ex).__name__, ex)
# order independence
import random
def outcomes_for(props):
    e=Engine(fresh()); r=e.tick(props); return tuple((o.proposal_id,o.reason) for o in r.outcomes), e.state.digest() if hasattr(e.state,'digest') else e.state.totals()
base=[transfer("x","a",0,to="b",amount=2), transfer("y","a",1,to="c",amount=2), claim("p","a",2,sources={"food":2}), claim("q","b",0,sources={"food":2}), claim("s","c",0,sources={"food":1})]
ref=outcomes_for(base)
for i in range(20):
    sh=base[:]; random.Random(i).shuffle(sh)
    assert outcomes_for(sh)==ref, i
print("order independence over 20 shuffles: OK")
# frozen state?
st=fresh()
try:
    st.balances["a"]=99; print("MUTATED balances dict in place! ->", st.balances["a"])
except Exception as ex: print("balances immutable:", type(ex).__name__)
try:
    Engine(st).state.sources["food"].stock=99; print("MUTATED source stock")
except Exception as ex: print("source immutable:", type(ex).__name__)
