"""Real browser reproduces the user's empty-plan error, recovers and approves without inference."""
from pathlib import Path
import shutil
import sys
import tempfile
import threading
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from tests.test_evidence import game_plan, CONFIG
from tests.test_workbench import ScriptedModels, await_job


def main():
    invalid = game_plan()
    invalid.pop('app_kind')
    invalid.pop('manual_checks')
    invalid['checks'] = invalid['checks'][:1]
    with tempfile.TemporaryDirectory() as temp:
        models = ScriptedModels([invalid, invalid])
        bench = Workbench(Path(temp) / 'projects', models)
        failed = bench.create('Build Neon Dodge from the arcade starter with localStorage.', CONFIG, CONFIG, 'arcade')
        failed = await_job(bench, failed['id'])
        assert failed['status'] == 'error' and failed['plan'] is None
        calls = len(models.calls)
        server = make_server(0, bench)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=shutil.which('chromium'))
                page = browser.new_page(viewport={'width': 1280, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#projects button').first.click()
                expect(page.locator('#project-status')).to_have_text('error')
                expect(page.locator('#recover-standard-game')).to_be_visible()
                page.locator('#recover-standard-game').click()
                expect(page.locator('#project-status')).to_have_text('proposed')
                expect(page.locator('#project-title')).to_have_text('Neon Dodge')
                expect(page.locator('#proposal-review-status')).to_contain_text('reviewed standard starter plan')
                expect(page.locator('#check-cards')).to_contain_text('Manual · not automated')
                expect(page.locator('#approve')).to_be_enabled()
                assert len(models.calls) == calls
                assert not bench.load(failed['id'])['approved']
                assert bench.files(failed['id']) == {}
                page.locator('#approve').click()
                expect(page.locator('#project-status')).to_have_text('approved')
                assert bench.load(failed['id'])['checks'] is None
                assert 'game.js' in bench.files(failed['id'])
                # Explicit standard creation must also avoid calling the failed model.
                page.locator('#new-project').click()
                page.locator('#arcade-example').click()
                expect(page.locator('#standard-plan-create')).to_be_visible()
                page.locator('#create-standard-game').click()
                expect(page.locator('#project-status')).to_have_text('proposed')
                assert len(models.calls) == calls
                assert len(bench.list_projects()) == 2
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                # Endpoint is still protected by the normal session token boundary.
                ident = next(s['id'] for s in bench.list_projects() if s['id'] != failed['id'])
                response = page.request.post(f'http://127.0.0.1:{server.server_port}/api/projects/{ident}/starter-plan', data={})
                assert response.status == 403
                assert not errors, errors
                browser.close()
                print('PASS: actual failed empty-plan screen → explicit standard-plan recovery → approval; direct standard creation; zero extra model calls; no code execution; authenticated endpoint; mobile layout.')
        finally:
            server.shutdown();server.server_close()


if __name__ == '__main__':
    main()
