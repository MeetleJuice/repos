"""Build a source distribution from an explicit allowlist; never include local data or keys."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parent
TOP = {".env.example", ".gitignore", ".gitattributes", "LICENSE", "README.md", "Start-Foundry.bat", "run.py", "package.py"}
DIRECTORIES = {"forge", "docs", "tests", "examples", ".github"}


def main():
    output = ROOT / "artifacts" / "Idea-Foundry.zip"
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or "__pycache__" in relative.parts or path.suffix in {".pyc", ".db"} or path.name.endswith((".db-wal", ".db-shm")):
                continue
            if (len(relative.parts) == 1 and path.name in TOP) or relative.parts[0] in DIRECTORIES:
                if path.name == ".env" or ".git" in relative.parts:
                    continue
                archive.write(path, "Idea-Foundry/" + relative.as_posix())
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n", encoding="utf-8")
    print(f"Created {output} ({output.stat().st_size:,} bytes)")
    print("SHA256:", checksum)


if __name__ == "__main__":
    main()
