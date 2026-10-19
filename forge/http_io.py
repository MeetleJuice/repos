"""Bound response bytes and elapsed read time without background request threads."""
from __future__ import annotations
import time
from typing import Any

MAX_RESPONSE_BYTES = 2_000_000


class ResponseTooLarge(ValueError):
    pass


def read_bounded(response: Any, deadline: float) -> bytes:
    """Check elapsed budget between read1 calls (one buffered/raw read).

    Socket timeouts still bound individual blocking operations. A blocked read can
    overshoot the elapsed budget by up to one socket timeout; this is not a hard
    asynchronous cancellation deadline.
    """
    chunks: list[bytes]=[]
    size=0
    reader=getattr(response,'read1',None) or response.read
    while True:
        if time.monotonic()>=deadline: raise TimeoutError('Model response elapsed read budget exceeded.')
        part=reader(min(65536,MAX_RESPONSE_BYTES+1-size))
        if time.monotonic()>=deadline: raise TimeoutError('Model response elapsed read budget exceeded.')
        if not part:break
        size+=len(part)
        if size>MAX_RESPONSE_BYTES:raise ResponseTooLarge('Model response exceeded 2 MB.')
        chunks.append(part)
    return b''.join(chunks)
