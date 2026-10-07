import base64, copy, json, os, sys, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,server,research
from core import *

class CoreTests(unittest.TestCase):
 def setUp(self):self.p=read(ROOT/'data/portfolio.initial.json')
 def test_initial_exact(self):
  self.assertEqual((self.p['asOf'],self.p['day'],self.p['totalPnl'],len(self.p['positions'])),('2026-09-30',339,-5024,18))
  p=next(x for x in self.p['positions'] if x['code']=='0056');self.assertIsNone(p['ret']);self.assertEqual(p['pnl'],0)
 def test_mutually_exclusive_thresholds(self):
  self.assertEqual([group({'ret':v},self.p['rules']) for v in [-20,-15,-14,-8,-7,0,5,8,None]],['P1','P1','P3','P3','正常持有','正常持有','P2','P2','待更新'])
 def test_unknown_is_not_zero(self):
  self.assertIsNone(parse_num(''));self.assertEqual(parse_num('0'),0);self.assertEqual(parse_num('(1,234)'),-1234);self.assertEqual(parse_num('-22.73%'),-22.73)
 def test_big5_csv(self):
  s='股票代號,股票名稱,報酬率,未實現損益,日期\n0056,元大高股息,,0,2026/10/08\n00910,第一金太空衛星,-22.73,-4422,2026/10/08'
  text,enc=decode_text(s.encode('big5'));self.assertEqual(enc,'big5');r=parse_csv(text)
  self.assertEqual(r['asOf'],'2026-10-08');self.assertEqual(r['positions'][0]['name'],'元大高股息');self.assertIsNone(r['positions'][0]['ret']);self.assertIsNone(r['totalPnl'])
 def test_csv_duplicate_non_null(self):
  r=parse_csv('code,name,ret,pnl\n0056,元大高股息,5,\n0056,,,-123')
  self.assertEqual(len(r['positions']),1);self.assertEqual(r['positions'][0]['ret'],5);self.assertEqual(r['positions'][0]['pnl'],-123)
 def test_reject_csv_mixed_dates(self):
  with self.assertRaises(ValueError):parse_csv('code,asOf\n0056,2026-10-08\n0050,2026-10-07')
 def test_merge_and_replace(self):
  inc={'asOf':'2026-10-08','totalPnl':None,'positions':[{'code':'0056','name':'元大高股息','ret':7,'pnl':None}]}
  merged=commit_import(self.p,inc,'merge');self.assertEqual(len(merged['positions']),18);self.assertEqual(merged['day'],340);self.assertEqual(merged['totalPnl'],-5024)
  p=next(x for x in merged['positions'] if x['code']=='0056');self.assertEqual(p['pnl'],0);self.assertEqual(p['ret'],7)
  replaced=commit_import(self.p,inc,'replace');self.assertEqual(len(replaced['positions']),1);self.assertIsNone(replaced['totalPnl'])
 def test_same_date_no_day_change(self):
  p=commit_import(self.p,{'asOf':'2026-09-30','positions':self.p['positions']},'merge');self.assertEqual(p['day'],339)
 def test_older_needs_explicit_choice_preserves_day(self):
  inc={'asOf':'2026-09-29','positions':self.p['positions']}
  with self.assertRaises(ValueError):commit_import(self.p,inc,'merge')
  self.assertEqual(commit_import(self.p,inc,'merge','accept')['day'],339)
 def test_missing_date_blocked(self):
  with self.assertRaises(ValueError):commit_import(self.p,{'asOf':None,'positions':self.p['positions']},'merge')
 def test_invalid_numeric_and_rules(self):
  for v in [float('nan'),float('inf'),True,'1']:
   with self.assertRaises(ValueError):number(v)
  self.p['rules']={'p1':5,'p3':-8,'p2':5}
  with self.assertRaises(ValueError):validate_portfolio(self.p)
 def test_ics_converts_dst_and_week(self):
  text='BEGIN:VEVENT\nSUMMARY:Consumer Price Index\nDTSTART:20261008T123000Z\nEND:VEVENT'
  r=research.parse_ics(text,'2026-10-08','https://example.test');self.assertEqual(r[0]['time'],'2026-10-08T20:30+08:00');self.assertIsNone(r[0]['consensus'])
 def test_calendar_open_close_and_unavailable(self):
  data=read(ROOT/'tests/fixtures/calendar-2026.json')['data']
  with patch('research.fetch',return_value=json.dumps(data)),patch('research.atomic'):
   self.assertTrue(research.calendar('2026-10-08')['isTradingDay']);self.assertFalse(research.calendar('2026-10-09')['isTradingDay']);self.assertTrue(research.calendar('2026-02-11')['isTradingDay']);self.assertFalse(research.calendar('2026-02-12')['isTradingDay'])
  with patch('research.fetch',side_effect=ValueError('offline')):self.assertIsNone(research.calendar('2026-10-08')['isTradingDay'])
 def test_scheduled_closed_does_not_generate(self):
  with patch('research.calendar',return_value={'isTradingDay':False}),patch('research.atomic') as store:
   result=research.generate('2026-10-09',True);self.assertEqual(result['status'],'skipped');self.assertEqual(store.call_count,1)

