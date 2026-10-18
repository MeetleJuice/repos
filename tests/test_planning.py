"""Contract review and bounded recovery, using actual failed user proposals."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error

from forge.contracts import review_plan, validate_structure, starter_contracts
from forge.core import Workbench
from forge.models import ModelClient, ModelError, request_json
from forge.prompts import PLAN as PLAN_PROMPT
from forge.routing import validate_config, validate_options
from forge.runner import verify
from forge.scaffolds import starter_files
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests/fixture_data'
CONFIG = {'provider': 'ollama', 'model': 'test'}


def good_notes():
    plan = json.loads((ROOT / 'examples/notes-proposal-v05.json').read_text())
    plan['api_contracts'] = starter_contracts('notes')
    plan['checks'][5]['name'] = 'Saved notes survive a server restart'
    plan['checks'][5]['restart_before'] = True
    return plan


class ContractTests(unittest.TestCase):
    def test_both_real_bad_proposals_passed_old_structure_but_fail_consistency(self):
        expected = [{('response_shape', '/checks/1/json_contains'), ('placeholder', '/checks/2/json_equals'), ('empty_response', '/checks/4'), ('false_restart', '/checks/5/name')},
                    {('response_shape', '/checks/1/json_equals'), ('false_restart', '/checks/8/name'), ('response_shape', '/checks/8/json_contains')}]
        for number in [1, 2]:
            plan = json.loads((DATA / f'notes-plan-{number}.json').read_text())
            validate_structure(plan)  # Before this upgrade, this was enough for approval.
            result = review_plan(plan, 'notes')
            self.assertFalse(result.passed)
            self.assertTrue(expected[number - 1].issubset({(f.code, f.path) for f in result.findings}))
            self.assertFalse(result.to_dict()['executed'])

    def test_valid_starter_proposal_with_real_restart_passes(self):
        result = review_plan(good_notes(), 'notes')
        self.assertTrue(result.passed, result.findings)

    def test_api_contract_deviation_is_reviewable_and_not_silently_normalized(self):
        plan = good_notes()
        index = next(i for i,c in enumerate(plan['api_contracts']) if c['method'] == 'POST')
        plan['api_contracts'][index]['response_kind'] = 'array'
        plan['checks'][1]['json_contains'] = [plan['checks'][1]['json_contains']]
        before = copy.deepcopy(plan)
        report = review_plan(plan, 'notes')
        self.assertTrue(report.passed, report.findings)
        self.assertIn('starter_contract_changed', [f.code for f in report.findings])
        self.assertEqual(plan, before)

    def test_empty_response_assertion_and_bad_body_combination(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'].append({'name': 'Delete without JSON', 'method': 'DELETE', 'path': '/api/tasks/1', 'status': 204, 'empty_body': True, 'feature_indexes': [0]})
        self.assertTrue(review_plan(plan).passed)
        plan['checks'][-1]['json_equals'] = []
        self.assertFalse(review_plan(plan).passed)

    def test_placeholder_literal_is_allowed_when_it_is_the_actual_requested_data(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'][0]['body']['title'] = '...'
        plan['checks'][0]['json_contains']['title'] = '...'
        self.assertTrue(review_plan(plan).passed)

    def test_restart_health_does_not_count_as_persistence(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'].append({'name': 'Restart proves persistence', 'method': 'GET', 'path': '/health', 'status': 200, 'json_contains': {'status': 'ok'}, 'restart_before': True, 'feature_indexes': [1]})
        self.assertIn('restart_evidence', [f.code for f in review_plan(plan).findings])

    def test_nonfinite_json_and_invalid_contracts_do_not_crash_review(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'][0]['body']['title'] = float('nan')
        self.assertFalse(review_plan(plan).passed)
        for contracts in [False, [{'method': 'GET', 'path': '//external', 'status': 200, 'response_kind': 'object'}], [{'method': 'GET', 'path': '/', 'status': True, 'response_kind': 'text'}]]:
            plan = dict(copy.deepcopy(PLAN), api_contracts=contracts)
            self.assertFalse(review_plan(plan).passed)

    def test_exact_object_must_include_declared_fields_and_lists_use_objects(self):
        plan = good_notes()
        plan['checks'][1].pop('json_contains')
        plan['checks'][1]['json_equals'] = {'id': 1}
        self.assertIn('exact_fields', [f.code for f in review_plan(plan, 'notes').findings])
        plan = good_notes()
        plan['checks'][2]['json_contains'] = [[1, 'Buy milk']]
        self.assertIn('item_shape', [f.code for f in review_plan(plan, 'notes').findings])


class PlannerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_actual_two_failures_are_corrected_before_approval_in_three_requests(self):
        replies = [json.loads((DATA / f'notes-plan-{i}.json').read_text()) for i in [1, 2]] + [good_notes()]
        app = starter_files('notes')['app.py']
        models = ScriptedModels(replies + [{'files': {'app.py': app}}, {'files': {'app.py': app}}])
        bench = Workbench(self.root, models)
        state = bench.create('Build a local notes app', CONFIG, CONFIG, 'notes')
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'proposed', state.get('error'))
        self.assertEqual(len(models.calls), 3)
        self.assertTrue(state['plan_review']['passed'])
        self.assertFalse(state['approved'])
        self.assertEqual(bench.context_files(state['id']), {})
        self.assertIn('response_shape', json.dumps(models.calls[1]['review_findings']))
        self.assertIn('starter_api_contracts', models.calls[0])
        bench.approve(state['id'], state['plan'])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 0})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'verified', state.get('error'))
        self.assertEqual(state['checks']['phases'][0]['server_restarts'], 1)
        self.assertEqual(state['checks']['phases'][1]['tests_run'], 13)
        self.assertEqual(json.loads(bench.files(state['id'])['CHECKS.json']), good_notes()['checks'])

    def test_identical_bad_output_stops_without_spending_all_requests(self):
        bad = json.loads((DATA / 'notes-plan-2.json').read_text())
        models = ScriptedModels([bad, bad])
        bench = Workbench(self.root, models)
        state = bench.create('Build a local notes app', CONFIG, CONFIG, 'notes')
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'error')
        self.assertEqual(len(models.calls), 2)
        self.assertFalse(state['approved'])
        self.assertIn('same invalid proposal', ' '.join(e['message'] for e in state['events']))
        with self.assertRaises(ValueError):
            bench.approve(state['id'], state['plan'])

    def test_configured_cloud_fallback_requires_consent_before_any_request(self):
        config = {**CONFIG, 'fallback': {'provider': 'groq', 'model': 'chosen-model'}}
        models = ScriptedModels([PLAN])
        bench = Workbench(self.root, models)
        with self.assertRaisesRegex(ValueError, 'cloud'):
            bench.create('Build a task tracker', config, CONFIG)
        self.assertFalse(models.calls)
        self.assertFalse(bench.list_projects())

    def test_planner_fallback_is_explicit_bounded_and_recorded(self):
        bad = json.loads((DATA / 'notes-plan-2.json').read_text())
        models = ScriptedModels([bad, bad, good_notes()])
        config = {**CONFIG, 'fallback': {'provider': 'groq', 'model': 'chosen-model'}}
        bench = Workbench(self.root, models)
        state = bench.create('Build a local notes app', config, CONFIG, 'notes', cloud_consent=True)
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'proposed', state.get('error'))
        self.assertEqual(len(models.calls), 3)
        self.assertTrue(state['planning_stats']['fallback_used'])
        self.assertEqual(state['model_calls'][-1]['provider'], 'groq')
        self.assertTrue(state['model_calls'][-1]['fallback'])
        with self.assertRaisesRegex(ValueError, 'cloud consent'):
            bench.start(state['id'], 'plan', {})

    def test_provider_error_routes_once_and_never_recursively(self):
        models = ScriptedModels([ModelError('Primary unavailable', 'transport'), PLAN])
        config = {**CONFIG, 'fallback': {'provider': 'ollama', 'model': 'other-local-model'}}
        bench = Workbench(self.root, models)
        state = bench.create('Build a task tracker', config, CONFIG)
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'proposed', state.get('error'))
        self.assertEqual(len(models.calls), 2)
        self.assertEqual(state['model_calls'][0]['error_category'], 'transport')
        self.assertEqual(state['model_calls'][1]['model'], 'other-local-model')

    def test_review_endpoint_logic_does_not_call_a_model_or_modify_source(self):
        models = ScriptedModels([PLAN])
        bench = Workbench(self.root, models)
        state = bench.create('Build a task tracker', CONFIG, CONFIG)
        state = await_job(bench, state['id'])
        before = (bench.directory(state['id']) / 'state.json').read_bytes()
        report = bench.review_proposal(state['id'], PLAN)
        self.assertTrue(report['passed'])
        self.assertEqual(len(models.calls), 1)
        self.assertEqual((bench.directory(state['id']) / 'state.json').read_bytes(), before)


class ModelSettingsTests(unittest.TestCase):
    def test_context_output_and_fallback_options_are_validated(self):
        self.assertEqual(validate_options({'num_ctx': 8192})['num_predict'], 4096)
        for options in [{'num_ctx': True}, {'num_ctx': 999999}, {'num_ctx': 4096, 'num_predict': 8192}, {'structured_outputs': 'true'}, {'arbitrary_setting': 1}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                validate_options(options)
        with self.assertRaises(ValueError):
            validate_config({**CONFIG, 'fallback': CONFIG})
        with self.assertRaises(ValueError):
            validate_config({**CONFIG, 'fallback': {'provider': 'groq', 'model': 'x', 'fallback': CONFIG}})

    def test_ollama_schemas_settings_and_actual_token_metadata(self):
        client = ModelClient('ollama', 'test', {'num_ctx': 8192, 'structured_outputs': True})
        response = {'message': {'content': json.dumps(PLAN)}, 'prompt_eval_count': 100, 'eval_count': 50}
        with patch('forge.models.request_json', return_value=response) as request:
            self.assertEqual(client.complete(PLAN_PROMPT, 'Idea'), PLAN)
            payload = request.call_args.args[1]
        self.assertEqual(payload['format']['type'], 'object')
        self.assertEqual(payload['options']['num_ctx'], 8192)
        self.assertEqual(payload['options']['num_predict'], 4096)
        self.assertEqual(payload['keep_alive'], '5m')
        self.assertEqual(client.last_usage, {'prompt_tokens': 100, 'completion_tokens': 50})
        client.options = validate_options({'structured_outputs': False})
        with patch('forge.models.request_json', return_value=response) as request:
            client.complete(PLAN_PROMPT, 'Idea')
            self.assertEqual(request.call_args.args[1]['format'], 'json')

    def test_truncation_and_malformed_responses_have_actionable_categories(self):
        for response, category in [({'done_reason': 'length'}, 'truncated'), ({'message': None}, 'format'), ({'message': {'content': None}}, 'format')]:
            with patch('forge.models.request_json', return_value=response), self.assertRaises(ModelError) as error:
                ModelClient('ollama', 'test').complete(PLAN_PROMPT, 'Idea')
            self.assertEqual(error.exception.category, category)

    def test_provider_http_errors_are_categorized_without_echoing_response(self):
        for status, category in [(429, 'rate_limit'), (401, 'auth'), (503, 'provider')]:
            exc = urllib.error.HTTPError('https://provider.invalid', status, 'failure', {}, None)
            with patch('forge.models.urllib.request.urlopen', side_effect=exc), self.assertRaises(ModelError) as error:
                request_json('https://provider.invalid')
            self.assertEqual(error.exception.category, category)


class RestartAcceptanceTests(unittest.TestCase):
    def test_actual_restart_retains_data_and_is_reported(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'][1].pop('contains')
        plan['checks'][1].update(name='Saved task survives restart', restart_before=True, json_contains=[{'title': 'Buy milk'}])
        self.assertTrue(review_plan(plan).passed)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / 'app.py').write_text(APP)
            (source / 'test_app.py').write_text(TEST)
            (source / 'CHECKS.json').write_text(json.dumps(plan['checks']))
            result = verify(source, 'local', threading.Event())
        self.assertTrue(result['passed'], result['log'])
        self.assertEqual(result['phases'][0]['server_restarts'], 1)

    def test_restart_detects_a_server_that_erases_existing_data(self):
        broken = APP.replace('def create_server(host, port):', 'def create_server(host, port):\n    from pathlib import Path\n    Path("tasks.db").unlink(missing_ok=True)')
        plan = copy.deepcopy(PLAN)
        plan['checks'][1].update(name='Saved task survives restart', restart_before=True)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / 'app.py').write_text(broken)
            (source / 'test_app.py').write_text(TEST)
            (source / 'CHECKS.json').write_text(json.dumps(plan['checks']))
            result = verify(source, 'local', threading.Event())
        self.assertFalse(result['passed'])
        self.assertEqual(result['phases'][0]['phase'], 'acceptance')
        self.assertIn('response missing', result['log'])


class RestartMemoryTests(unittest.TestCase):
    def test_independent_process_rejects_memory_only_data_that_survives_factory_restart(self):
        app = '''import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROWS=[]
def create_server(host, port):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args): pass
  def reply(self,value,html=False):
   data=value.encode() if html else json.dumps(value).encode()
   self.send_response(200);self.send_header('Content-Type','text/html' if html else 'application/json');self.end_headers();self.wfile.write(data)
  def do_GET(self):
   if self.path=='/health':self.reply({'status':'ok'})
   elif self.path=='/':self.reply('<html>Notes</html>',True)
   else:self.reply(ROWS)
  def do_POST(self):
   row=json.loads(self.rfile.read(int(self.headers['Content-Length'])));ROWS.append(row);self.reply(row)
 return ThreadingHTTPServer((host,port),Handler)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--host');p.add_argument('--port',type=int);a=p.parse_args();create_server(a.host,a.port).serve_forever()
'''
        checks = [{'name': 'Create note', 'method': 'POST', 'path': '/api/notes', 'body': {'title': 'Keep me'}, 'status': 200, 'json_contains': {'title': 'Keep me'}},
                  {'name': 'Survives real restart', 'method': 'GET', 'path': '/api/notes', 'restart_before': True, 'status': 200, 'json_contains': [{'title': 'Keep me'}]}]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / 'app.py').write_text(app)
            (source / 'test_app.py').write_text(TEST)
            (source / 'CHECKS.json').write_text(json.dumps(checks))
            result = verify(source, 'local', threading.Event())
        self.assertFalse(result['passed'])
        self.assertIn('unexpected JSON: []', result['log'])


class ReasoningParsingTests(unittest.TestCase):
    def test_only_leading_reasoning_is_stripped_not_tokens_inside_generated_source(self):
        from forge.models import extract_json
        value = {'files': {'app.py': 'print("</think>")'}}
        self.assertEqual(extract_json(json.dumps(value)), value)
        self.assertEqual(extract_json('<think>Plan carefully</think>\n' + json.dumps(value)), value)
        with self.assertRaises(ModelError):
            extract_json('<think>incomplete')
