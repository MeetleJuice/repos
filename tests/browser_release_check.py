"""Guided workbench + model settings + safe change requests + backup download."""
import copy
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import threading
import zipfile
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels


def main():
    root = Path(__file__).resolve().parents[1]
    plan = copy.deepcopy(PLAN)
    plan["features"].append("Display an upgraded heading")
    plan["tasks"][0]["feature_indexes"] = [0, 1, 2]
    plan["checks"].append({"name": "New heading", "method": "GET", "path": "/", "status": 200, "contains": "Upgraded", "feature_indexes": [2]})
    changed = APP.replace("<h1>Pocket Tasks</h1>", "<h1>Pocket Tasks Upgraded</h1>")
    with tempfile.TemporaryDirectory() as temp:
        models = ScriptedModels([PLAN, {"files": {"app.py": APP, "test_app.py": TEST}}, plan, {"files": {"app.py": changed}}])
        bench = Workbench(Path(temp) / "projects", models)
        server = make_server(0, bench)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                executable = shutil.which("chromium") or shutil.which("google-chrome")
                browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#workspace-version")).to_contain_text("0.3.0")
                page.locator("#idea").fill("Build a simple task tracker")
                page.locator("#propose").click()
                expect(page.locator("#next-title")).to_have_text("Review the plan before we build", timeout=15000)
                expect(page.locator("#check-cards")).to_contain_text("Create task")
                page.locator("#approve").click()
                expect(page.locator("#next-title")).to_contain_text("plan is approved")
                page.locator("#generate").click()
                expect(page.locator("#project-status")).to_have_text("Files ready · not tested", timeout=15000)
                page.locator("#edit-models").click()
                page.locator("#project-coder-model").fill("test-coder")
                page.get_by_role("button", name="Save model choices").click()
                expect(page.locator("#model-label")).to_contain_text("test-coder")
                page.locator("#runtime").select_option("local")
                page.locator("#execution-consent").check()
                page.locator("#verify").click()
                expect(page.locator("#project-status")).to_have_text("verified", timeout=15000)
                parent = bench.list_projects()[0]["id"]
                page.locator("#change-request").fill("Add an upgraded heading to the interface")
                page.locator("#request-change").click()
                expect(page.locator("#project-lineage")).to_contain_text("Improvement of Pocket Tasks", timeout=15000)
                expect(page.locator("#next-title")).to_have_text("Review the plan before we build", timeout=15000)
                page.locator("#approve").click()
                page.locator("#verify").click()
                expect(page.locator("#project-status")).to_have_text("verified", timeout=15000)
                self_parent = bench.load(parent)
                assert bench.files(parent)["app.py"] == APP
                assert self_parent["status"] == "verified"
                page.get_by_role("tab", name="Project files").click()
                page.get_by_text("Review changes since the last checkpoint", exact=True).click()
                page.locator("#review-diff").click()
                expect(page.locator("#diff-list")).to_contain_text("app.py")
                page.locator("#workspace-button").click()
                expect(page.locator("#workspace-details")).to_contain_text("Projects: 2")
                with page.expect_download() as info:
                    page.locator("#backup-workspace").click()
                archive_path = Path(temp) / "backup.zip"
                info.value.save_as(archive_path)
                with zipfile.ZipFile(archive_path) as archive:
                    assert len([n for n in archive.namelist() if n.endswith('/state.json')]) == 2
                page.locator("#close-workspace").click()
                (root / "artifacts").mkdir(exist_ok=True)
                page.screenshot(path=str(root / "artifacts" / "foundry-03.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
                page.screenshot(path=str(root / "artifacts" / "foundry-03-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
                print("PASS: guided build, human-readable checks, model switch, verified app, change request, preserved original, diffs, workspace backup, and mobile layout.")
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__":
    main()
