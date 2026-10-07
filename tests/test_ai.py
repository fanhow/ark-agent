import io,json,os,unittest
from unittest.mock import patch
import ai

class OpenAITests(unittest.TestCase):
 def test_openai_payload_and_output(self):
  answer={'status':'completed','output':[{'content':[{'type':'output_text','text':'已連線'}]}]}
  response=io.BytesIO(json.dumps(answer).encode())
  with patch.dict(os.environ,{'AI_PROVIDER':'openai','OPENAI_API_KEY':'test-only'},clear=True),patch('ai.urllib.request.urlopen',return_value=response) as call:
   self.assertEqual(ai.call('輸出 JSON',json_mode=True),'已連線')
   req=call.call_args.args[0];payload=json.loads(req.data)
   self.assertEqual(req.full_url,'https://api.openai.com/v1/responses');self.assertFalse(payload['store']);self.assertEqual(payload['text']['format']['type'],'json_object')
 def test_openai_completed_stream(self):
  events=[{'type':'response.output_text.delta','delta':'繁體中文'},{'type':'response.completed','response':{'status':'completed'}}]
  self.assertEqual(list(ai.deltas(io.BytesIO(b''.join(b'data: '+json.dumps(e).encode()+b'\n\n' for e in events)))),['繁體中文'])
 def test_openai_incomplete_or_missing_completion(self):
  for events in [[{'type':'response.incomplete'}],[{'type':'response.completed','response':{'status':'incomplete'}}],[{'type':'response.output_text.delta','delta':'partial'}]]:
   with self.assertRaises(ValueError):list(ai.deltas(io.BytesIO(b''.join(b'data: '+json.dumps(e).encode()+b'\n\n' for e in events))))
 def test_selected_provider_does_not_silently_fallback(self):
  with patch.dict(os.environ,{'AI_PROVIDER':'openai','ANTHROPIC_API_KEY':'test-only'},clear=True):self.assertFalse(ai.configured())
 def test_openai_auto_selection_and_anthropic_compatibility(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'},clear=True):self.assertEqual(ai.provider(),'openai')
  with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'test-only'},clear=True):self.assertEqual(ai.provider(),'anthropic');self.assertTrue(ai.configured())
