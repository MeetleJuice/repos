"""0.5 onboarding, runtime readiness, starter export, and update-dialog browser check."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import tempfile
import threading
import zipfile
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels
from tests.test_updates import archive_for, manifest_for


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp, patch('forge.server.runtime_diagnostics', return_value={'installed': False, 'running': False, 'image_ready': False}):
        models = ScriptedModels([PLAN, {'files': {'app.py': APP, 'test_app.py': TEST}}])
        bench = Workbench(Path(temp) / 'projects', models)
        server = make_server(0, bench)
        release = manifest_for(archive_for())
        server.updater.downloader = lambda *args: json.dumps(release).encode()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                executable = shutil.which('chromium') or shutil.which('google-chrome')
                browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1080})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#update-button')).to_be_visible()
                expect(page.locator('#starter')).to_have_value('web')
                page.screenshot(path=str(artifacts / 'foundry-05-home.png'), full_page=True)
                page.locator('#update-button').click()
                page.locator('#check-update').click()
                expect(page.locator('#update-status')).to_have_text('Version 0.5.1 is available.')
                expect(page.locator('#install-update')).to_be_disabled()  # test server bypasses stable launcher
                expect(page.locator('#update-history')).to_contain_text('Start-Foundry.bat')
                page.screenshot(path=str(artifacts / 'foundry-05-update.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Update dialog mobile overflow'
                page.locator('#close-update').click()
                page.screenshot(path=str(artifacts / 'foundry-05-home-mobile.png'), full_page=True)
                page.set_viewport_size({'width': 1440, 'height': 1080})
                page.locator('#idea').fill('Build a task tracker with saved tasks')
                page.locator('#propose').click()
                expect(page.locator('#next-title')).to_have_text('Review the plan before we build', timeout=10000)
                page.locator('#approve').click()
                expect(page.locator('#runtime-readiness')).to_contain_text('Docker is not installed')
                expect(page.locator('#verify')).to_be_disabled()
                page.locator('#generate').click()
                expect(page.locator('#project-status')).to_have_text('Files ready · not tested', timeout=10000)
                expect(page.locator('#execution-consent')).not_to_be_checked()
                page.locator('#runtime').select_option('local')
                expect(page.locator('#verify')).to_be_enabled()
                expect(page.locator('#runtime-note')).to_contain_text('not a sandbox')
                page.locator('#execution-consent').check()
                page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified', timeout=15000)
                expect(page.locator('#phase-list')).to_contain_text('Passed')
                page.screenshot(path=str(artifacts / 'foundry-05-verification.png'), full_page=True)
                page.get_by_role('tab', name='Project files').click()
                with page.expect_download() as info:
                    page.locator('#download').click()
                downloaded = Path(temp) / 'app.zip'
                info.value.save_as(downloaded)
                with zipfile.ZipFile(downloaded) as archive:
                    assert 'generated-app/test_foundation.py' in archive.namelist()
                    report = json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['checks']['passed']
                    assert report['checks']['phases'][1]['tests_run'] == 2
                page.locator('#project-search').fill('no matches')
                expect(page.locator('#projects button')).to_have_count(0)
                page.locator('#project-search').fill('Pocket')
                expect(page.locator('#projects button')).to_have_count(1)
                assert not errors, errors
                browser.close()
                print('PASS: tested foundation, clear missing-Docker state, consent, actual verification, protected test export, project search, update dialog, desktop/mobile and no JS errors.')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
