"""Controlled replay. Optional argument: an extracted baseline release root."""
import copy,json,tempfile
from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).resolve().parents[2]))
from forge import __version__
from forge.contracts import validate_structure
from forge.core import Workbench
from tests.fixtures import PLAN,APP,TEST
from tests.test_workbench import ScriptedModels,await_job
plan=copy.deepcopy(PLAN);plan['task_contract_version']=1
plan['tasks']=[{'title':'One task increment','instructions':'Implement task behavior and tests.', 'feature_indexes':list(range(len(plan['features']))),'outcome':'Create and list tasks.', 'files':['app.py','test_app.py'],'depends_on':[],'done_when':['A saved task is listed.']}]
invalid=copy.deepcopy(plan);invalid['tasks'][0]['depends_on']=[0];invalid['tasks'][0]['files']=['a.py','b.py','c.py','d.py']
result={'version':__version__,'scope':'synthetic provider replay, not live model evaluation'}
try:validate_structure(invalid);result['wide_cyclic_task']='accepted'
except ValueError:result['wide_cyclic_task']='rejected'
models=ScriptedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST,'outside.js':'const scopeLeak=1;'}},{'files':{'app.py':APP,'test_app.py':TEST}}])
with tempfile.TemporaryDirectory() as d:
 b=Workbench(Path(d)/'projects',models);config={'provider':'ollama','model':'fixture'}
 s=await_job(b,b.create('Build a task tracker',config,config)['id']);b.approve(s['id'],s['plan']);b.start(s['id'],'build',{'execute':False,'repairs':0});s=await_job(b,s['id'])
 result.update(status=s['status'],outside_file_written='outside.js' in b.files(s['id']),saved_tasks=s['next_task'],behavior_executed=bool(s.get('checks')))
print(json.dumps(result))
