"""Actual Chromium gameplay and full Foundry pipeline; no live model calls."""
from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile
import threading
import zipfile
import io
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from forge.runner import verify
from forge.scaffolds import starter_files
from tests.test_evidence import game_plan, CONFIG
from tests.test_workbench import ScriptedModels

ROOT = Path(__file__).resolve().parents[1]


def browser_checks():
    return [{'name': 'Start, animate and pause', 'feature_indexes': [1, 2], 'steps': [
        {'action': 'click', 'selector': '#start'},
        {'action': 'expect_text', 'selector': '#state', 'value': 'Playing'},
        {'action': 'expect_canvas_changes', 'selector': '#game', 'ms': 300},
        {'action': 'click', 'selector': '#pause'},
        {'action': 'expect_text', 'selector': '#state', 'value': 'Paused'},
    ]}]


def ship_x(page):
    return page.locator('#game').evaluate('''canvas => {
        const data = canvas.getContext('2d').getImageData(0, 570, 600, 35).data;
        let sum=0, count=0;
        for (let i=0;i<data.length;i+=4) if(data[i]<150 && data[i+1]>180 && data[i+2]>210){sum+=(i/4)%600;count++;}
        if(!count) throw new Error('Ship pixels not rendered');
        return sum/count;
    }''')


