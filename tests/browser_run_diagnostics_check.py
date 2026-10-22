"""A real fixture repair -> quick Test -> source-bound Diag download in Chromium."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import zipfile
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.server import make_server
from forge.core import Workbench
from tests.fixtures import PLAN, APP, BROKEN, TEST
from tests.test_workbench import ScriptedModels, await_job


def main():
    models = ScriptedModels([PLAN, {'files': {'app.py': BROKEN, 'test_app.py': TEST}}, {'files': {'app.py': APP}}])
    with tempfile.TemporaryDirectory() as folder:
        bench = Workbench(Path(folder)/'projects', models)
        config = {'provider': 'ollama', 'model': 'fixture-local'}
        state = await_job(bench, bench.create('PRIVATE PROMPT NOT FOR EXPORT', config, config)['id'])
        bench.approve(state['id'], state['plan'])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 1})
        state = await_job(bench, state['id'])
        assert state['status'] == 'verified', state.get('error')
        before = (bench.directory(state['id'])/'state.json').read_bytes()
        with patch('forge.server.connection_info', return_value={'ollama': {'connected': True, 'models': ['fixture-local']}}), \
             patch('forge.cloud.CloudSetup.check', return_value={}), \
             patch('forge.diagnostic_report._ollama_probe', return_value={'status': 'unavailable'}):
            server = make_server(0, bench)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=shutil.which('chromium'))
                    page = browser.new_page(viewport={'width': 1440, 'height': 1100}); errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto('http://127.0.0.1:'+str(server.server_port))
                    page.locator('#projects .project-link').first.click()
                    page.locator('#system-test-button').click(); page.locator('#system-test-start').click()
                    expect(page.locator('#system-test-status')).to_contain_text('Run finished', timeout=15000)
                    expect(page.locator('#system-test-results')).to_contain_text('Repair evidence safeguards')
                    expect(page.locator('#system-test-results')).to_contain_text('Recorded build: verified')
                    page.locator('#system-test-close').click(); page.locator('#diag-button').click()
                    expect(page.locator('#diag-summary')).to_contain_text('Latest selected build: verified', timeout=15000)
                    expect(page.locator('#diag-summary')).to_contain_text('behavioral_pass')
                    with page.expect_download() as pending: page.locator('#diag-export').click()
                    path = Path(folder)/'evidence.zip'; pending.value.save_as(path)
                    with zipfile.ZipFile(path) as archive:
                        manifest = json.loads(archive.read('manifest.json'))
                        summary = json.loads(archive.read('summary.json'))
                        run = summary['selected_execution']
                        repair = run['repairs'][0]
                        assert repair['validation'] == 'behavioral_pass'
                        assert repair['source_changed'] and run['attempts'] == 2
                        assert run['coverage']['attempt_details_complete'] is True
                        projects = json.loads(archive.read('evidence/projects.json'))
                        project = next(row for row in projects if row['project_id'] == state['id'])
                        records = {r['id']: r for r in project['history']['records']}
                        checked = records[repair['validation_event_id']]['data']
                        assert checked['passed'] and checked['source_sha256'] == repair['after_source_sha256']
                        tests = json.loads(archive.read('evidence/system_tests.json'))
                        assert next(r for r in tests['rows'] if r['code']=='loop_guards')['case_count'] == 6
                        assert all(b'PRIVATE PROMPT NOT FOR EXPORT' not in archive.read(name) for name in archive.namelist())
                        assert all(APP.encode() not in archive.read(name) for name in archive.namelist())
                        for entry in manifest['files']:
                            content = archive.read(entry['path'])
                            assert len(content) == entry['bytes'] and hashlib.sha256(content).hexdigest() == entry['sha256']
                    assert len(models.calls) == 3
                    assert (bench.directory(state['id'])/'state.json').read_bytes() == before
                    page.set_viewport_size({'width': 390, 'height': 844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    assert not errors, errors
                    browser.close()
            finally:
                server.shutdown(); server.server_close()
    print('PASS: real fixture application failure -> repair -> matching-source behavioral pass -> quick Test/Diag UI -> correlated ZIP evidence and manifest; no extra inference, project mutation, private prompt/source export or browser errors. No live model claim.')


if __name__ == '__main__': main()
