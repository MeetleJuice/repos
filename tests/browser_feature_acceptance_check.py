"""New granular UI -> corrected feature packets -> real generated-app verification."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.browser_evidence_planning_check import main

if __name__=='__main__':
    main(granular=True)
    print('PASS: granular creation through feature acceptance correction, scoped task generation, unchanged human approval, actual SQLite/server/browser checks and verified ZIP. Model replies are fixtures.')
