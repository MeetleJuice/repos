"""Frozen, paired prompt-transport experiment. Never calls providers or executes repairs.

Optional exact normalized counts: install tiktoken==0.12.0 outside the product,
then run with --encoding-file pointing to the SHA-verified cl100k_base data.
Without that flag, report characters and semantic round-trips only.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forge.prompts import CODE

DATA = Path(__file__).with_name('fixture_data')/'handoff-regressions-v1.json'
DATA_SHA = 'bbd15c652c4c919a51987a25a6a309320204e2e1f4ce62e27b904560744491f7'
ENCODING_SHA = '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'


def structured_brief(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluation-only prototype; never wired into Foundry inference."""
    result = {'contract_version':1,'role':'repairer',
              'goal':'Resolve the evidenced failure while preserving approved behavior.',
              'context':payload,
              'constraints':{'preserve_frozen_tests':True,'maximum_corrections':1},
              'done_when':['Candidate is valid source','Independent approved checks and regressions pass','Manual observations remain pending until reviewed']}
    validate_brief(result)
    return result


def validate_brief(value: Any) -> None:
    if not isinstance(value,dict) or set(value) != {'contract_version','role','goal','context','constraints','done_when'}:
        raise ValueError('Invalid brief fields.')
    if value['contract_version'] != 1 or value['role'] != 'repairer' or not isinstance(value['context'],dict):
        raise ValueError('Unsupported brief contract.')
    if value['constraints'] != {'preserve_frozen_tests':True,'maximum_corrections':1} or not isinstance(value['goal'],str) or not value['goal']:
        raise ValueError('Invalid repair authority.')
    if not isinstance(value['done_when'],list) or not value['done_when'] or not all(isinstance(x,str) and x for x in value['done_when']):
        raise ValueError('Missing completion criteria.')


def evaluate(encoding_file: str | None = None) -> dict[str, Any]:
    content = DATA.read_bytes()
    if hashlib.sha256(content).hexdigest() != DATA_SHA: raise ValueError('Frozen regression set changed; use a new version.')
    dataset = json.loads(content)
    encoder = None
    if encoding_file:
        import tiktoken
        raw=Path(encoding_file).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=ENCODING_SHA: raise ValueError('Unexpected encoding data.')
        ranks={base64.b64decode(token):int(rank) for token,rank in (line.split() for line in raw.splitlines() if line)}
        encoder=tiktoken.Encoding(name='foundry-cl100k',pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s",mergeable_ranks=ranks,special_tokens={})
    rows=[]
    totals={key:0 for key in ['baseline','compact','unicode','brief']}
    for case in dataset['cases']:
        payload=case['payload']
        texts={'baseline':json.dumps(payload),'compact':json.dumps(payload,separators=(',',':')),
               'unicode':json.dumps(payload,separators=(',',':'),ensure_ascii=False),
               'brief':json.dumps(structured_brief(payload),separators=(',',':'),ensure_ascii=False)}
        for key in ['baseline','compact','unicode']: assert json.loads(texts[key])==payload
        assert json.loads(texts['brief'])['context']==payload
        counts={k:len(encoder.encode(CODE+v,disallowed_special=())) if encoder else len(CODE+v) for k,v in texts.items()}
        if encoder and counts['baseline']!=case['baseline_prompt_tokens_cl100k']:
            raise ValueError('Baseline prompt/encoding differs from frozen run.')
        for key,count in counts.items():totals[key]+=count
        rows.append({'id':case['id'],'origin':case['origin'],'counts':counts,'information_roundtrip':True,'first_attempt_repair_success':None})
    return {'schema':1,'dataset_sha256':DATA_SHA,'cases':len(rows),'metric':'cl100k_normalized_input_tokens' if encoder else 'characters',
            'tokenizer':'tiktoken 0.12.0 cl100k_base (framing excluded)' if encoder else None,
            'totals':totals,'semantic_roundtrips':len(rows),'live_model_requests':0,'first_attempt_repair_success':None,
            'billed_token_delta':None,'rows':rows,
            'limitations':'Transport-only paired replay. Exact decoded values retained; no repair candidates were generated or evaluated. No provider quality, latency or billed-cost claim.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--encoding-file');args=parser.parse_args()
    print(json.dumps(evaluate(args.encoding_file),indent=2))
