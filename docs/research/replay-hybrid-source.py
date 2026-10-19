"""Controlled source-support replay; optional extracted baseline directory argument."""
import copy,json,tempfile
from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).resolve().parents[2]))
from forge import __version__
from forge.core import Workbench
from tests.test_workbench import ScriptedModels,await_job
from tests.fixtures import PLAN,APP,TEST
plan=copy.deepcopy(PLAN);plan['task_contract_version']=1
first={'title':'Implement task behavior','instructions':'Implement source and tests.','feature_indexes':list(range(len(plan['features']))),'files':['app.py','test_app.py'],'outcome':'Tasks can be created and listed.','depends_on':[],'done_when':['A created task appears in the list.']}
second={**copy.deepcopy(first),'title':'Inspect existing server','depends_on':[0]};plan['tasks']=[first,second]
support={'already_satisfied':{'reason':'The current app already defines the requested server implementation.','evidence':[{'file':'app.py','contains':APP[:80]}]}}
models=ScriptedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST}},{'edits':[{'file':'app.py','search':'not found','replace':'invalid'}]},support])
with tempfile.TemporaryDirectory() as d:
 b=Workbench(Path(d)/'projects',models);config={'provider':'ollama','model':'fixture'}
 s=await_job(b,b.create('Build a task tracker',config,config)['id']);b.approve(s['id'],s['plan']);b.start(s['id'],'build',{'execute':False,'repairs':0});s=await_job(b,s['id'])
 print(json.dumps({'version':__version__,'scope':'synthetic source-support replay, no live models or generated-code execution','status':s['status'],'saved_tasks':s['next_task'],'source_preserved':b.files(s['id'])['app.py']==APP,'behavior_verified':bool(s.get('checks')),'last_disposition':s['task_receipts'][-1].get('disposition'),'error':s.get('error')}))
