"""Build a source distribution from an explicit allowlist; never include local data or keys."""
from pathlib import Path
import hashlib
import zipfile
import json
import sys
import subprocess
import re
from forge import __version__, __release_notes__
from forge.updates import REPOSITORY

ROOT = Path(__file__).resolve().parent
TOP = {"AGENTS.md", "PLANS.md", "GOALS.md", "PROMPTS.md", ".env.example", ".gitignore", ".gitattributes", "LICENSE", "README.md", "Start-Foundry.bat", "run.py", "bootstrap.py", "desktop_launcher.py", "package.py", "DASHBOARD_CODEBASE_MAP.md"}
DIRECTORIES = {"forge", "docs", "tests", "examples", ".github", "tools"}


def build_identity():
    identity = {'schema': 1, 'version': __version__, 'source_commit': None,
                'tracked_modified_files': None,
                'meaning': 'Git identity at packaging time; source_tree_sha256 identifies packaged file bytes excluding this metadata.'}
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, timeout=3)
        revision = result.stdout.strip()
        if result.returncode == 0 and re.fullmatch(r'[a-f0-9]{40,64}', revision):
            identity['source_commit'] = revision
            status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, capture_output=True, text=True, timeout=3)
            if status.returncode == 0:
                identity['tracked_modified_files'] = len(status.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        pass
    return identity


def main():
    output = ROOT / "artifacts" / "Idea-Foundry.zip"
    output.parent.mkdir(exist_ok=True)
    identity = build_identity()
    tree = hashlib.sha256()
    file_count = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or "__pycache__" in relative.parts or path.suffix in {".pyc", ".db"} or path.name.endswith((".db-wal", ".db-shm")):
                continue
            if (len(relative.parts) == 1 and path.name in TOP) or relative.parts[0] in DIRECTORIES:
                if path.name == ".env" or ".git" in relative.parts or relative.as_posix() == 'forge/build-info.json':
                    continue
                entry = zipfile.ZipInfo("Idea-Foundry/" + relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                content = path.read_bytes()
                archive.writestr(entry, content)
                tree.update(relative.as_posix().encode('utf-8') + b'\0' + hashlib.sha256(content).digest())
                file_count += 1
        identity.update(source_tree_sha256=tree.hexdigest(), source_file_count=file_count)
        metadata = zipfile.ZipInfo('Idea-Foundry/forge/build-info.json', date_time=(2026, 1, 1, 0, 0, 0))
        metadata.compress_type = zipfile.ZIP_DEFLATED
        metadata.external_attr = 0o100644 << 16
        archive.writestr(metadata, json.dumps(identity, indent=2).encode('utf-8'))
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n", encoding="utf-8")
    print(f"Created {output} ({output.stat().st_size:,} bytes)")
    print("SHA256:", checksum)
    if "--release" in sys.argv:
        release = ROOT / "releases"
        release.mkdir(exist_ok=True)
        filename = "Idea-Foundry-" + __version__ + ".zip"
        archive = release / filename
        content = output.read_bytes()
        if archive.exists() and archive.read_bytes() != content:
            raise ValueError("Published release artifacts are immutable. Bump the version before replacing one.")
        archive.write_bytes(content)
        manifest = {"schema": 1, "version": __version__, "data_schema": 2, "python": [3, 11],
                    "url": f"https://raw.githubusercontent.com/{REPOSITORY}/main/releases/{filename}",
                    "sha256": checksum,
                    "notes": __release_notes__}
        (release / "latest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print("Release ready:", archive)


if __name__ == "__main__":
    main()
