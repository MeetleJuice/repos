"""Request identity metrics and an evaluation-only lossless serialization prototype."""
from __future__ import annotations
import hashlib
import json
from typing import Any, TypedDict

HANDOFF_VERSION = 1


class HandoffMetrics(TypedDict):
    handoff_version: int
    input_characters: int
    prompt_sha256: str


def serialize_handoff(payload: dict[str, Any]) -> str:
    """Evaluation-only prototype; production inference retains legacy serialization."""
    if not isinstance(payload, dict):
        raise ValueError('A task handoff must be a JSON object.')
    return json.dumps(payload, separators=(',', ':'), ensure_ascii=False)


def handoff_metrics(system: str, prompt: str) -> HandoffMetrics:
    """Record identity and size, never prompt contents or invented token counts."""
    return {'handoff_version':HANDOFF_VERSION,'input_characters':len(system)+len(prompt),
            'prompt_sha256':hashlib.sha256((system+'\0'+prompt).encode('utf-8',errors='surrogatepass')).hexdigest()}
