"""Optional end-to-end browser check with scripted model responses (no paid APIs)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
import threading
import shutil
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from tests.fixtures import PLAN, BROKEN, APP, TEST
from tests.test_workbench import ScriptedModels


def main():
    artifacts = Path(__file__).resolve().parents[1] / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        models = ScriptedModels([PLAN, {"files": {"app.py": BROKEN, "test_app.py": TEST}}, {"summary": "Fixed task listing", "files": {"app.py": APP}}])
        bench = Workbench(temp, models)
        server = make_server(0, bench)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                executable = shutil.which("chromium") or shutil.which("google-chrome")
                browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
                page = browser.new_page(viewport={"width": 1440, "height": 1080})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.get_by_role("heading", name="What will you bring to life?")).to_be_visible()
                page.screenshot(path=str(artifacts / "workbench.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile page overflows"
                page.screenshot(path=str(artifacts / "workbench-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1080})
                page.locator("#idea").fill("Build a small persistent task tracker")
                page.get_by_role("button", name="Shape my idea").click()
                expect(page.locator("#project-title")).to_have_text("Pocket Tasks", timeout=15000)
                expect(page.locator("#features")).to_contain_text("Create a task")
                page.get_by_role("button", name="Approve this project").click()
                page.get_by_role("button", name="Generate / resume code").click()
                expect(page.locator("#project-status")).to_have_text("Files ready · not tested", timeout=15000)
                expect(page.locator("#test-badge")).to_have_text("Not verified")
                page.locator("#runtime").select_option("local")
                expect(page.locator("#runtime-note")).to_contain_text("not a sandbox")
                page.locator("#execution-consent").check()
                page.get_by_role("button", name="Build, test & repair").click()
                expect(page.locator("#project-status")).to_have_text("verified", timeout=25000)
                expect(page.locator("#events")).to_contain_text("Repair attempt 1")
                expect(page.locator("#test-badge")).to_have_text("Checks passed")
                page.screenshot(path=str(artifacts / "verified-build.png"), full_page=True)
                page.get_by_role("tab", name="Project files").click()
                expect(page.locator("#file-list")).to_contain_text("app.py")
                expect(page.locator("#file-content")).to_contain_text("def create_server")
                with page.expect_download() as info:
                    page.get_by_role("button", name="Download app .zip").click()
                download = info.value
                download.save_as(str(artifacts / "browser-tested-generated-app.zip"))
                assert not errors, errors
                browser.close()
                print("PASS: browser idea → proposal → approval → generation → failing checks → repair → verified → files → ZIP download; desktop/mobile layout; no JavaScript errors.")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
