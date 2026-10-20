"""Local-only setup never discovers cloud models or silently changes old profiles."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.cloud import CloudSetup
from forge.core import Workbench
from forge.models import ModelError
from forge.routing import uses_cloud, validate_config
from tests.fixtures import PLAN
from tests.test_workbench import ScriptedModels
from tests.test_cloud import state_for


class ModelStudioTests(unittest.TestCase):
    def test_local_only_is_bounded_unique_persisted_and_cloud_free(self):
        with tempfile.TemporaryDirectory() as temp, patch('forge.cloud.request_json') as cloud:
            setup=CloudSetup(temp)
            routes=setup.automatic(['qwen3.5:9b','qwen2.5-coder:7b','qwen3.5:9b','qwen3-embedding:0.6b','qwen2.5vl:3b','../bad model','granite4.2:8b'],mode='local_only')
            cloud.assert_not_called()
            for config in routes.values():
                validate_config(config);self.assertFalse(uses_cloud(config))
                entries=[config,*config.get('fallbacks',[])]
                self.assertEqual(len(entries),3)
                self.assertEqual(len({c['model'] for c in entries}),3)
                self.assertFalse(any('embed' in c['model'] or 'vl:' in c['model'] for c in entries))
            self.assertEqual(routes['coder']['model'],'qwen2.5-coder:7b')
            restored=CloudSetup(temp)
            self.assertEqual(restored.mode,'local_only')
            self.assertEqual(restored.automatic_routes,routes)

    def test_no_local_model_leaves_saved_cloud_routes_unchanged(self):
        with tempfile.TemporaryDirectory() as temp,patch('forge.cloud.request_json') as request:
            path=Path(temp)/'cloud-models.json'
            before=json.dumps({'mode':'cloud_first','automatic_routes':{role:{'provider':'gemini','model':'fixture'} for role in ('planner','coder')}})
            path.write_text(before)
            setup=CloudSetup(temp)
            with self.assertRaisesRegex(ValueError,'Cloud was not contacted'):
                setup.automatic(['qwen3-embedding:0.6b'],mode='local_only')
            request.assert_not_called()
            self.assertEqual(path.read_text(),before)
            self.assertEqual(setup.mode,'cloud_first')
            self.assertEqual(setup.automatic_routes['planner']['provider'],'gemini')

    def test_single_local_model_has_no_duplicate_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            route=CloudSetup(temp).automatic(['qwen2.5-coder:7b']*2,mode='local_only')
            for config in route.values():self.assertNotIn('fallbacks',config)

    def test_local_failure_advances_to_second_local_model_without_cloud(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);route=CloudSetup(root).automatic(['qwen3.5:9b','qwen2.5-coder:7b'],mode='local_only')
            models=ScriptedModels([ModelError('Local service failed','transport'),PLAN]);calls=[]
            def factory(provider,model):
                calls.append((provider,model));return models
            bench=Workbench(root/'projects',factory)
            # An explicit local route uses the existing bounded failure policy.
            state=state_for(bench);state['planner']=route['planner'];state['coder']=route['coder']
            result=bench.call_model(state,'coder','Return code','{}',threading.Event())
            self.assertEqual(result,PLAN)
            self.assertEqual(len(calls),2)
            self.assertTrue(all(p=='ollama' for p,_ in calls))
            self.assertNotEqual(calls[0],calls[1])
            self.assertEqual([r['success'] for r in state['model_calls']],[False,True])

    def test_manual_defaults_restore_after_local_only_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            setup=CloudSetup(temp)
            setup.automatic(['qwen2.5-coder:7b'],mode='local_only')
            setup.checked={'gemini':{'status':'catalogue_available','models':['fixture-text']}}
            selected=setup.select({'gemini':'fixture-text'},local_model='qwen2.5-coder:7b')
            self.assertEqual(setup.mode,'manual')
            restored=CloudSetup(temp)
            self.assertEqual(restored.mode,'manual')
            self.assertEqual(restored.saved_profiles(),selected)
            self.assertTrue(uses_cloud(restored.saved_profiles()['planner']))
            self.assertEqual(restored.saved_profiles()['coder']['fallbacks'][0]['provider'],'ollama')

    def test_invalid_legacy_manual_profile_cannot_break_connections(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'cloud-models.json').write_text(json.dumps({'models':{'gemini':'fixture'},'local_model':'   '}))
            self.assertEqual(CloudSetup(temp).saved_profiles(),{})
