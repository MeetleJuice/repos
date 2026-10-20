"""Frozen orchestration route, local context and delivery-budget regressions."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.cloud import CloudSetup
from forge.core import Workbench
from forge.focus import dependencies,prepare_context
from forge.models import ModelError
from forge.routing import uses_cloud
from tests.fixtures import PLAN,APP,TEST
from tests.test_cloud import state_for
from tests.test_hybrid_execution import supported
from tests.test_task_contracts import structured_plan
from tests.test_workbench import ScriptedModels,await_job

LOCAL=['qwen3.5:9b','qwen2.5-coder:7b','qwen3-embedding:0.6b']
CATALOGUE={p:{'status':'catalogue_available','models':['fixture-'+p]} for p in ('gemini','groq')}


def profile(home):
    setup=CloudSetup(home);setup.checked=copy.deepcopy(CATALOGUE)
    with patch.object(setup,'check'):routes=setup.automatic(LOCAL,mode='orchestrated')
    return setup,routes


class OrchestrationTests(unittest.TestCase):
    def test_frozen_scenarios(self):
        root=Path(__file__).parent/'fixture_data'
        for entry in json.loads((root/'frozen-regressions-v14.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/entry['file']).read_bytes()).hexdigest(),entry['sha256'])

    def test_cloud_plan_local_build_order_and_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            setup,routes=profile(temp)
            self.assertEqual([c['provider'] for c in [routes['planner'],*routes['planner']['fallbacks']]],['gemini','groq','ollama','ollama'])
            self.assertEqual(routes['planner']['options']['timeout_seconds'],30)
            self.assertFalse(uses_cloud(routes['coder']))
            self.assertEqual(routes['coder']['model'],'qwen2.5-coder:7b')
            self.assertEqual(len(routes['coder']['fallbacks']),1)
            self.assertEqual(CloudSetup(temp).saved_profiles(),routes)
            self.assertEqual(CloudSetup(temp).mode,'orchestrated')
            setup.order=['groq',*[p for p in setup.order if p!='groq']]
            with patch.object(setup,'check'):custom=setup.automatic(LOCAL,mode='orchestrated')
            self.assertEqual(custom['planner']['provider'],'groq')

    def test_missing_local_coder_preserves_setup_without_cloud_discovery(self):
        with tempfile.TemporaryDirectory() as temp:
            setup,routes=profile(temp);before=setup.path.read_bytes()
            with patch.object(setup,'check') as check:
                with self.assertRaisesRegex(ValueError,'No cloud discovery'):setup.automatic(['embed:latest'],mode='orchestrated')
                check.assert_not_called()
            self.assertEqual(setup.path.read_bytes(),before);self.assertEqual(setup.saved_profiles(),routes)

    def test_primary_failure_calls_secondary_without_sleep_then_all_clouds_fall_back_local(self):
        for replies,providers in [([ModelError('Unavailable','transport'),PLAN],['gemini','groq']),
                                 ([ModelError('Unavailable','transport'),ModelError('Unavailable','transport'),PLAN],['gemini','groq','ollama'])]:
            with self.subTest(providers=providers),tempfile.TemporaryDirectory() as temp:
                _,routes=profile(temp);models=ScriptedModels(replies);bench=Workbench(Path(temp)/'projects',models)
                state=state_for(bench);state['planner']=routes['planner']
                with patch('forge.core.time.sleep',side_effect=AssertionError('Fallback must not sleep')):
                    result=bench.call_model(state,'planner','Return JSON','{}',threading.Event())
                self.assertEqual(result,PLAN)
                self.assertEqual([r['provider'] for r in state['model_calls']],providers)

    def test_local_coder_failover_never_calls_cloud(self):
        with tempfile.TemporaryDirectory() as temp:
            _,routes=profile(temp);models=ScriptedModels([ModelError('Local error','transport'),{'files':{'app.py':APP}}])
            bench=Workbench(Path(temp)/'projects',models);state=state_for(bench);state['coder']=routes['coder']
            result=bench.call_model(state,'coder','Return source','{}',threading.Event())
            self.assertIn('app.py',result['files'])
            self.assertEqual([r['provider'] for r in state['model_calls']],['ollama','ollama'])

    def test_invocation_budget_covers_all_roles_before_another_call(self):
        for role in ('planner','coder'):
            with self.subTest(role=role),tempfile.TemporaryDirectory() as temp:
                models=ScriptedModels([PLAN]);bench=Workbench(Path(temp)/'projects',models);state=state_for(bench)
                state.update(job_inference_attempts=3,job_max_model_calls=3)
                with self.assertRaisesRegex(ModelError,'invocation allowance'):bench.call_model(state,role,'Return JSON','{}',threading.Event())
                self.assertEqual(models.calls,[])

    def test_budget_stop_preserves_saved_cursor_and_resumes_remaining_task(self):
        plan=structured_plan();task=copy.deepcopy(plan['tasks'][0]);task['title']='Inspect existing implementation';task['depends_on']=[0];plan['tasks'].append(task)
        models=ScriptedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST}},supported()])
        config={'provider':'ollama','model':'fixture'}
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',models);state=await_job(bench,bench.create('Build a task tracker',config,config)['id']);bench.approve(state['id'],state['plan'])
            for invalid in (None,True,0,129,'64'):
                with self.assertRaisesRegex(ValueError,'invocation allowance'):bench.start(state['id'],'build',{'execute':False,'max_model_calls':invalid})
            bench.start(state['id'],'build',{'execute':False,'repairs':0,'max_model_calls':1});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'error');self.assertEqual(state['next_task'],1)
            self.assertEqual(bench.files(state['id'])['app.py'],APP);self.assertEqual(len(models.calls),2)
            bench.start(state['id'],'build',{'execute':False,'repairs':0,'max_model_calls':2});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'));self.assertEqual(state['next_task'],2)
            self.assertEqual(len(models.calls),3);self.assertEqual(state['plan'],plan)
            files,report,_=bench.export_snapshot(state['id']);text=report['work_checklist']
            self.assertIn('- [ ] Current automated checks passed',text)
            self.assertIn('- [x] All task source saved',text)
            self.assertIn('Declared criteria (not individually verified)',text)
            self.assertIn('.foundry/WORK-CHECKLIST.md',report['export_metadata_files'])
            self.assertNotIn('.foundry/WORK-CHECKLIST.md',files)
            self.assertFalse(report['workflow']['evidence']['accepted_current'])

    def test_relative_python_modules_and_package_initializers_resolve(self):
        files={'pkg/__init__.py':'','pkg/sub/__init__.py':'','pkg/sub/routes.py':'from ..storage import store\nfrom . import util\n',
               'pkg/storage.py':'store={}\n','pkg/sub/util.py':'value=1\n','pkg/extra.py':'','root.py':'from pkg import extra\n'}
        self.assertEqual(dependencies('pkg/sub/routes.py',files['pkg/sub/routes.py'],files),{'pkg/storage.py','pkg/__init__.py','pkg/sub/__init__.py','pkg/sub/util.py'})
        self.assertEqual(dependencies('root.py',files['root.py'],files),{'pkg/__init__.py','pkg/extra.py'})
        self.assertEqual(dependencies('root.py','from ..pkg import extra\n',files),set())
        files['pkg/sub/util.py']='from ..storage import store\n'
        focused=prepare_context({'proposal':{'context_policy':'focused_v1'},'task_packet':{'structured':True,'files':['pkg/sub/routes.py']},'files':files},files)
        self.assertIn('pkg/storage.py',focused['files']);self.assertEqual(focused['files']['pkg/storage.py'],'store={}\n')

    def test_relative_web_references_normalize_and_cannot_escape(self):
        files={'ui/storage.js':'','ui/assets/theme.css':'','outside.js':'','ui/pages/main.js':''}
        text="import {store} from '../storage.js'; require('../storage'); const lazy=import('../storage.js');"
        self.assertEqual(dependencies('ui/pages/main.js',text,files),{'ui/storage.js'})
        self.assertEqual(dependencies('ui/pages/main.js',"<link href='../assets/theme.css?v=1#top'>",files),{'ui/assets/theme.css'})
        self.assertEqual(dependencies('ui/pages/main.js',"url('../assets/theme.css')",files),{'ui/assets/theme.css'})
        for ref in ['../../../outside.js','https://example.com/outside.js','//example.com/outside.js','%2e%2e/%2e%2e/%2e%2e/outside.js','..\\outside.js']:
            self.assertEqual(dependencies('ui/pages/main.js',"import '"+ref+"'",files),set(),ref)

    def test_source_cap_explains_merged_size_and_keeps_files(self):
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects');state=state_for(bench)
            with self.assertRaisesRegex(ValueError,'Smaller patches do not reduce stored project size'):
                bench.apply(state,{'files':{'game.js':'//'+'x'*35999}})
            self.assertEqual(bench.files(state['id']),{})

    def test_cloud_consent_tracks_used_stage_and_never_leaks_into_local_build(self):
        config={'provider':'gemini','model':'fixture-cloud'};local={'provider':'ollama','model':'fixture-local'}
        models=ScriptedModels([structured_plan(),{'files':{'app.py':APP,'test_app.py':TEST}}])
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',models)
            state=await_job(bench,bench.create('Build a task tracker',config,local,cloud_consent=True)['id'])
            with self.assertRaisesRegex(ValueError,'cloud consent'):bench.start(state['id'],'plan',{'cloud_consent':False})
            self.assertEqual(len(models.calls),1)
            bench.approve(state['id'],state['plan'])
            bench.start(state['id'],'build',{'execute':False,'repairs':0,'cloud_consent':False});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertFalse(state['job_cloud_consent'])
            self.assertEqual([r['provider'] for r in state['model_calls']],['gemini','ollama'])
            bench.configure_models(state['id'],config,config)
            with self.assertRaisesRegex(ValueError,'cloud consent'):bench.start(state['id'],'build',{'execute':False,'cloud_consent':False})
            self.assertEqual(len(models.calls),2)

    def test_legacy_history_does_not_invent_a_job_allowance(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([PLAN]);bench=Workbench(Path(temp)/'projects',models);state=state_for(bench)
            state['job_inference_attempts']=105  # Legacy/direct instrumentation has no configured run allowance.
            bench.call_model(state,'coder','Return JSON','{}',threading.Event())
            self.assertEqual(len(models.calls),1)
            snapshot=bench.workflow(state['id'])
            self.assertEqual(snapshot['model_budget']['used'],106)
            self.assertIsNone(snapshot['model_budget']['limit'])

    def test_no_cloud_catalogue_models_yields_explicit_all_local_routes(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(CloudSetup,'check',return_value={}):
            setup=CloudSetup(temp);routes=setup.automatic(LOCAL,mode='orchestrated')
            self.assertTrue(all(not uses_cloud(config) for config in routes.values()))
            self.assertEqual(routes['coder']['model'],'qwen2.5-coder:7b')
            self.assertEqual(CloudSetup(temp).mode,'orchestrated')
