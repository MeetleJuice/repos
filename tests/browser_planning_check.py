"""Real browser: bounded proposal recovery, explicit routing and edited-plan approval gate."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from tests.test_workbench import ScriptedModels
from tests.test_planning import good_notes, DATA
from tests.test_compatibility import legacy_state


def main():
    root = Path(__file__).resolve().parents[1]
    (root / 'artifacts').mkdir(exist_ok=True)
    responses = [json.loads((DATA / f'notes-plan-{n}.json').read_text()) for n in [1, 2]] + [good_notes()]
    with tempfile.TemporaryDirectory() as temporary:
        models = ScriptedModels(responses)
        bench = Workbench(Path(temporary) / 'projects', models)
        server = make_server(0, bench)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                executable = shutil.which('chromium') or shutil.which('google-chrome')
                browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#planner-model').locator('..').locator('summary').click()
                page.locator('#planner-context').select_option('8192')
                expect(page.locator('#planner-output')).to_have_value('4096')
                page.locator('#planner-fallback-provider').select_option('groq')
                page.locator('#planner-fallback-model').fill('user-chosen-model')
                expect(page.locator('.cloud-option')).to_be_visible()
                page.locator('#planner-fallback-provider').select_option('')
                expect(page.locator('.cloud-option')).to_be_hidden()
                page.locator('#planner-fallback-provider').select_option('ollama')
                page.locator('#planner-fallback-model').fill('local-backup-planner')
                page.locator('#starter').select_option('notes')
                page.locator('#idea').fill('Build a local notes app with title/body, list, title search, delete and SQLite persistence.')
                page.locator('#propose').click()
                expect(page.locator('#proposal-review-status')).to_contain_text('recovered in 3 requests using configured fallback', timeout=15000)
                expect(page.locator('#check-cards')).to_contain_text('Restart server → GET /api/notes')
                expect(page.locator('#approve')).to_be_enabled()
                assert len(models.calls) == 3
                page.get_by_text('Edit the proposal JSON before approval', exact=True).click()
                bad = good_notes()
                bad['checks'][1]['json_contains'] = [bad['checks'][1]['json_contains']]
                page.locator('#plan-editor').fill(json.dumps(bad, indent=2))
                expect(page.locator('#proposal-findings')).to_contain_text('/checks/1/json_contains', timeout=5000)
                expect(page.locator('#approve')).to_be_disabled()
                page.screenshot(path=str(root / 'artifacts/foundry-06-review-error.png'), full_page=True)
                page.locator('#plan-editor').fill(json.dumps(good_notes(), indent=2))
                expect(page.locator('#proposal-review-status')).to_contain_text('checks passed', timeout=5000)
                expect(page.locator('#approve')).to_be_enabled()
                assert len(models.calls) == 3, 'Editing/review must not spend inference requests'
                page.get_by_text('Edit the proposal JSON before approval', exact=True).click()
                page.screenshot(path=str(root / 'artifacts/foundry-06-proposal.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Proposal review mobile overflow'
                page.screenshot(path=str(root / 'artifacts/foundry-06-mobile.png'), full_page=True)
                page.locator('#approve').click()
                state = bench.list_projects()[0]
                assert state['approved']
                assert state['planner']['options']['num_ctx'] == 8192
                assert state['planner']['fallback']['model'] == 'local-backup-planner'
                assert state['model_calls'][-1]['model'] == 'local-backup-planner'
                assert not state.get('checks'), 'Approval must not execute code'
                old = legacy_state()
                old.update(title='Legacy proposal', approved=False, status='proposed', starter='notes', plan=bad, next_task=0)
                directory = bench.directory(old['id'])
                (directory / 'source').mkdir(parents=True)
                (directory / 'state.json').write_text(json.dumps(old))
                unchanged = (directory / 'state.json').read_bytes()
                page.locator('#new-project').click()
                page.locator('#projects button').filter(has_text='Legacy proposal').click()
                expect(page.locator('#proposal-review-status')).to_contain_text('Resolve proposal contradictions', timeout=5000)
                expect(page.locator('#approve')).to_be_disabled()
                assert (directory / 'state.json').read_bytes() == unchanged
                assert len(models.calls) == 3
                assert not errors, errors
                browser.close()
                print('PASS: semantic recovery in 3 requests, explicit fallback, context/output controls, cloud consent visibility, live edit review with no inference, approval gate, restart evidence and mobile layout.')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