def main():
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plan = game_plan()
        # Exercise optional automation in addition to manual observations.
        plan['browser_checks'] = browser_checks()
        files = starter_files('arcade')
        models = ScriptedModels([plan, {'files': {'game.js': files['game.js']}}, {'files': {'test_app.py': files['test_app.py']}}])
        bench = Workbench(root / 'projects', models)
        server = make_server(0, bench)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=shutil.which('chromium'))
                page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('.brand-mark')).to_have_attribute('src', '/icon.png')
                page.locator('#arcade-example').click()
                expect(page.locator('#starter')).to_have_value('arcade')
                page.locator('#propose').click()
                expect(page.locator('#approve')).to_be_enabled(timeout=15000)
                expect(page.locator('#check-cards')).to_contain_text('Manual · not automated')
                page.screenshot(path=str(ROOT / 'artifacts/foundry-07-proposal.png'), full_page=True)
                page.locator('#approve').click()
                expect(page.locator('#project-status')).to_contain_text('approved')
                page.locator('#generate').click()
                expect(page.locator('#project-status')).to_contain_text('Files ready', timeout=20000)
                page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check()
                page.locator('#verify').click()
                expect(page.locator('#project-status')).to_contain_text('Automated checks passed', timeout=45000)
                expect(page.locator('#phase-list')).to_contain_text('Real browser interactions')
                expect(page.locator('#manual-panel')).to_be_visible()
                expect(page.locator('#manual-result')).to_contain_text('Download and try')
                ident = bench.list_projects()[0]['id']
                state = bench.load(ident)
                assert state['status'] == 'review_required'
                assert state['checks']['phases'][-1]['phase'] == 'browser'
                assert state['checks']['phases'][-1]['assertions'] == 3
                assert state['manual_results'] == {}
                source = bench.directory(ident) / 'source'
                # Play the real generated/exportable app; do not read app-internal state hooks.
                spec = importlib.util.spec_from_file_location('arcade_under_test', source / 'app.py')
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                game_server = module.create_server('127.0.0.1', 0)
                threading.Thread(target=game_server.serve_forever, daemon=True).start()
                try:
                    game = browser.new_page(viewport={'width': 1000, 'height': 1000})
                    game.on('pageerror', lambda error: errors.append(str(error)))
                    game.add_init_script('Math.random = () => 0.5')  # deterministic center obstacles, no app test hooks
                    game.goto(f'http://127.0.0.1:{game_server.server_port}')
                    game.locator('#start').click()
                    expect(game.locator('#state')).to_have_text('Playing')
                    game.wait_for_timeout(150)
                    before = ship_x(game)
                    game.keyboard.down('ArrowLeft'); game.wait_for_timeout(250); game.keyboard.up('ArrowLeft')
                    assert ship_x(game) < before - 40, 'Arrow key did not move rendered ship'
                    game.keyboard.down('d'); game.wait_for_timeout(250); game.keyboard.up('d')
                    assert ship_x(game) > before - 30, 'D key did not move rendered ship right'
                    game.locator('#pause').click()
                    expect(game.locator('#state')).to_have_text('Paused')
                    game.wait_for_timeout(100)
                    paused_score = game.locator('#score').inner_text()
                    frozen = game.locator('#game').evaluate('(c) => c.toDataURL()')
                    game.wait_for_timeout(400)
                    assert game.locator('#score').inner_text() == paused_score
                    assert game.locator('#game').evaluate('(c) => c.toDataURL()') == frozen
                    game.locator('#pause').click()
                    expect(game.locator('#state')).to_have_text('Playing')
                    game.locator('#restart').click()
                    assert int(game.locator('#score').inner_text()) <= 1
                    expect(game.locator('#state')).to_have_text('Game over', timeout=10000)
                    final = int(game.locator('#score').inner_text())
                    assert final > 0
                    best = game.locator('#best').inner_text()
                    game.reload()
                    expect(game.locator('#best')).to_have_text(best)
                    assert int(best) >= final
                    game.set_viewport_size({'width': 390, 'height': 844})
                    assert game.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    game.locator('#start').click();game.wait_for_timeout(100)
                    original_x = ship_x(game)
                    box = game.locator('#left').bounding_box()
                    game.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
                    game.mouse.down();game.wait_for_timeout(250);game.mouse.up()
                    assert ship_x(game) < original_x - 40, 'Pointer-held movement failed'
                    game.screenshot(path=str(ROOT / 'artifacts/neon-dodge-07-mobile.png'), full_page=True)
                    game.close()
                finally:
                    game_server.shutdown(); game_server.server_close()
                for i in range(len(plan['manual_checks'])):
                    page.locator('#manual-' + str(i)).select_option('pass')
                page.locator('#save-manual').click()
                expect(page.locator('#project-status')).to_have_text('verified')
                expect(page.locator('#manual-result')).to_contain_text('User-reported observations')
                page.screenshot(path=str(ROOT / 'artifacts/foundry-07-accepted.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Workbench mobile overflow'
                page.screenshot(path=str(ROOT / 'artifacts/foundry-07-mobile.png'), full_page=True)
                # Download really includes frozen contracts and honest provenance.
                token = page.locator('meta[name="foundry-token"]').get_attribute('content')
                response = page.request.get(f'http://127.0.0.1:{server.server_port}/api/projects/{ident}/download', headers={'X-Foundry-Token': token})
                assert response.ok
                with zipfile.ZipFile(io.BytesIO(response.body())) as archive:
                    report = json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['manual_results']['evidence'].startswith('User-reported')
                    assert len(report['manual_checks']) == 4
                    assert 'generated-app/BROWSER-CHECKS.json' in archive.namelist()
                assert not errors, errors
                browser.close()
            # A broken real JS handler must fail browser verification, not get a green pass.
            broken = root / 'broken';shutil.copytree(source, broken)
            js = (broken / 'game.js').read_text().replace('addEventListener("click", start)', 'addEventListener("click", () => {})')
            (broken / 'game.js').write_text(js)
            result = verify(broken, 'local', threading.Event())
            assert not result['passed'] and result['phases'][-1]['phase'] == 'browser', result
            assert 'Playing' in result['log']
            print('PASS: real plan/build/HTTP/tests/launch/Chromium/manual/export pipeline; rendered keyboard/pointer movement, pause freeze, collision/game-over, restart, high-score refresh persistence; mobile layout; broken JS rejected.')
        finally:
            server.shutdown();server.server_close()


if __name__ == '__main__':
    main()
