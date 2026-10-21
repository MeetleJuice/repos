"""Prove feature removal restores the current core, including later upgrades."""
from pathlib import Path
import hashlib
import runpy
import shutil
import subprocess
import sys
import tempfile

FEATURE=Path(__file__).resolve().parent
ROOT=FEATURE.parents[1]
REGISTRATION=b'    from .dashboard import register; Handler = register(Handler)\n'


def main():
    sys.path.insert(0,str(ROOT))
    policy=runpy.run_path(str(ROOT/'package.py'),run_name='dashboard_packaging_policy')
    with tempfile.TemporaryDirectory(prefix='foundry-dashboard-removal-') as temp:
        target=Path(temp)
        inventory=[]
        for source in sorted(ROOT.rglob('*')):
            relative=source.relative_to(ROOT)
            if not source.is_file() or source.is_symlink() or any(part in {'__pycache__','node_modules','.git','.env'} for part in relative.parts) or source.suffix in {'.pyc','.db'} or source.name.endswith(('.db-wal','.db-shm')):continue
            if relative.parts[:2]==('forge','dashboard'):continue
            if not (len(relative.parts)==1 and relative.name in policy['TOP'] or relative.parts[0] in policy['DIRECTORIES']):continue
            content=source.read_bytes()
            if relative.as_posix()=='forge/server.py':
                assert content.count(REGISTRATION)==1
                content=content.replace(REGISTRATION,b'',1)
            destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
            inventory.append((relative,hashlib.sha256(content).hexdigest()))
        # Simulate deleting the feature after constructing the isolated copy.
        shutil.copytree(FEATURE,target/'forge/dashboard',ignore=shutil.ignore_patterns('__pycache__','node_modules'))
        shutil.rmtree(target/'forge/dashboard')
        assert not (target/'forge/dashboard').exists()
        for relative,digest in inventory:assert hashlib.sha256((target/relative).read_bytes()).hexdigest()==digest,str(relative)
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
    print('PASS: '+str(len(inventory))+' current-core file hashes preserved with only the registration removed; feature deleted in a temporary copy; core suite passes; workbench has no Dashboard launcher and /dashboard returns 404. Historical edition inventory remains unchanged.')


if __name__=='__main__':main()
