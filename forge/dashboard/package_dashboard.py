"""Build a distinct ZIP without modifying the core version/updater manifest."""
from pathlib import Path
import hashlib
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    subprocess.run([sys.executable,'package.py'],cwd=ROOT,check=True)
    base=ROOT/'artifacts/Idea-Foundry.zip'
    output=ROOT/'artifacts/Idea-Foundry-Dashboard-1.0.0.zip'
    with zipfile.ZipFile(base) as source,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            assert 'node_modules' not in entry.filename
            target.writestr(entry,source.read(entry))
        entry=zipfile.ZipInfo('Idea-Foundry/DASHBOARD_CODEBASE_MAP.md',date_time=(2026,1,1,0,0,0))
        entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16
        target.writestr(entry,(ROOT/'DASHBOARD_CODEBASE_MAP.md').read_bytes())
    content=output.read_bytes();checksum=hashlib.sha256(content).hexdigest()
    release=ROOT/'releases'/output.name
    if release.exists() and release.read_bytes()!=content:raise ValueError('Dashboard release is immutable; use a new dashboard edition number.')
    release.write_bytes(content)
    output.with_suffix('.zip.sha256').write_text(checksum+'  '+output.name+'\n')
    print('Dashboard edition:',output)
    print('SHA256:',checksum)
    print('Core version and releases/latest.json unchanged. Install this edition into a new folder; do not expect an automatic update offer.')


if __name__=='__main__':main()
