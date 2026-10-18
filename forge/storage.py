"""User data separate from downloaded program files, with conservative legacy import."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import uuid
import re


def data_home(program_root, override=None):
    if override or os.getenv("FOUNDRY_HOME"):
        return Path(override or os.environ["FOUNDRY_HOME"]).expanduser().resolve()
    if os.name == "nt":
        return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "IdeaFoundry"
    # Preserve the existing portable layout on non-Windows installations.
    return Path(program_root) / "data"


def import_legacy(program_root, target, warnings=None):
    """Copy missing legacy projects once; never overwrite a project or remove originals."""
    legacy = Path(program_root) / "data" / "projects"
    destination = Path(target) / "projects"
    if legacy.resolve() == destination.resolve() or not legacy.exists():
        return []
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    skipped = []
    for source in sorted(legacy.iterdir()):
        if not source.is_dir() or source.is_symlink() or not (source / "state.json").is_file():
            continue
        if (destination / source.name).exists():
            continue
        # Validate metadata before copying, but never execute project code.
        try:
            state = json.loads((source / "state.json").read_text(encoding="utf-8"))
            if not isinstance(state, dict) or state.get("id") != source.name or not re.fullmatch(r"[a-f0-9]{32}", source.name):
                raise ValueError("Metadata does not match its project directory.")
            if any(p.is_symlink() for p in source.rglob("*")):
                raise ValueError("Project contains symbolic links.")
        except (ValueError, OSError):
            skipped.append(f"Could not import legacy project {source.name}. Its original files were kept beside the old program.")
            continue
        staging = destination / (".import-" + uuid.uuid4().hex)
        try:
            shutil.copytree(source, staging)
            (staging / "state.json").read_text(encoding="utf-8")
            os.replace(staging, destination / source.name)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        copied.append(source.name)
    if warnings is not None:
        warnings.extend(skipped)
    if copied or skipped:
        record = Path(target) / ("legacy-import-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".json")
        record.write_text(json.dumps({"imported": copied, "skipped": skipped, "originals_preserved": True}, indent=2), encoding="utf-8")
    return copied


@contextmanager
def workspace_lock(home):
    Path(home).mkdir(parents=True, exist_ok=True)
    with (Path(home) / ".workspace.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Another Idea Foundry is using this data folder. Stop its terminal before starting this copy.") from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
