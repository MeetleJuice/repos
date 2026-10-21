"""Wire regressions for the Tiny Wins guided-planning failure; no live APIs."""
import json
import unittest
from unittest.mock import patch
from forge.capabilities import CapabilityRegistry
from forge.guided import OUTLINE_PROMPT, TASKS_PROMPT, OUTLINE_SCHEMA, BATCH_SCHEMA
from forge.models import ModelClient
from tests.test_guided_planning import responses


class GuidedWireContractTests(unittest.TestCase):
    def test_every_adapter_receives_the_stage_schema_even_without_native_json(self):
        for provider in ('gemini','groq','openrouter','cloudflare','nvidia','requesty','huggingface','ollama','local'):
            for system,schema,response in ((OUTLINE_PROMPT,OUTLINE_SCHEMA,responses()[0]),(TASKS_PROMPT,BATCH_SCHEMA,responses()[1])):
                for structured in (False,True):
                    with self.subTest(provider=provider,stage=schema['required'],structured=structured):
                        client=ModelClient(provider,'fixture',{'num_ctx':32768,'num_predict':8192,'structured_outputs':structured})
                        client.planner_budget=CapabilityRegistry().reserve(provider,'fixture',client.options,system,'{}')
                        result={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response)}}]}
                        if provider=='gemini':result={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(response)}]}}]}
                        if provider=='ollama':result={'done':True,'message':{'content':json.dumps(response)}}
                        with patch('forge.models.key_for',return_value='fixture'),patch('forge.models.endpoint',return_value='http://127.0.0.1:1234/v1'),patch('forge.models.request_json',return_value=result) as wire:
                            self.assertEqual(client.complete(system,'{}'),response)
                        payload=wire.call_args.args[1]
                        text=payload['systemInstruction']['parts'][0]['text'] if provider=='gemini' else payload['messages'][0]['content']
                        self.assertIn('STAGE OUTPUT SCHEMA:',text)
                        actual=json.loads(text.split('STAGE OUTPUT SCHEMA:',1)[1].split('\n',1)[0])
                        self.assertEqual(actual,schema)
                        if system==OUTLINE_PROMPT:
                            self.assertEqual(actual['properties']['app_kind']['enum'],['server','browser'])
                            self.assertEqual(actual['properties']['manual_checks']['items']['required'],['name','steps','expected','feature_indexes'])
                            self.assertIn('name',actual['properties']['checks']['items']['required'])
                        self.assertGreaterEqual(client.planner_budget.max_output_tokens,8192)

    def test_local_reservation_includes_both_prompt_and_native_schema(self):
        registry=CapabilityRegistry();options={'num_ctx':32768,'num_predict':8192,'structured_outputs':True}
        native=registry.reserve('ollama','fixture',options,OUTLINE_PROMPT,'{}')
        plain=registry.reserve('ollama','fixture',{**options,'structured_outputs':False},OUTLINE_PROMPT,'{}')
        self.assertGreaterEqual(native.input_estimate_tokens-plain.input_estimate_tokens,len(json.dumps(OUTLINE_SCHEMA))//2)


if __name__=='__main__':unittest.main()
