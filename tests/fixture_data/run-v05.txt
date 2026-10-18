"""Launch the supervised workbench; --server is an internal child-process option."""
import sys
from pathlib import Path

if __name__ == '__main__':
    if '--server' in sys.argv:
        sys.argv.remove('--server')
        from forge.server import main
        main()
    else:
        from bootstrap import supervise
        raise SystemExit(supervise(Path(__file__).resolve().parent, sys.argv[1:]))
