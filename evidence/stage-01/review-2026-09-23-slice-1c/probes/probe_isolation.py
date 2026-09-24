from common import *
from collections.abc import Mapping
from dataclasses import is_dataclass, fields, FrozenInstanceError
from stream.recover import restore_engine
from stream.run_file import read_run, decode_input

path=reference('scenario'); tick=33
a,b,c=[restore_engine(path,tick) for _ in range(3)]
before=b.state.digest(); initial=a.state.digest(); stored=read_run(path).ticks[tick+1]
def objects(obj,path='',seen=None):
    seen=set() if seen is None else seen
    if id(obj) in seen:return {}
    seen.add(id(obj));found={}
    if isinstance(obj,(Mapping,list,set)) or is_dataclass(obj):found[id(obj)]=path
    if isinstance(obj,Mapping):
        for key,val in obj.items():found.update(objects(val,path+f'[{key!r}]',seen))
    elif isinstance(obj,(list,tuple,set,frozenset)):
        for i,val in enumerate(obj):found.update(objects(val,path+f'[{i}]',seen))
    elif is_dataclass(obj):
        for f in fields(obj):found.update(objects(getattr(obj,f.name),path+'.'+f.name,seen))
        if hasattr(obj,'__dict__'):found.update(objects(obj.__dict__,path+'.__dict__',seen))
    return found
oa,ob=objects(a.state,'state'),objects(b.state,'state')
shared=[(oa[i],ob[i]) for i in oa.keys() & ob.keys()]
blocked=[]
def try_write(name,fn):
    try:fn();blocked.append(dict(path=name,blocked=False))
    except (AttributeError,TypeError,FrozenInstanceError) as exc:blocked.append(dict(path=name,blocked=True,exception=type(exc).__name__))
for name in ('balances','sources','reservations'):
    mapping=getattr(a.state,name); key=next(iter(mapping))
    try_write(name,lambda m=mapping,k=key:m.__setitem__(k,m[k]))
for sid,source in a.state.sources.items():
    try_write('source.'+sid+'.stock',lambda s=source:setattr(s,'stock',s.stock+1))
    try_write('source.'+sid+'.authorised',lambda s=source:s.authorised.add('intruder'))
for rid,res in a.state.reservations.items():
    for f in fields(res):try_write('reservation.'+rid+'.'+f.name,lambda r=res,n=f.name:setattr(r,n,getattr(r,n)))
    for i,effect in enumerate(res.effects):try_write(f'reservation.{rid}.effects.{i}',lambda e=effect:setattr(e,'delta',0))
copy=a.state.canonical();copy['balances'].clear();copy['sources'].clear();copy['reservations'].clear()
detached_unchanged=a.state.digest()==initial and b.state.digest()==before
view=a.view_for('p1')
try_write('view.balances',lambda:view.balances.__setitem__('p1',0))
proposals=[decode_input(x) for x in stored['inputs']]
for proposal in proposals:try_write('proposal.'+proposal.proposal_id+'.params',lambda p=proposal:p.params.__setitem__('amount',999))
record=a.tick(proposals); bdigest_after=b.state.digest(); cdigest_after=c.state.digest()
recordcopy=record.canonical(); recordcopy['outcomes'].clear()
for out in record.outcomes:
    try_write('outcome.'+out.proposal_id+'.reason',lambda o=out:setattr(o,'reason','edited'))
    if out.reservation:try_write('outcome.'+out.proposal_id+'.reservation.actor',lambda o=out:setattr(o.reservation,'actor','intruder'))
records_private=not (objects(record).keys() & objects(b.state).keys())
b.tick([decode_input(x) for x in stored['inputs']]);c.tick([decode_input(x) for x in stored['inputs']])
ordinary_equal=a.state.digest()==b.state.digest()==c.state.digest()==stored['state_digest']
# Even reflective mutation in a disposable A must not cross to B or C.
x,y,z=[restore_engine(path,tick) for _ in range(3)]; y0=y.state.digest();z0=z.state.digest()
for source in x.state.sources.values():source.__dict__['stock']+=1
for res in x.state.reservations.values():
    res.__dict__['operation']='probe-local'
    for effect in res.effects:effect.__dict__['delta']=0
save('P6-isolation',dict(tick=tick,holds=len(restore_engine(path,tick).state.reservations),objects_checked_a=len(oa),objects_checked_b=len(ob),shared_objects=shared,mutation_attempts=blocked,canonical_copy_detached=detached_unchanged,unticked_b_unchanged=bdigest_after==before,unticked_c_unchanged=cdigest_after==before,record_no_shared_objects_with_b=records_private,three_independent_advances_match=ordinary_equal,reflective_a_changed=x.state.digest()!=y0,reflective_b_unchanged=y.state.digest()==y0,reflective_c_unchanged=z.state.digest()==z0))
