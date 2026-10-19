"""Task decomposition invariants, execution scope, restart and legacy parity."""
import hashlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
from forge.contracts import validate_structure
from forge.tasks import task_packet, validate_task_response, task_document
from forge.core import Workbench
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job


def structured_plan():
    plan=copy.deepcopy(PLAN)
    plan['task_contract_version']=1
    plan['tasks']=[{'title':'Task tracker behavior','instructions':'Implement task CRUD and tests using the existing HTTP contract.',
        'outcome':'Create and list saved tasks through the browser and API.','files':['app.py','test_app.py'],
        'depends_on':[],'done_when':['A created task appears in the list; task behavior has unittest coverage.'],
        'feature_indexes':list(range(len(plan['features'])))}]
    return plan


class TaskContractTests(unittest.TestCase):
    def test_frozen_task_regressions(self):
        root=Path(__file__).parent/'fixture_data'
        for item in json.loads((root/'frozen-regressions-v11.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/item['file']).read_bytes()).hexdigest(),item['sha256'])
        self.assertEqual(json.loads((root/'task-decomposition-v1.json').read_text())['limits']['tasks'],16)

    def test_contract_fields_and_dependencies_validate(self):
        plan=structured_plan();validate_structure(plan)
        second=copy.deepcopy(plan['tasks'][0]);second['depends_on']=[0];plan['tasks'].append(second)
        validate_structure(plan)
        with self.assertRaisesRegex(ValueError,'dependencies'):task_packet(plan,1,0)
        self.assertEqual(task_packet(plan,1,1)['depends_on'],[0])
        self.assertEqual(plan['tasks'][1],second)
        self.assertIn('Dependencies: Task 1',task_document(plan))
        self.assertIn('Editable files: app.py, test_app.py',task_document(plan))

    def test_reject_wide_cyclic_protected_or_unbounded_tasks(self):
        for change in [{'files':['a.py','b.py','c.py','d.py']},{'depends_on':[0]},{'files':['README.md']},
                       {'files':['../x.py']},{'done_when':[]},{'instructions':'x'*1801},{'files':['APP.py','app.py']},{'files':['CON.py']},{'outcome':'Implement all remaining features'}]:
            with self.subTest(change=change):
                plan=structured_plan();plan['tasks'][0].update(change)
                with self.assertRaises(ValueError):validate_structure(plan)
        plan=structured_plan();del plan['tasks'][0]['outcome']
        with self.assertRaisesRegex(ValueError,'outcome'):validate_structure(plan)

    def test_structured_planner_reserves_for_task_metadata(self):
        from forge.capabilities import CapabilityRegistry
        from forge.routing import validate_options
        registry=CapabilityRegistry()
        options=validate_options({})
        legacy=registry.reserve('gemini','gemini-3.8-flash',options,'system','{}')
        structured=registry.reserve('gemini','gemini-3.8-flash',options,'system','{"task_contract_version":1}')
        self.assertGreater(structured.estimated_required_tokens,legacy.estimated_required_tokens)
        self.assertGreaterEqual(structured.text_output_tokens,legacy.text_output_tokens)

    def test_native_schema_requests_structured_contract(self):
        from forge.schemas import PLAN_SCHEMA
        self.assertIn('task_contract_version',PLAN_SCHEMA['required'])
        for field in ('files','depends_on','outcome','done_when'):
            self.assertIn(field,PLAN_SCHEMA['properties']['tasks']['items']['required'])

    def test_legacy_plan_and_task_values_preserved(self):
        before=copy.deepcopy(PLAN);validate_structure(PLAN)
        packet=task_packet(PLAN,0,0)
        self.assertFalse(packet['structured']);self.assertEqual(PLAN,before)
        validate_task_response({'files':{'outside.js':'x'}},{},packet)

    def test_scope_rejects_changed_file_but_not_unchanged_context_echo(self):
        packet=task_packet(structured_plan(),0,0)
        current={'extra.js':'original','app.py':'old'}
        validate_task_response({'files':{'extra.js':'original','app.py':'new'}},current,packet)
        with self.assertRaisesRegex(ValueError,'scope violation'):
            validate_task_response({'files':{'extra.js':'changed'}},current,packet)
        with self.assertRaisesRegex(ValueError,'no source changes'):
            validate_task_response({'files':{'app.py':'old'}},current,packet)
        with self.assertRaisesRegex(ValueError,'scope violation'):
            validate_task_response({'edits':[{'file':'extra.js','search':'original','replace':'changed'}]},current,packet)

    def test_sixteen_focused_tasks_supported_seventeen_rejected(self):
        plan=structured_plan();plan['tasks']=[copy.deepcopy(plan['tasks'][0]) for _ in range(16)]
        validate_structure(plan)
        plan['tasks'].append(copy.deepcopy(plan['tasks'][0]))
        with self.assertRaisesRegex(ValueError,'1–16'):validate_structure(plan)

    def test_scope_rejection_is_atomic_and_focused_correction_finishes(self):
        plan=structured_plan();models=ScriptedModels([plan,{'files':{'outside.js':'const forbidden=1;','app.py':APP}},
                                                   {'files':{'app.py':APP,'test_app.py':TEST}}])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models);config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a task tracker',config,config)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            bench.approve(state['id'],state['plan']);approved=copy.deepcopy(bench.load(state['id'])['plan'])
            bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertNotIn('outside.js',bench.files(state['id']))
            self.assertEqual(state['next_task'],1);self.assertEqual(state['plan'],approved)
            self.assertTrue(models.calls[-1]['task_packet']['structured'])
            self.assertFalse(state['task_receipts'][0]['behavior_verified'])
            self.assertEqual(state['task_receipts'][0]['task_packet']['files'],['app.py','test_app.py'])
            self.assertEqual(Workbench(Path(d)/'projects',models).load(state['id'])['next_task'],1)
