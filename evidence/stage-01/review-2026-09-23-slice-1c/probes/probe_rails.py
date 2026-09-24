from common import *
import hashlib, ast, xml.etree.ElementTree as ET, collections, platform

def git(name,args):
    p=subprocess.run(['git']+args,cwd=REPO,capture_output=True)
    (OUT/(name+'.stdout.txt')).write_bytes(p.stdout);(OUT/(name+'.stderr.txt')).write_bytes(p.stderr)
    save(name+'.command',dict(argv=['git']+args,returncode=p.returncode,cwd=str(REPO)))
    return p.stdout

base='6f500408b59e69f6f9c0da2be14172bb2f30a993'; target='d14decec50d285395febb97c06d8eb7d94930b88'
diff=git('P9-full-diff',['diff',base,target]); names=git('P9-changed-files',['diff','--name-only',base,target]).decode().splitlines()
protected_prefixes=('automation/','tests/fixtures/','evidence/stage-01/slice-1b/','evidence/stage-01/instrument/')
protected_files=('kernel/settlement.py','kernel/engine.py','kernel/proposals.py','kernel/version.py','world/decide.py')
old=git('P9-original-state',['show',base+':kernel/state.py']).decode();new=(REPO/'kernel/state.py').read_text()
old_ast=ast.parse(old);new_ast=ast.parse(new)
def unchanged_ast(old,new):
    new=copy_ast=ast.parse(ast.unparse(new))
    new.body=[n for n in new.body if not isinstance(n,ast.FunctionDef) or n.name!='_canonical_map']
    for n in new.body:
        if isinstance(n,ast.ClassDef):n.body=[m for m in n.body if not isinstance(m,ast.FunctionDef) or m.name!='from_canonical']
    return ast.dump(old)==ast.dump(new)
decl=git('P9-original-declaration',['show','56d3c3fe746f22ca58f4219a9ac0aa3b16293623:evidence/stage-01/RECORD.md']).decode()
latest=(REPO/'evidence/stage-01/RECORD.md').read_text()
def numbered(text):return text[text.index('1. **Format and header.**'):text.index('Changes from the 2026-09-23 build brief')].replace('\r\n','\n')
save('P9-rails',dict(changed_files=names,protected_changes=[n for n in names if n.startswith(protected_prefixes) or n in protected_files],state_additive_only_ast=unchanged_ast(old_ast,new_ast),declaration_items_1_13_identical=numbered(decl)==numbered(latest),declaration_sha256=hashlib.sha256(numbered(decl).encode()).hexdigest()))

xml=ET.parse(OUT/'R1-junit.xml');groups=collections.defaultdict(collections.Counter); errors=[]
for case in xml.iter('testcase'):
    name=case.attrib['classname']; result='passed'
    for tag in ('failure','error','skipped'):
        el=case.find(tag)
        if el is not None:
            result=tag
            if tag in ('error','failure'):errors.append(dict(file=name,test=case.attrib['name'],message=el.attrib.get('message'),text=el.text))
    groups[name][result]+=1
automation={'test_orchestrator','test_orchestrator_audit','test_orchestrator_execution','test_preflight','test_run_gate','test_runtime_and_startup','test_verify_evidence'}
parts={'automation':collections.Counter(),'simulation':collections.Counter()}
for name,counts in groups.items(): parts['automation' if name.split('.')[-1] in automation else 'simulation'].update(counts)
save('R1-partition',dict(files=groups,parts=parts,errors=errors))
