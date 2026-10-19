"""Five-category workflow facts, receipt accuracy, and export evidence regression."""
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from forge.core import Workbench
from forge.workflow import workflow_snapshot, ownership_warnings
from forge.contracts import review_plan
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job
from forge.server import make_server

CONFIG={'provider':'ollama','model':'fixture'}


class WorkflowTests(unittest.TestCase):
    def make_project(self, directory, responses=None):
        models=ScriptedModels(responses or [PLAN]);bench=Workbench(Path(directory)/'projects',models)
        state=await_job(bench,bench.create('Build task tracker',CONFIG,CONFIG)['id'])
        return bench,state,models

    def test_five_categories_are_facts_and_do_not_start_models(self):
        with tempfile.TemporaryDirectory() as d:
            bench,state,models=self.make_project(d);before=len(models.calls)
            snapshot=bench.workflow(state['id'])
            self.assertEqual([c['id'] for c in snapshot['categories']],['models','planning','generation','verification','delivery'])
            self.assertEqual(len(models.calls),before)
            self.assertFalse(snapshot['evidence']['accepted_current'])
            self.assertEqual(snapshot['receipt_coverage']['available'],0)
            self.assertTrue(all(row['tasks'] for row in snapshot['coverage']))
            self.assertFalse(bench.load(state['id'])['approved'])

    def test_owned_references_are_advisory_and_plan_unchanged(self):
        plan=copy.deepcopy(PLAN);plan['tasks'][0]['instructions']+=' Create README.md and MANUAL-CHECKS.md.'
        before=copy.deepcopy(plan);result=review_plan(plan)
        self.assertTrue(result.passed,result.findings)
        warning=next(f for f in result.findings if f.code=='controller_owned_reference')
        self.assertEqual(warning.severity,'warning');self.assertEqual(plan,before)
        self.assertEqual(ownership_warnings(plan)[0]['files'],['manual-checks.md','readme.md'])

    def test_task_receipts_capture_before_after_and_actual_changed_files(self):
        plan=copy.deepcopy(PLAN);plan['tasks']=[{'title':'Build all','instructions':'Implement all approved features','feature_indexes':list(range(len(plan['features'])))}]
        with tempfile.TemporaryDirectory() as d:
            bench,state,_=self.make_project(d,[plan,{'files':{'app.py':APP,'test_app.py':TEST}}])
            bench.approve(state['id'],state['plan']);bench.start(state['id'],'build',{'execute':False,'repairs':0})
            state=await_job(bench,state['id']);self.assertEqual(state['status'],'generated',state.get('error'))
            receipt=state['task_receipts'][0]
            self.assertTrue(receipt['source_changed']);self.assertNotEqual(receipt['before_sha256'],receipt['after_sha256'])
            self.assertIn('test_app.py',receipt['changed_files']);self.assertFalse(receipt['behavior_verified'])
            self.assertEqual(bench.workflow(state['id'])['receipt_coverage']['available'],1)

    def test_stale_manual_observations_become_pending(self):
        with tempfile.TemporaryDirectory() as d:
            bench,state,_=self.make_project(d)
            state['plan']['manual_checks']=[{'name':'Try','steps':['Try app'],'expected':'Works','feature_indexes':[0]}]
            state['manual_results']={'results':[True],'source_sha256':'old'}
            snapshot=workflow_snapshot(state,bench.files(state['id']))
            self.assertEqual(snapshot['manual']['passed'],0);self.assertEqual(snapshot['manual']['pending'],1)
            self.assertFalse(snapshot['manual']['observations_current'])

    def test_restored_task_counter_does_not_show_future_receipts_as_current(self):
        with tempfile.TemporaryDirectory() as d:
            bench,state,_=self.make_project(d);state['next_task']=0;state['task_receipts']=[{'task':1,'changed_files':['app.py']}]
            self.assertEqual(workflow_snapshot(state,bench.files(state['id']))['receipt_coverage']['available'],0)
            bench.save(state)
            _,report,_=bench.export_snapshot(state['id'])
            self.assertEqual(report['task_receipts'],[])

    def test_export_guide_is_honest_and_does_not_change_source(self):
        with tempfile.TemporaryDirectory() as d:
            bench,state,_=self.make_project(d);before=bench.files(state['id'])
            files,report,_=bench.export_snapshot(state['id'])
            self.assertIn('Current automated verification: NO',report['delivery_guide'])
            self.assertIn('Current overall acceptance: NO',report['delivery_guide'])
            self.assertEqual(files,before);self.assertEqual(bench.files(state['id']),before)
            self.assertIn('.foundry/DELIVERY.md',report['export_metadata_files'])
            self.assertNotIn('.foundry/DELIVERY.md',[r['file'] for r in report['file_manifest']])

    def test_workflow_endpoint_is_read_only_and_download_contains_guide(self):
        with tempfile.TemporaryDirectory() as d:
            bench,state,models=self.make_project(d);server=make_server(0,bench)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                root='http://127.0.0.1:'+str(server.server_port)
                with urllib.request.urlopen(root) as r:html=r.read().decode()
                import re
                token=re.search('name="foundry-token" content="([^"]+)',html).group(1)
                def get(path):
                    with urllib.request.urlopen(urllib.request.Request(root+path,headers={'X-Foundry-Token':token})) as r:return r.read()
                snap=json.loads(get('/api/projects/'+state['id']+'/workflow'));self.assertEqual(len(snap['categories']),5)
                with zipfile.ZipFile(io.BytesIO(get('/api/projects/'+state['id']+'/download'))) as z:
                    guide=z.read('generated-app/.foundry/DELIVERY.md').decode()
                    self.assertIn('Current automated verification: NO',guide)
                    report=json.loads(z.read('generated-app/BUILD-REPORT.json'))
                    self.assertEqual(guide,report['delivery_guide'])
                self.assertEqual(len(models.calls),1)
            finally:server.shutdown();server.server_close()

    def test_current_failed_manual_checks_point_to_repair(self):
        from forge.context import fingerprint
        with tempfile.TemporaryDirectory() as d:
            bench,state,_=self.make_project(d)
            state['plan']['manual_checks']=[{'name':'Try app','steps':['Try app'],'expected':'Works','feature_indexes':[0]}]
            bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
            state.update(next_task=len(state['plan']['tasks']),checks={'passed':True},verification_fingerprint=fingerprint(bench.context_files(state['id'])),status='needs_attention')
            state['manual_results']={'results':[False],'source_sha256':state['verification_fingerprint']}
            snapshot=workflow_snapshot(state,bench.files(state['id']))
            self.assertEqual(snapshot['manual']['failed'],1)
            self.assertIn('Repair',snapshot['next_step'])
            self.assertFalse(snapshot['evidence']['accepted_current'])
