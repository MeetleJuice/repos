"""Launch the supervised workbench; --server is an internal child-process option."""
import sys
from pathlib import Path

if __name__ == '__main__':
    if '--server' in sys.argv:
        sys.argv.remove('--server')
        try:
            from forge.server import main
            main()
        except BaseException as exc:
            # This helper is independent of forge imports. Old launchers without it
            # still retain their ordinary startup rollback behavior.
            if not isinstance(exc, (KeyboardInterrupt, SystemExit)) or isinstance(exc, SystemExit) and exc.code not in (None, 0, 75):
                try:
                    from bootstrap import home_for, record_launcher_exception
                    record_launcher_exception(home_for(Path(__file__).resolve().parent, sys.argv[1:]), exc)
                except (ImportError, OSError):
                    pass
            raise
    else:
        from bootstrap import supervise
        raise SystemExit(supervise(Path(__file__).resolve().parent, sys.argv[1:]))
