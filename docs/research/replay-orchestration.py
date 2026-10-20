"""Compare controlled orchestration/context behavior; no live inference or execution."""
from pathlib import Path
import copy
import json
import sys
import tempfile
from unittest.mock import patch

repository=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(repository))
from forge import __version__
from forge.cloud import CloudSetup
from forge.focus import dependencies
from forge.core import Workbench
from tests.fixtures import PLAN,APP,TEST
from tests.test_workbench import ScriptedModels,await_job

result={'version':__version__,'scope':'Deterministic controller replay. No provider, GPU, token-cost or generated-product-quality measurement.'}
with tempfile.TemporaryDirectory() as temp:
    setup=CloudSetup(temp)
    setup.checked={p:{'status':'catalogue_available','models':['fixture-'+p]} for p in ('gemini','groq')}
    with patch.object(setup,'check'):
        for mode in ('hybrid','orchestrated'):
            try:
                profile=setup.automatic(['qwen3.5:9b','qwen2.5-coder:7b'],mode=mode)
                result[mode]={role:[r['provider']+'/'+r['model'] for r in [config,*config.get('fallbacks',[])]] for role,config in profile.items()}
            except ValueError as error:result[mode]={'error':str(error)}
result['python_relative_dependencies']=sorted(dependencies('pkg/routes.py','from .storage import store\n',{'pkg/routes.py':'','pkg/storage.py':'store={}\n'}))
result['js_relative_dependencies']=sorted(dependencies('ui/pages/main.js',"import {store} from '../storage.js';",{'ui/pages/main.js':'','ui/storage.js':'export const store={}'}))
with tempfile.TemporaryDirectory() as temp:
    models=ScriptedModels([copy.deepcopy(PLAN),{'files':{'app.py':APP,'test_app.py':TEST}}])
    bench=Workbench(Path(temp)/'projects',models)
    state=await_job(bench,bench.create('Build a small task tracker',{'provider':'gemini','model':'fixture-cloud'},{'provider':'ollama','model':'fixture-local'},cloud_consent=True)['id'])
    bench.approve(state['id'],state['plan'])
    try:
        bench.start(state['id'],'build',{'execute':False,'repairs':0,'cloud_consent':False});state=await_job(bench,state['id'])
        result['local_build_without_unused_cloud_consent']={'status':state['status'],'providers':[r['provider'] for r in state['model_calls']],'app_executed':False}
    except ValueError as error:result['local_build_without_unused_cloud_consent']={'error':str(error),'app_executed':False}
print(json.dumps(result,indent=2))
