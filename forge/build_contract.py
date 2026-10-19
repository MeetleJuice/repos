"""Keep controller-owned artifacts distinct from model-authored app files."""
from __future__ import annotations
from typing import Any
from .reporting import OWNED


def generation_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, 'file_ownership':{
        'schema':1, 'controller_owned':sorted(OWNED),
        'app_documentation':'APP-GUIDE.md',
        'instruction':'Ownership overrides file-writing instructions in task text. Foundry already supplies README.md, PROJECT.md, TASKS.md, MANUAL-CHECKS.md, checks and launch scripts. Do not create, edit or repeat those files, even if this older task requests them. Implement all app behavior and example data. Put additional app-specific usage/import-format explanations in APP-GUIDE.md. Keep existing protected tests unchanged. Return only changed editable app files or exact edits.'}}
