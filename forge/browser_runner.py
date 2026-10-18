"""Optional real Chromium verification. Fixed actions, fresh profile, no model scripts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit


def diagnostics() -> dict[str, Any]:
    # Inspect installation only; opening a connection panel must not launch Node/Chromium.
    import importlib.util
    import importlib.metadata
    import os
    if importlib.util.find_spec('playwright') is None:
        return {'available': False, 'detail': 'Optional browser tests need: python -m pip install playwright==1.56.0; python -m playwright install chromium'}
    try:
        version = importlib.metadata.version('playwright')
        clock_supported = tuple(int(v) for v in version.split('.')[:2]) >= (1, 45)
    except (importlib.metadata.PackageNotFoundError, ValueError):
        version, clock_supported = 'unknown', False
    executable = shutil.which('chromium') or shutil.which('google-chrome')
    caches = [Path.home() / '.cache' / 'ms-playwright', Path.home() / 'Library' / 'Caches' / 'ms-playwright']
    if os.getenv('LOCALAPPDATA'):
        caches.append(Path(os.environ['LOCALAPPDATA']) / 'ms-playwright')
    if os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
        caches.insert(0, Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']))
    installed = bool(executable) or any(any(root.glob(pattern)) for root in caches for pattern in ('chromium-*/chrome-linux/chrome', 'chromium-*/chrome-linux64/chrome', 'chromium-*/chrome-win/chrome.exe', 'chromium-*/chrome-win64/chrome.exe', 'chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium'))
    return {'available': installed, 'version': version, 'clock_supported': clock_supported, 'detail': 'Chromium installation found; launch is checked during verification.' if installed else 'Run: python -m playwright install chromium'}


class BrowserEnvironmentError(RuntimeError):
    pass


class BrowserCheckError(AssertionError):
    def __init__(self, details: dict[str, Any]):
        self.details = details
        super().__init__(json.dumps(details, ensure_ascii=False))


def initialize_page(page: Any, check: dict[str, Any]) -> None:
    """Fixed instrumentation only. Never execute model-provided JavaScript."""
    if 'random_values' in check:
        page.add_init_script("{ const values = " + json.dumps(check['random_values']) + "; let i = 0; Math.random = () => values[Math.min(i++, values.length - 1)]; }")
    elif 'random_seed' in check:
        page.add_init_script("{ let seed = " + str(check['random_seed']) + "; Math.random = () => { seed = (Math.imul(1664525, seed) + 1013904223) >>> 0; return seed / 4294967296; }; }")
    if check.get('clock'):
        if not hasattr(page, 'clock'):
            raise BrowserEnvironmentError('Controlled-clock tests need Playwright 1.45 or newer. Update the optional Playwright installation.')
        page.clock.install(time=datetime(2026, 1, 1, tzinfo=timezone.utc))


def perform_step(page: Any, step: dict[str, Any], clock: bool) -> int:
    from playwright.sync_api import expect
    action = step['action']
    locator = page.locator(step['selector']) if 'selector' in step and action != 'expect_storage' else None
    if action == 'click': locator.click()
    elif action == 'fill': locator.fill(step['value'])
    elif action == 'press': page.keyboard.press(step['value'])
    elif action == 'key_down': page.keyboard.down(step['value'])
    elif action == 'key_up': page.keyboard.up(step['value'])
    elif action == 'advance_time': page.clock.run_for(step['ms'])
    elif action == 'wait':
        if clock: page.clock.run_for(step.get('ms', 300))
        else: page.wait_for_timeout(step.get('ms', 300))
    elif action == 'reload': page.reload(wait_until='load')
    elif action == 'expect_text': expect(locator).to_contain_text(step['value']); return 1
    elif action == 'expect_text_exact': expect(locator).to_have_text(step['value']); return 1
    elif action == 'expect_visible': expect(locator).to_be_visible(); return 1
    elif action == 'expect_storage':
        actual = page.evaluate('(key) => localStorage.getItem(key)', step['selector'])
        assert actual == step['value'], f"localStorage mismatch: expected {step['value']!r}, got {actual!r}"
        return 1
    elif action in {'expect_canvas_changes', 'expect_canvas_still'}:
        before = locator.evaluate('(canvas) => canvas.toDataURL()')
        if clock: page.clock.run_for(step.get('ms', 300))
        else: page.wait_for_timeout(step.get('ms', 300))
        after = locator.evaluate('(canvas) => canvas.toDataURL()')
        if action == 'expect_canvas_changes':
            assert before != after, 'Canvas did not change; this checks rendering, not collision correctness.'
        else:
            assert before == after, 'Canvas changed while expected to remain still.'
        return 1
    else: raise ValueError('Unsupported browser action')
    return 0


def run(source: Path) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright
    from harness import start_app_process, stop_app_process
    import os
    errors: list[str] = []
    blocked: list[str] = []
    checks = json.loads((source / 'BROWSER-CHECKS.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='foundry-browser-') as temp:
        root = Path(temp)
        shutil.copytree(source, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.db', '*.sqlite*'))
        old = Path.cwd()
        os.chdir(root)
        proc = None
        try:
            proc, base = start_app_process()
            with sync_playwright() as p:
                executable = shutil.which('chromium') or shutil.which('google-chrome')
                try:
                    browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
                except Exception as exc:
                    raise BrowserEnvironmentError('Chromium could not start. Check Playwright/browser installation and host dependencies: ' + str(exc)[:1500]) from exc
                try:
                    context = browser.new_context(viewport={'width': 1000, 'height': 800}, service_workers='block', accept_downloads=False)
                    def route_request(route: Any) -> None:
                        url = urlsplit(route.request.url)
                        if url.scheme in {'data', 'about', 'blob'} or (url.scheme == 'http' and url.netloc == urlsplit(base).netloc):
                            route.continue_()
                        else:
                            blocked.append(url.scheme + '://' + url.netloc)
                            route.abort()
                    context.route('**/*', route_request)
                    if hasattr(context, 'route_web_socket'):
                        def block_socket(route: Any) -> None:
                            blocked.append('websocket')
                            route.close(code=1008, reason='External sockets are not part of this verification contract')
                        context.route_web_socket('**/*', block_socket)
                    assertions = 0
                    completed = []
                    for check in checks:
                        # A new page resets script/clock instrumentation; only disposable storage is shared.
                        page = context.new_page()
                        page.set_default_timeout(3000)
                        page.on('pageerror', lambda error: errors.append(str(error)[:1000]))
                        page.on('dialog', lambda dialog: dialog.dismiss())
                        try:
                            initialize_page(page, check)
                            page.goto(base + '/', wait_until='load', timeout=8000)
                            if check.get('clock'):
                                page.clock.pause_at(datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
                            for index, step in enumerate(check['steps']):
                                try:
                                    assertions += perform_step(page, step, bool(check.get('clock')))
                                    assert not errors, 'Browser JavaScript errors: ' + '; '.join(errors)
                                    assert not blocked, 'External browser requests blocked: ' + ', '.join(blocked)
                                except Exception as exc:
                                    raise BrowserCheckError({'check': check['name'], 'step_number': index + 1,
                                        'step': step, 'completed_steps': check['steps'][:index],
                                        'clock': bool(check.get('clock')), 'random_seed': check.get('random_seed'),
                                        'random_values': check.get('random_values'), 'error': str(exc)[:2500],
                                        'javascript_errors': errors[-5:], 'external_requests': blocked[-5:]}) from exc
                            completed.append({'name': check['name'], 'steps': len(check['steps']), 'clock': bool(check.get('clock'))})
                            print('PASS browser:', check['name'], flush=True)
                        finally:
                            page.close()
                    return {'phase': 'browser', 'passed': True, 'browser_checks': len(checks), 'assertions': assertions, 'javascript_errors': errors, 'external_requests': blocked, 'completed': completed}
                finally:
                    browser.close()
        finally:
            if proc is not None: stop_app_process(proc)
            os.chdir(old)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.source.resolve())))
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(json.dumps({'phase': 'browser', 'passed': False, 'error': str(exc)[:4000], 'failure_kind': 'environment' if isinstance(exc, BrowserEnvironmentError) else 'application', 'browser_failure': exc.details if isinstance(exc, BrowserCheckError) else None}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
