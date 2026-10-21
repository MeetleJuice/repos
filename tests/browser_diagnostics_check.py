"""Diagnostics/idea UI safety. HTTP replies are fixtures, not model-quality evidence."""
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import expect, sync_playwright
from forge.core import Workbench
from forge.server import make_server


def main():
    report = {
        "schema": 1, "id": "diagnostic-fixture-1", "created_at": "2026-10-21T12:00:00Z",
        "summary": {"confirmed_failure": 1, "healthy": 2, "missing_evidence": 1},
        "findings": [{"classification": "confirmed_failure", "component": "Ollama",
                      "message": '<img src=x onerror="alert(1)"> is a literal diagnostic message',
                      "evidence_ids": ["event-fixture-1"]}],
        "completeness": {"live_model_generation": "not performed", "source_bodies": "excluded"},
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("START_HERE.md", "Fixture diagnostic export")
    with tempfile.TemporaryDirectory() as folder, patch("forge.server.connection_info", return_value={"ollama": {"connected": True, "models": ["qwen3.5:9b"]}}), patch("forge.models.request_json", return_value={}):
        bench = Workbench(Path(folder) / "projects")
        server = make_server(0, bench)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=shutil.which("chromium"))
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors, posts, idea_routes, export_bodies = [], [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: posts.append(request.url) if request.method == "POST" and request.url.endswith("/api/projects") else None)
                page.route("**/api/diagnostics", lambda route: route.fulfill(json=report))
                def download_diagnostics(route):
                    export_bodies.append(route.request.post_data_json)
                    route.fulfill(status=200, content_type="application/zip", body=stream.getvalue(), headers={"Content-Disposition": 'attachment; filename="Idea-Foundry-Diagnostics.zip"'})
                page.route("**/api/diagnostics/export", download_diagnostics)
                page.route("**/api/ideas/generate", lambda route: idea_routes.append(route))
                page.goto("http://127.0.0.1:" + str(server.server_port))
                expect(page.locator("#diag-button")).to_be_visible(timeout=3000)
                page.locator("#diag-button").click()
                expect(page.locator("#diag-dialog")).to_be_visible()
                expect(page.locator("#diag-findings")).to_contain_text("literal diagnostic message")
                assert page.locator("#diag-findings img").count() == 0
                expect(page.locator("#diag-findings")).to_contain_text("event-fixture-1")
                with page.expect_download() as pending:
                    page.locator("#diag-export").click()
                target = Path(folder) / "diagnostics.zip"
                pending.value.save_as(target)
                assert export_bodies == [{"project_id": None, "report_id": "diagnostic-fixture-1"}]
                with zipfile.ZipFile(target) as archive:
                    assert archive.read("START_HERE.md") == b"Fixture diagnostic export"
                page.locator("#close-diag").click()

                page.locator("#generate-idea").click()
                expect(page.locator("#generate-idea")).to_be_disabled()
                page.wait_for_timeout(100)
                assert len(idea_routes) == 1
                idea_routes.pop().fulfill(json={"idea": "Build a tiny local garden diary with a tested SQLite foundation.", "provider": "ollama", "model": "qwen3.5:9b"})
                expect(page.locator("#idea")).to_have_value("Build a tiny local garden diary with a tested SQLite foundation.")
                expect(page.locator("#idea-generation-status")).to_contain_text("Review")
                assert not posts and bench.list_projects() == []

                # Existing text is never silently replaced; declining sends no model request.
                page.once("dialog", lambda dialog: dialog.dismiss())
                page.locator("#generate-idea").click()
                assert len(idea_routes) == 0
                expect(page.locator("#idea")).to_have_value("Build a tiny local garden diary with a tested SQLite foundation.")

                # A response cannot overwrite text typed while the request was in flight.
                page.once("dialog", lambda dialog: dialog.accept())
                page.locator("#generate-idea").click()
                page.wait_for_timeout(100)
                assert len(idea_routes) == 1
                page.locator("#idea").fill("Keep my freshly edited idea instead of overwriting it.")
                idea_routes.pop().fulfill(json={"idea": "Build a useful pantry tracker with local persistence.", "provider": "ollama", "model": "qwen3.5:9b"})
                expect(page.locator("#idea")).to_have_value("Keep my freshly edited idea instead of overwriting it.")
                expect(page.locator("#idea-generation-status")).to_contain_text("kept")

                # Failure remains local to the helper and preserves input.
                page.once("dialog", lambda dialog: dialog.accept())
                page.locator("#generate-idea").click()
                page.wait_for_timeout(100)
                idea_routes.pop().fulfill(status=503, json={"error": "Ollama unavailable. Start Ollama and retry."})
                expect(page.locator("#idea-generation-status")).to_contain_text("Ollama unavailable")
                expect(page.locator("#idea")).to_have_value("Keep my freshly edited idea instead of overwriting it.")
                expect(page.locator("#generate-idea")).to_be_enabled()
                # A known active job is rechecked on click, without polling or inference.
                page.route("**/api/projects", lambda route: route.fulfill(json=[{"id": "active-fixture", "title": "Running fixture", "status": "building"}]))
                page.evaluate("refreshIdeaHelper([{status:'building'}])")
                page.locator("#generate-idea").click()
                expect(page.locator("#idea-generation-status")).to_contain_text("Finish or stop")
                assert not idea_routes
                page.unroute("**/api/projects")
                page.evaluate("refreshIdeaHelper([])")
                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#diag-button").click()
                expect(page.locator("#diag-findings")).to_contain_text("literal diagnostic message")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert page.locator("#diag-dialog").evaluate("element => element.scrollWidth <= element.clientWidth")
                assert not errors, errors
                assert not posts and bench.list_projects() == []
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    print("PASS: Diag fixture findings/ZIP, literal text safety and mobile layout; local idea input only, no project submission; overwrite confirmation, in-flight edit preservation and model-error recovery. No live model request was tested.")


if __name__ == "__main__":
    main()
