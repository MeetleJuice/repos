"""Optional real Chromium verification. Fixed actions, fresh profile, no model scripts."""
from __future__ import annotations

import argparse
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
    import os
    if importlib.util.find_spec('playwright') is None:
        return {'available': False, 'detail': 'Optional browser tests need: python -m pip install playwright; python -m playwright install chromium'}
    executable = shutil.which('chromium') or shutil.which('google-chrome')
    caches = [Path.home() / '.cache' / 'ms-playwright', Path.home() / 'Library' / 'Caches' / 'ms-playwright']
    if os.getenv('LOCALAPPDATA'):
        caches.append(Path(os.environ['LOCALAPPDATA']) / 'ms-playwright')
    if os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
        caches.insert(0, Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']))
    installed = bool(executable) or any(any(root.glob(pattern)) for root in caches for pattern in ('chromium-*/chrome-linux/chrome', 'chromium-*/chrome-linux64/chrome', 'chromium-*/chrome-win/chrome.exe', 'chromium-*/chrome-win64/chrome.exe', 'chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium'))
    return {'available': installed, 'detail': 'Chromium installation found; launch is checked during verification.' if installed else 'Run: python -m playwright install chromium'}


class BrowserEnvironmentError(RuntimeError):
    pass


def run(source: Path) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright, expect
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
                    page = context.new_page()
                    page.set_default_timeout(3000)
                    page.on('pageerror', lambda error: errors.append(str(error)[:1000]))
                    page.on('dialog', lambda dialog: dialog.dismiss())
                    assertions = 0
                    for check in checks:
                        # Each check starts at /; storage persists only within this disposable profile.
                        page.goto(base + '/', wait_until='load', timeout=8000)
                        for step in check['steps']:
                            action = step['action']
                            locator = page.locator(step['selector']) if 'selector' in step and action != 'expect_storage' else None
                            if action == 'click': locator.click()
                            elif action == 'fill': locator.fill(step['value'])
                            elif action == 'press': page.keyboard.press(step['value'])
                            elif action == 'wait': page.wait_for_timeout(step.get('ms', 300))
                            elif action == 'reload': page.reload(wait_until='load')
                            elif action == 'expect_text': expect(locator).to_contain_text(step['value']); assertions += 1
                            elif action == 'expect_visible': expect(locator).to_be_visible(); assertions += 1
                            elif action == 'expect_storage':
                                actual = page.evaluate('(key) => localStorage.getItem(key)', step['selector'])
                                assert actual == step['value'], f"{check['name']}: localStorage mismatch"
                                assertions += 1
                            elif action == 'expect_canvas_changes':
                                before = locator.evaluate('(canvas) => canvas.toDataURL()')
                                page.wait_for_timeout(step.get('ms', 300))
                                after = locator.evaluate('(canvas) => canvas.toDataURL()')
                                assert before != after, 'Canvas did not change; this checks rendering, not collision correctness.'
                                assertions += 1
                            else: raise ValueError('Unsupported browser action')
                        assert not errors, 'Browser JavaScript errors: ' + '; '.join(errors)
                        assert not blocked, 'External browser requests blocked: ' + ', '.join(blocked)
                        print('PASS browser:', check['name'], flush=True)
                    return {'phase': 'browser', 'passed': True, 'browser_checks': len(checks), 'assertions': assertions, 'javascript_errors': errors, 'external_requests': blocked}
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
        print(json.dumps({'phase': 'browser', 'passed': False, 'error': str(exc)[:4000], 'failure_kind': 'environment' if isinstance(exc, BrowserEnvironmentError) else 'application'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
