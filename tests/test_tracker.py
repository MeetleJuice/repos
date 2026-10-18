"""Run the shipped repaired tracker tests in the workbench CI too."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("repaired_tracker_tests", Path(__file__).resolve().parents[1] / "examples" / "task-tracker" / "test_app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TrackerTests = module.TrackerTests
