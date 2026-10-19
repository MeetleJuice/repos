"""Controlled replay; optional argument: extracted baseline release root."""
import copy,json,tempfile
from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).resolve().parents[2]))
from forge import __version__
from forge.core import Workbench
from forge.capabilities import CapabilityRegistry
from tests.fixtures import PLAN,APP,TEST
from tests.test_workbench import ScriptedModels,await_job
plan=copy.deepcopy(PLAN);plan['task_contract_version']=1
plan['tasks']=[{'title':'Task increment','instructions':'Implement task behavior and tests.','feature_indexes':list(range(len(plan['features']))),'files':['app.py','test_app.py'],'outcome':'Create and list tasks.','depends_on':[],'done_when':['A saved task is listed.']}]
models=ScriptedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST}}]);result={'version':__version__,'scope':'controlled adapter replay; no live models or generated-app execution'}
with tempfile.TemporaryDirectory() as d:
 b=Workbench(Path(d)/'projects',models);config={'provider':'ollama','model':'fixture'}
 s=await_job(b,b.create('Build a task tracker',config,config)['id']);b.approve(s['id'],s['plan']);original=b.apply
 def stop_after_commit(state,response,repair=False):
  original(state,response,repair=repair);b.jobs[state['id']][1].set()
 b.apply=stop_after_commit;b.start(s['id'],'build',{'execute':False,'repairs':0});s=await_job(b,s['id'])
 result['before_resume']={'status':s['status'],'cursor':s['next_task'],'adapter_calls':len(models.calls)}
 s['status']='building';b.save(s)
 resumed=Workbench(Path(d)/'projects',models);resumed.start(s['id'],'build',{'execute':False,'repairs':0});s=await_job(resumed,s['id'])
 result['after_resume']={'status':s['status'],'cursor':s['next_task'],'adapter_calls':len(models.calls),'source_preserved':resumed.files(s['id'])['app.py']==APP,'behavior_executed':bool(s.get('checks'))}
files={'app.py':'value = 1\n','unused.js':'x'*30000}
payload={'proposal':{'context_policy':'focused_v1'},'task_packet':{'structured':True,'files':['app.py']},'files':files}
try:
 from forge.focus import prepare_context
 request=prepare_context(payload,files)
except ImportError:request=payload
encoded=json.dumps(request);eligible=True
try:CapabilityRegistry().reserve_builder('ollama','fixture',{'num_ctx':16384,'num_predict':8192},'fixture',encoded)
except ValueError:eligible=False
result['isolated_budget_probe']={'payload_utf8_bytes':len(encoded.encode()),'reservation_eligible':eligible,'context_tokens':16384,'output_cap':8192,'excluded':'Production CODE/system prompt, framing, live model and GPU execution; not billed tokens.'}
print(json.dumps(result))
