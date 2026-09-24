from common import *
from probe_integrity import wire, inspect, attempt_recover
lines=reference('scenario').read_bytes().splitlines(keepends=True)
idx=next(i for i,line in enumerate(lines) if json.loads(line).get('kind')=='tick' and json.loads(line)['tick']==57)
h=json.loads(lines[0]);h['horizon']=121
changed=lines.copy();changed[idx]=wire(h)
source=DATA/'suffix-header-horizon.jsonl';source.write_bytes(b''.join(changed))
result=dict(reader=inspect(source),recovery=attempt_recover('suffix-header-horizon',source))
dest=DATA/'suffix-header-horizon-recovered.jsonl'
if dest.exists():result['recovered_reader']=inspect(dest)
save('extra-unsealed-header',result)
# A nonempty malformed record evades the reader's `or {}` fallback.
changed=lines.copy();row=json.loads(changed[idx]);row['record']=[1];changed[idx]=wire(row)
source=DATA/'suffix-nonempty-record.jsonl';source.write_bytes(b''.join(changed))
save('extra-nonempty-record',dict(reader=inspect(source),recovery=attempt_recover('suffix-nonempty-record',source)))
