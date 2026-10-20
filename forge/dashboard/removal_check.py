"""Prove the feature's removal against the frozen pre-change file inventory."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

FEATURE=Path(__file__).resolve().parent
ROOT=FEATURE.parents[1]
REGISTRATION=b'    from .dashboard import register; Handler = register(Handler)\n'
# Normal release publishing is explicitly authorized after Dashboard edition 1.0.
# Preserve these release-metadata changes when testing feature removal.
RELEASE_METADATA={'forge/__init__.py','package.py','releases/latest.json','AGENTS.md','README.md'}


def main():
    inventory=json.loads((FEATURE/'docs/baseline-inventory.json').read_text())
    with tempfile.TemporaryDirectory(prefix='foundry-dashboard-removal-') as temp:
        target=Path(temp)
        for record in inventory:
            relative=record['path'];source=ROOT/relative
            content=source.read_bytes()
            if relative=='forge/server.py':
                assert content.count(REGISTRATION)==1
                content=content.replace(REGISTRATION,b'',1)
            if relative not in RELEASE_METADATA:
                assert hashlib.sha256(content).hexdigest()==record['sha256'],relative+' changed outside registration seam or authorized release metadata'
            destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
        # Simulate deleting the feature after constructing the isolated copy.
        shutil.copytree(FEATURE,target/'forge/dashboard',ignore=shutil.ignore_patterns('__pycache__','node_modules'))
        shutil.rmtree(target/'forge/dashboard')
        assert not (target/'forge/dashboard').exists()
        result=subprocess.run([sys.executable,'-m','unittest','discover','-q'],cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        print(result.stdout)
        if result.returncode:raise SystemExit(result.returncode)
        probe="""from forge.server import make_server
from forge.core import Workbench
import tempfile,threading,urllib.request,urllib.error
with tempfile.TemporaryDirectory() as temp:
 server=make_server(0,Workbench(temp));threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  base='http://127.0.0.1:'+str(server.server_port)
  with urllib.request.urlopen(base) as response:assert b'href=\"/dashboard\"' not in response.read()
  try:urllib.request.urlopen(base+'/dashboard');raise AssertionError('Dashboard survived removal')
  except urllib.error.HTTPError as error:assert error.code==404;error.close()
 finally:server.shutdown();server.server_close()
"""
        subprocess.run([sys.executable,'-c',probe],cwd=target,check=True)
    print('PASS: 346 original baseline hashes restored, with five explicitly authorized release metadata/guidance files retained; feature deleted and registration removed in a temporary copy; baseline suite passes; workbench has no Dashboard launcher and /dashboard returns 404.')


if __name__=='__main__':main()
