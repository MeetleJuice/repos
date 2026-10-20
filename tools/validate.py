"""Repeatable checks; never publish, install dependencies or use real API keys."""
from pathlib import Path
import argparse
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TYPED = ('contracts planning routing schemas models evidence edits cloud credentials handoffs capabilities context history reporting providers model_status build_contract workflow http_io tasks circuit execution focus calibration streaming guided').split()


def run(args, cwd=ROOT):
    subprocess.run([sys.executable, *args], cwd=cwd, check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--types',action='store_true',help='Requires installed mypy==1.18.2.')
    parser.add_argument('--browser',action='store_true',help='Requires Playwright==1.56.0 and Chromium.')
    parser.add_argument('--package',action='store_true',help='Also build, extract and run the distribution tests.')
    args=parser.parse_args()
    run(['-m','unittest','discover','-q'])
    if args.types:run(['-m','mypy','--strict',*['forge/'+name+'.py' for name in TYPED]])
    if args.browser:
        for name in ('workflow_overview','task_contract','hybrid_execution','delivery_control','orchestration','local_harness','guided_planning','model_studio','model_activity','automatic_routing','proposal_import','upgrade','arcade','cloud','provider_pool','repair','starter_recovery','planning'):
            run(['tests/browser_'+name+'_check.py'])
    if args.package:
        run(['package.py'])
        with tempfile.TemporaryDirectory(prefix='foundry-validation-') as temp:
            with zipfile.ZipFile(ROOT/'artifacts/Idea-Foundry.zip') as archive:archive.extractall(temp)
            run(['-m','unittest','discover','-q'],Path(temp)/'Idea-Foundry')
    print('All requested validation stages passed. No release was published.')


if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as exc:raise SystemExit(exc.returncode)
