"""Run the repaired Notes App behavioral tests in CI."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("repaired_notes_tests", Path(__file__).resolve().parents[1] / "examples" / "notes-app" / "test_app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NotesTests = module.NotesTests
