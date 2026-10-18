"""Optional real-browser check of the repaired Notes App."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("browser_notes_app", ROOT / "examples" / "notes-app" / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def main():
    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "notes.db"
        server = app.create_server("127.0.0.1", 0, database)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                executable = shutil.which("chromium") or shutil.which("google-chrome")
                browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
                page = browser.new_page(viewport={"width": 1100, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.get_by_label("Title", exact=True).fill("Buy milk")
                page.get_by_label("Your note", exact=True).fill("Need to buy groceries")
                page.get_by_role("button", name="Save note").click()
                expect(page.locator("#notes")).to_contain_text("Need to buy groceries")
                page.get_by_label("Title", exact=True).fill("Weekend plans")
                page.get_by_label("Your note", exact=True).fill("Read a book")
                page.get_by_role("button", name="Save note").click()
                expect(page.locator("#notes article")).to_have_count(2)
                page.locator("#search").fill("milk")
                expect(page.locator("#notes article")).to_have_count(1)
                expect(page.locator("#notes")).to_contain_text("Buy milk")
                page.locator("#search").fill("no-such-title")
                expect(page.locator("#notes article")).to_have_count(0)
                page.locator("#search").fill("")
                server.shutdown(); server.server_close()
                server = app.create_server("127.0.0.1", 0, database)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#notes article")).to_have_count(2)
                expect(page.locator("#notes")).to_contain_text("Need to buy groceries")
                page.get_by_label("Title", exact=True).fill('<img src=x onerror="alert(1)">')
                page.get_by_label("Your note", exact=True).fill("<script>alert(1)</script>")
                page.get_by_role("button", name="Save note").click()
                expect(page.locator("#notes article")).to_have_count(3)
                expect(page.locator("#notes img, #notes script")).to_have_count(0)
                (ROOT / "artifacts").mkdir(exist_ok=True)
                page.screenshot(path=str(ROOT / "artifacts" / "notes-app.png"), full_page=True)
                page.get_by_role("button", name="Delete Buy milk", exact=True).click()
                expect(page.locator("#notes article")).to_have_count(2)
                expect(page.locator("#notes")).not_to_contain_text("Buy milk")
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
                assert not errors, errors
                browser.close()
                print("PASS: Notes App browser create/title/body, matching/nonmatching search, restart persistence, safe text, deletion, mobile layout; no JavaScript errors.")
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__":
    main()
