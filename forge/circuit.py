"""In-memory provider transport/service circuit; finite cooldown, no sleeping retries."""
from __future__ import annotations
import threading
import time


class TransportCircuit:
    def __init__(self) -> None:
        self.failures: dict[str,tuple[int,float]]={}
        self.blocked: dict[str,float]={}
        self.lock=threading.Lock()

    def remaining(self, provider: str) -> float:
        with self.lock:return max(0,self.blocked.get(provider,0)-time.monotonic())

    def failure(self, provider: str) -> None:
        with self.lock:
            now=time.monotonic();count,last=self.failures.get(provider,(0,0))
            count=count+1 if now-last<300 else 1
            self.failures[provider]=(count,now)
            if count>=2:
                self.blocked[provider]=now+120
                self.failures.pop(provider,None)

    def success(self, provider: str) -> None:
        with self.lock:
            self.failures.pop(provider,None);self.blocked.pop(provider,None)

    def reset(self) -> None:
        with self.lock:self.failures.clear();self.blocked.clear()
