"""Optional browser test of the repaired tracker, with real persistence and UI actions."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("browser_tracker", ROOT / "examples" / "task-tracker" / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def main():
    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "tasks.db"
        server = app.create_server("127.0.0.1", 0, database)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                executable = shutil.which("chromium") or shutil.which("google-chrome")
                browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
                page = browser.new_page(viewport={"width": 1100, "height": 900})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.get_by_label("New task").fill("Buy milk")
                page.get_by_role("button", name="Add task", exact=True).click()
                expect(page.locator("#tasks")).to_contain_text("Buy milk")
                page.get_by_role("checkbox", name="Complete Buy milk").check()
                expect(page.locator("#count")).to_contain_text("0 remaining")
                page.get_by_role("button", name="Active", exact=True).click()
                expect(page.locator("#tasks li")).to_have_count(0)
                page.get_by_role("button", name="Done", exact=True).click()
                expect(page.locator("#tasks")).to_contain_text("Buy milk")
                # Restart the real HTTP server using the same SQLite file.
                server.shutdown(); server.server_close()
                server = app.create_server("127.0.0.1", 0, database)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.get_by_role("checkbox", name="Complete Buy milk")).to_be_checked()
                page.get_by_label("New task").fill('<img src=x onerror="alert(1)">')
                page.get_by_role("button", name="Add task", exact=True).click()
                expect(page.locator("#tasks li")).to_have_count(2)
                expect(page.locator("#tasks img")).to_have_count(0)
                page.get_by_label("New task").fill("Try my repaired app")
                page.get_by_role("button", name="Add task", exact=True).click()
                expect(page.locator("#tasks li")).to_have_count(3)
                (ROOT / "artifacts").mkdir(exist_ok=True)
                page.screenshot(path=str(ROOT / "artifacts" / "task-tracker.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
                page.get_by_role("button", name="Delete Buy milk", exact=True).click()
                expect(page.locator("#tasks li")).to_have_count(2)
                assert not errors, errors
                browser.close()
                print("PASS: repaired tracker browser add, complete, filters, server restart persistence, safe text, delete, and mobile layout.")
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__":
    main()
