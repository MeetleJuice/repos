"""Exception metadata without source lines, local variables or provider bodies."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
import threading
import traceback
from typing import Any, Iterator


def record_exception(recorder: Any, kind: str, exc: BaseException, **correlation: Any) -> None:
    """Best-effort frame locations; error text may contain prompts and is omitted."""
    try:
        frames = [{'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
                  for frame in traceback.extract_tb(exc.__traceback__)[-16:]]
        if isinstance(exc, SyntaxError) and exc.filename:
            frames.append({'file': Path(exc.filename).name, 'line': exc.lineno, 'function': '<syntax>'})
        recorder.record(kind, {'exception_type': type(exc).__name__, 'frames': frames,
                              'message_omitted': 'Exception text can contain private application data.'}, **correlation)
    except Exception:
        pass


@contextmanager
def exception_hooks(recorder: Any) -> Iterator[None]:
    """Install for the actual application lifetime, never as an import side effect."""
    previous_sys = sys.excepthook
    previous_thread = threading.excepthook

    def unhandled(kind: type[BaseException], exc: BaseException, tb: Any) -> None:
        record_exception(recorder, 'unhandled_exception', exc.with_traceback(tb))
        previous_sys(kind, exc, tb)

    def thread_unhandled(args: Any) -> None:
        record_exception(recorder, 'unhandled_thread_exception', args.exc_value.with_traceback(args.exc_traceback))
        previous_thread(args)

    sys.excepthook = unhandled
    threading.excepthook = thread_unhandled
    try:
        yield
    finally:
        sys.excepthook = previous_sys
        threading.excepthook = previous_thread
