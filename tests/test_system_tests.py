"""Real private storage/HTTP-independent checks; inference replies are fixtures."""
import json
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.core import Workbench
from forge.models import ModelError
from forge.system_tests import SystemTests,read_tests,probe_targets
from tests.test_workbench import ScriptedModels


class SystemTestTests(unittest.TestCase):
    def test_truncated_probe_distinguishes_received_reply_from_accepted_json(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,factory,runner=self.make(folder,[ModelError('cut off','truncated_output')])
            factory.last_metadata={'finish_reason':'length','observed_output_tokens':1024,'http_status':200}
            runner.start([{'provider':'ollama','model':'fixture'}],True)
            row=next(row for row in self.finish(runner)['rows'] if row['code']=='fixed_json_probe')
            self.assertTrue(row['response_received'])
            self.assertFalse(row['response_accepted'])
            self.assertTrue(row['http_response_received'])
            self.assertEqual(row['failure_class'],'truncated_output')

    def test_no_saved_route_never_claims_inference_was_tested(self):
        with tempfile.TemporaryDirectory() as folder:
            _,factory,runner=self.make(folder)
            runner.start([],True);report=self.finish(runner)
            self.assertEqual(factory.calls,[]);self.assertEqual(report['completed_probes'],0)
            self.assertTrue(any(row.get('failure_class')=='no_saved_models' for row in report['rows']))

    def test_local_runtime_metadata_omits_bodies_and_never_generates(self):
        from forge.diagnostic_report import _ollama_probe
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        data={'models':[{'name':'fixture-local','size':7,'size_vram':5,'context_length':4096,'source':'PRIVATE SOURCE'}]}
        with patch.dict(os.environ,{'OLLAMA_URL':'http://127.0.0.1:11434'}),patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=Response(json.dumps(data).encode())
            report=_ollama_probe('/api/ps')
            self.assertEqual(report['models'][0]['context_length'],4096)
            self.assertNotIn('PRIVATE SOURCE',json.dumps(report))
            self.assertEqual(opener.return_value.open.call_args.args[0].full_url,'http://127.0.0.1:11434/api/ps')
        with patch.dict(os.environ,{'OLLAMA_URL':'https://external.invalid'}),patch('urllib.request.build_opener') as opener:
            self.assertEqual(_ollama_probe('/api/ps')['status'],'configuration_error');opener.assert_not_called()

    def test_runtime_sampler_records_model_metadata_without_loading_models(self):
        from forge.diagnostics import ResourceSampler
        with tempfile.TemporaryDirectory() as folder:
            bench,_,_=self.make(folder)
            sampler=ResourceSampler(bench.diagnostics,Path(folder))
            def observation():
                sampler._stop.set();return {'status':'available','models':[{'model':'fixture','context_length':4096,'size_vram':123}]}
            sampler.local_probe=observation
            with patch('forge.diagnostics.resource_snapshot',return_value={}):sampler._run()
            rows=bench.diagnostics.snapshot()['records']
            event=next(row for row in rows if row['kind']=='local_runtime_sample')
            self.assertEqual(event['data']['models'][0]['context_length'],4096)

    def make(self, folder, replies=()):
        factory=ScriptedModels(list(replies));bench=Workbench(Path(folder)/'projects',factory)
        runner=SystemTests(bench,lambda:{'groq':{'status':'catalogue_available','models':['fixture']}},lambda:{'connected':True})
        return bench,factory,runner

    def finish(self, runner):
        runner.worker.join(5);self.assertFalse(runner.worker.is_alive());return runner.status()

    def test_quick_checks_never_infer_and_persist_into_diag(self):
        from forge.diagnostic_report import collect_report
        with tempfile.TemporaryDirectory() as folder:
            bench,factory,runner=self.make(folder)
            runner.start([]);report=self.finish(runner)
            self.assertTrue(report['passed'],report)
            self.assertEqual(len(factory.calls),0)
            self.assertFalse(bench.test_busy)
            self.assertEqual(read_tests(runner.path)['id'],report['id'])
            exported=collect_report(bench,Path(__file__).resolve().parents[1])
            self.assertEqual(exported['evidence']['system_tests']['id'],report['id'])
            self.assertFalse(report['generated_code_executed'])

    def test_cloud_probe_requires_consent_before_worker_or_network(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,factory,runner=self.make(folder,[{'answer':7}])
            with self.assertRaisesRegex(ValueError,'explicitly'):
                runner.start([{'provider':'groq','model':'fixture'}],True,False)
            self.assertEqual(factory.calls,[])
            self.assertFalse(getattr(bench,'test_busy',False))

    def test_probe_failure_is_recorded_without_mutating_routes_or_cooldowns(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,factory,runner=self.make(folder,[ModelError('PRIVATE PROVIDER ERROR','quota',http_status=402)])
            runner.start([{'provider':'groq','model':'fixture'}],True,True)
            report=self.finish(runner)
            row=next(row for row in report['rows'] if row['code']=='fixed_json_probe')
            self.assertEqual(row['http_status'],402);self.assertFalse(report['passed'])
            self.assertFalse(bench.model_status.avoid('groq','fixture'))
            self.assertNotIn('PRIVATE PROVIDER ERROR',runner.path.read_text())
            self.assertTrue(bench.inference_lock.acquire(False));bench.inference_lock.release()

    def test_fixed_local_probe_has_no_project_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,factory,runner=self.make(folder,[{'answer':7}])
            runner.start([{'provider':'ollama','model':'fixture'}],True)
            self.assertTrue(self.finish(runner)['passed'])
            self.assertEqual(factory.calls,[{'numbers':[2,5],'operation':'add'}])

    def test_active_job_blocks_tests_and_test_stop_releases_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,_,runner=self.make(folder)
            bench.test_busy=True
            with self.assertRaises(ValueError):runner.start([])
            bench.test_busy=False
            entered=threading.Event();resume=threading.Event()
            runner.local=lambda:(entered.set(),resume.wait(3),{'connected':True})[-1]
            runner.start([]);self.assertTrue(entered.wait(2));runner.stop();resume.set()
            self.assertEqual(self.finish(runner)['status'],'stopped')
            self.assertFalse(bench.test_busy)

    def test_target_selection_is_bounded_and_preserves_local_primaries(self):
        a={'provider':'ollama','model':'coder','fallbacks':[{'provider':'ollama','model':'backup'}]}
        b={'provider':'ollama','model':'planner','fallbacks':[{'provider':'groq','model':'first'},{'provider':'groq','model':'second'}]}
        rows=probe_targets([a,b])
        self.assertEqual([(r['provider'],r['model']) for r in rows],[('groq','first'),('ollama','coder'),('ollama','planner')])

    def test_restarted_running_test_is_interpreted_as_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,_,runner=self.make(folder)
            runner.path.parent.mkdir(exist_ok=True)
            runner.path.write_text(json.dumps({'schema':1,'status':'running'}))
            self.assertEqual(SystemTests(bench,lambda:{},lambda:{}).status()['status'],'interrupted')