class APITests(unittest.TestCase):
 def setUp(self):
  isolated=patch.dict(os.environ,{'AI_PROVIDER':'','OPENAI_API_KEY':'','ANTHROPIC_API_KEY':''})
  isolated.start();self.addCleanup(isolated.stop)
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.dir=Path(cls.tmp.name);cls.oldcore=core.DATA;cls.oldserver=server.DATA
  core.DATA=server.DATA=cls.dir
  for d in ['briefs','journal','avatars','uploads','history','cache']:(cls.dir/d).mkdir()
  atomic(cls.dir/'portfolio.json',read(ROOT/'data/portfolio.initial.json'))
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();core.DATA=cls.oldcore;server.DATA=cls.oldserver;cls.tmp.cleanup()
 def request(self,path,obj=None,method='POST',headers=None):
  h={'Content-Type':'application/json','X-Ark-Token':server.TOKEN};h.update(headers or {});r=urllib.request.Request(self.url+path,data=json.dumps(obj).encode() if obj is not None else None,headers=h,method=method if obj is not None else 'GET')
  try:
   with urllib.request.urlopen(r) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as e:
   with e:return e.code,json.load(e)
 def test_status_no_secrets(self):
  with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'test-secret-only'}):
   status,r=self.request('/api/status');self.assertTrue(r['aiConfigured']);self.assertNotIn('test-secret-only',json.dumps(r))
 def test_private_files_not_served(self):
  for path in ['/server.py','/data/portfolio.json','/.env','/data/uploads/a','/../core.py']:self.assertEqual(self.request(path)[0],404)
 def test_cross_origin_and_csrf_blocked(self):
  self.assertEqual(self.request('/api/portfolio',{},'PUT',{'Origin':'https://evil.example'})[0],403)
  self.assertEqual(self.request('/api/portfolio',{},'PUT',{'X-Ark-Token':'wrong'})[0],403)
  self.assertEqual(self.request('/api/status',headers={'Host':'evil.example'})[0],403)
 def test_no_key_ai_503(self):
  with patch.dict(os.environ,{'ANTHROPIC_API_KEY':''}):self.assertEqual(self.request('/api/ask',{'prompt':'test'})[0],503)
 def test_big5_upload_preview_images_dedup(self):
  text='代號,名稱,報酬率,未實現損益,日期\n0056,元大高股息,,0,2026-10-08';csvfile={'name':'對帳單.csv','data':base64.b64encode(text.encode('big5')).decode()}
  _,f=self.request('/api/uploads',csvfile);self.assertEqual(f['encoding'],'big5');self.assertIn('元大高股息',f['text'])
  raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZioAAAAASUVORK5CYII=')
  _,a=self.request('/api/uploads',{'name':'test.png','data':base64.b64encode(raw).decode()});_,b=self.request('/api/uploads',{'name':'copy.png','data':base64.b64encode(raw).decode()});self.assertEqual(a['id'],b['id'])
  fixture=json.dumps({'asOf':'2026-10-08','totalPnl':None,'positions':[{'code':'0050','name':'測試股票','ret':3.5}]})
  with patch('server.ai.configured',return_value=True),patch('server.ai.call',return_value=fixture) as mock:
   status,r=self.request('/api/import/preview',{'files':[f['id'],a['id'],b['id']]});self.assertEqual(status,200);self.assertEqual(len(r['positions']),2);self.assertEqual(len(mock.call_args.args[1]),1)
  with patch('server.ai.configured',return_value=False):self.assertEqual(self.request('/api/import/preview',{'files':[a['id']]})[0],400)
 def test_commit_optimistic_check(self):
  p=read(self.dir/'portfolio.json');self.assertEqual(self.request('/api/import/commit',{'baseUpdatedAt':'outdated','mode':'merge','preview':p})[0],409)
 def test_previous_skips_same_and_future_dates(self):
  current=read(self.dir/'portfolio.json')
  for name,d in [('200001','2026-09-29'),('200002','2026-09-30'),('200003','2026-10-01')]:atomic(self.dir/'history'/f'{name}.json',{**current,'asOf':d})
  self.assertEqual(self.request('/api/portfolio/previous')[1]['asOf'],'2026-09-29')
 def test_journal_saved_readable(self):
  j={'day':339,'text':'測試用 **文章**。這不是運氣，是紀律的回報。','totalPnl':-5024};self.assertEqual(self.request('/api/journal/2026-09-30',j,'PUT')[0],200);self.assertIn('測試用',self.request('/api/journal')[1][0]['text'])
 def test_avatar_reject_non_jpeg(self):self.assertEqual(self.request('/api/avatars',{'id':'buffett','data':base64.b64encode(b'invalid').decode()})[0],400)
 def test_stream_proxy_mock_contract(self):
  import io
  body=b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hello"}}\n\ndata: {"type":"message_stop"}\n\n'
  with patch('server.ai.configured',return_value=True),patch('server.ai.call',return_value=io.BytesIO(body)):
   req=urllib.request.Request(self.url+'/api/ask',data=b'{"prompt":"test","stream":true}',headers={'Content-Type':'application/json','X-Ark-Token':server.TOKEN})
   with urllib.request.urlopen(req) as r:s=r.read().decode()
   self.assertIn('event: delta',s);self.assertIn('event: done',s)

if __name__=='__main__':unittest.main(verbosity=2)
