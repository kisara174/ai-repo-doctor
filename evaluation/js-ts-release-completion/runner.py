"""Source-backed static investigations; never execute target repository code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from xml.etree import ElementTree as ET

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--cli',type=Path)
p.add_argument('--baseline',action='store_true')
a=p.parse_args()
W=Path(__file__).resolve().parents[2]
B=Path('/Users/kisara/.local/share/ai-repo-doctor/evaluations/benchmark200-v1/checkouts')
assert a.out.is_absolute() and (not a.baseline or a.cli)
D=a.out; D.mkdir(parents=True,exist_ok=False); (D/'commands').mkdir();(D/'maps').mkdir()
cases=json.loads((Path(__file__).with_name('cases.json')).read_text())['cases']
cli=[str(a.cli)] if a.cli else ['/Users/kisara/.local/share/ai-repo-doctor/releases/v0.7.0/candidate/venvs/js/bin/python','-B','-m','repo_doctor']
env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','DEEPSEEK_API_KEY')};env['PYTHONDONTWRITEBYTECODE']='1'
commands=[];reviews=[]
sha=lambda b:hashlib.sha256(b).hexdigest()
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def identity(c):
 root=B/c['repo_id']; assert git(root,'rev-parse','HEAD')==c['commit'] and git(root,'rev-parse','HEAD^{tree}')==c['tree'];assert not git(root,'status','--porcelain')
 hashes={f:sha((root/f).read_bytes()) for f in c['sources']};assert hashes=={f:r['sha256'] for f,r in c['sources'].items()}
 for r in c['imports']:assert (root/c['component']['file']).read_text().splitlines()[r['line']-1]==r['quote']
 return dict(commit=c['commit'],tree=c['tree'],sources=hashes,git_status='clean')
def run(name,*args,expected=0):
 argv=cli+list(map(str,args));cwd=D if a.cli else W;start=time.monotonic();r=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',timeout=180)
 record=dict(argv=argv,cwd=str(cwd),expected_exit_code=expected,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,duration_seconds=time.monotonic()-start,stdout_sha256=sha(r.stdout.encode()),stderr_sha256=sha(r.stderr.encode()))
 filename=f'{len(commands)+1:02d}-{name}.json';(D/'commands'/filename).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');commands.append(dict(name=name,record=filename,expected_exit_code=expected,exit_code=r.returncode));assert r.returncode==expected,(name,r.stderr[-1000:]);return json.loads(r.stdout) if expected==0 else None
for c in cases:
 rid=c['repo_id'];root=B/rid;before=identity(c);component=c['component'];sid=component['id'];opts=['--languages','javascript,typescript','--json']
 overview=run(rid+'-overview','overview',root,*opts)
 matches=run(rid+'-symbols','symbols',root,'--query',component['name'],*opts)['matches'];found=[m for m in matches if m['id']==sid]
 if a.baseline:assert not found
 else:
  assert len(found)==1;sid=found[0]['id'];assert found[0]['start_line']==component['start_line']
 callee=None
 if c['call']:
  matches=run(rid+'-helper-symbols','symbols',root,'--query',c['call']['callee_query'],*opts)['matches'];selected=[m for m in matches if m['id']==c['call']['callee_id']];assert len(selected)==1;callee=selected[0]['id'];assert selected[0]['start_line']==c['call']['callee_start_line']
 context=run(rid+'-context','context',root,sid,*(['--include-symbol',callee] if callee else []),'--max-lines','120',*opts,expected=2 if a.baseline else 0)
 impact=run(rid+'-impact','impact',root,callee or sid,'--depth','2',*opts,expected=2 if a.baseline and not callee else 0)
 mapping=run(rid+'-map','map',root,'--out',D/'maps'/rid,*opts);directory=Path(mapping['map_json']).parent;graph=json.loads((directory/'map.json').read_text());assert {x.name for x in directory.iterdir()}=={'map.json','map.html','structure.svg','relations.svg'}
 projections={}
 for name,view in graph['views'].items():
  ids={n['id'] for n in view['nodes']};assert len(ids)<=200 and len(view['edges'])<=500;assert all(e['source'] in ids and e['target'] in ids for e in view['edges'])
  actual={e.get('data-edge-id') for e in ET.parse(directory/(name+'.svg')).findall('.//{http://www.w3.org/2000/svg}path') if e.get('data-edge-id') is not None};assert actual=={e['id'] for e in view['edges']};projections[name]=dict(nodes=len(ids),edges=len(actual))
 imports=[e for e in graph['edges'] if e['kind']=='import' and e['source']=='file:'+component['file']]
 for r in c['imports']:
  edges=[e for e in imports if e['target']=='file:'+r['target'] and any(x['line']==r['line'] for x in e['evidence'])];assert bool(edges)==(not a.baseline)
 edges=[e for e in graph['edges'] if e['kind']=='call' and e['source']=='symbol:'+sid]
 if not c['call']:assert not edges,'JSX tag or callback falsely connected'
 count=0;call=None
 if context:
  for block in context['blocks']:
   lines=(root/block['file']).read_text(encoding='utf-8-sig').splitlines()
   for line in block['lines']:assert lines[line['line']-1]==line['text'];count+=1
  assert count<=120
  block=next(b for b in context['blocks'] if b['symbol']==sid)
  assert (block['start_line'],block['end_line'])==(component['start_line'],component['end_line']) and not block['truncated']
  assert [l['text'] for l in block['lines']]==component['quote']
 if c['call']:
  affected=[r for r in impact['affected_symbols'] if r['symbol']==sid]
  if a.baseline:assert not affected
  else:
   ce=[e for e in context['call_evidence'] if e['caller']==sid and e['callee']==callee and e['line']==c['call']['line']];assert len(ce)==1 and len(affected)==1;call=ce[0];proof=call['via_esm_import'];r=c['imports'][0];assert (proof['file'],proof['start_line'],proof['specifier'],proof['resolved_file'],proof['resolution_kind'])==(component['file'],r['line'],r['specifier'],r['target'],'unique-extensionless-source');assert affected[0]['call_path_evidence']==[call];assert context['analysis']['esm_source_resolution']['runtime_resolution'] is False
 assert identity(c)==before
 reviews.append(dict(repo_id=rid,identity=before,component_found=bool(found),context_lines=count,budget_exhausted=context['budget_exhausted'] if context else None,direct_call=call,projections=projections,map_sha256={x.name:sha(x.read_bytes()) for x in directory.iterdir()},stats=overview['stats']))
 print('verified',rid,flush=True)
summary=dict(schema_version=1,status='verified-baseline-unsupported' if a.baseline else 'passed-directed-frontend',baseline=a.baseline,cli=cli,source_commit=git(W,'rev-parse','HEAD'),cases_sha256=sha(Path(__file__).with_name('cases.json').read_bytes()),commands=commands,reviews=reviews,target_code_executed=False,target_dependencies_installed=False,target_sources_unchanged=True,full_200_regression=False,browser_interaction_performed=False)
(D/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(summary['status'],len(commands),flush=True)
