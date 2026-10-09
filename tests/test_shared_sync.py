import copy, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import shared_sync as sync
from core import parse_csv, commit_import, validate_portfolio
SAMPLE={'asOf':'2026-10-08','day':4,'totalPnl':None,'cumulativePnl':1200,'positions':[{'code':'TEST','name':'Test','shares':1,'ret':0,'pnl':0,'value':10,'note':''}],'rules':{'p1':-15,'p3':-8,'p2':5},'note':''}
class SyncTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name);self.portfolio=self.data/'portfolio.json';self.portfolio.write_text(json.dumps(SAMPLE))
  self.patches=[patch.object(sync,'DATA',self.data),patch.object(sync,'STATE',self.data/'shared-sync.json'),patch.object(sync,'settings',return_value={}),patch.object(sync,'configured',return_value=True)]
  for p in self.patches:p.start()
  self.cloud={'key':'portfolio','revision':0,'value':None};self.writes=0;self.fail_after_write=False
 def tearDown(self):
  for p in self.patches:p.stop()
  self.temp.cleanup()
 def transport(self,key,body=None):
  if key=='manifest':return {'documents':[{'key':'portfolio','revision':self.cloud['revision']}] if self.cloud['revision'] else []}
  if body:
   if body['baseRevision']!=self.cloud['revision']:raise sync.SyncError('conflict')
   self.cloud.update(revision=self.cloud['revision']+1,value=copy.deepcopy(body['value']),requestId=body['requestId']);self.writes+=1
   if self.fail_after_write:self.fail_after_write=False;raise sync.SyncError('offline after commit')
  return copy.deepcopy(self.cloud)
 def test_publish_readback_and_no_repeated_writes(self):
  self.assertEqual(sync.sync_once(self.transport)['changed'],1);self.assertEqual(sync.public_status()['pending'],0)
  sync.sync_once(self.transport);self.assertEqual(self.writes,1);self.assertEqual(self.cloud['value']['cumulativePnl'],1200)
 def test_lost_response_recovers_then_newer_local_data(self):
  self.fail_after_write=True;self.assertEqual(sync.sync_once(self.transport)['status'],'error')
  new={**SAMPLE,'cumulativePnl':-450};self.portfolio.write_text(json.dumps(new));self.assertEqual(sync.sync_once(self.transport)['status'],'synced');self.assertEqual(self.cloud['revision'],2);self.assertEqual(self.cloud['value']['cumulativePnl'],-450)
 def test_initial_cloud_conflict_keeps_both(self):
  self.cloud.update(revision=5,value={**SAMPLE,'cumulativePnl':555})
  before=self.portfolio.read_bytes();self.assertEqual(sync.sync_once(self.transport)['status'],'error');self.assertEqual(self.portfolio.read_bytes(),before);self.assertEqual(self.writes,0)
 def test_equivalent_integer_float_readback(self):
  self.assertEqual(sync.digest({'a':1.0}),sync.digest({'a':1}))
 def test_cumulative_import_separate_zero_null_negative_and_summary(self):
  parsed=parse_csv('代號,名稱,日期,累積損益（台幣）,總未實現損益\nTEST,Test,2026-10-08,-450,\n');self.assertEqual(parsed['cumulativePnl'],-450);self.assertIsNone(parsed['totalPnl'])
  for value in [0,-300,None]:
   result=commit_import(SAMPLE,{'asOf':'2026-10-08','totalPnl':None,'cumulativePnl':value,'positions':SAMPLE['positions']},'merge');self.assertEqual(result['cumulativePnl'],1200 if value is None else value)
  result=commit_import(SAMPLE,{'asOf':'2026-10-08','cumulativePnl':0,'positions':[]},'merge');self.assertEqual(result['positions'],SAMPLE['positions'])
  with self.assertRaises(ValueError):commit_import(SAMPLE,{'asOf':'2026-10-08','cumulativePnl':0,'positions':[]},'replace')
  with self.assertRaises(ValueError):validate_portfolio({**SAMPLE,'cumulativePnl':True})

 def test_cloud_edit_pulls_only_when_local_unchanged(self):
  sync.sync_once(self.transport)
  self.cloud.update(revision=2,value={**self.cloud['value'],'cumulativePnl':999,'updatedAt':'2026-10-09T12:00:00Z'},requestId='other-writer')
  self.assertEqual(sync.sync_once(self.transport)['status'],'synced');self.assertEqual(json.loads(self.portfolio.read_text())['cumulativePnl'],999)
  current=json.loads(self.portfolio.read_text());current['cumulativePnl']=123;self.portfolio.write_text(json.dumps(current));self.cloud.update(revision=3,value={**self.cloud['value'],'cumulativePnl':456},requestId='third-writer')
  self.assertEqual(sync.sync_once(self.transport)['status'],'error');self.assertEqual(json.loads(self.portfolio.read_text())['cumulativePnl'],123);self.assertEqual(self.cloud['value']['cumulativePnl'],456)

 def test_pull_rechecks_local_edit_during_network_read(self):
  sync.sync_once(self.transport)
  self.cloud.update(revision=2,value={**self.cloud['value'],'cumulativePnl':999},requestId='other-writer')
  def racing_transport(key,body=None):
   if key=='portfolio' and body is None:self.portfolio.write_text(json.dumps({**SAMPLE,'cumulativePnl':777}))
   return self.transport(key,body)
  self.assertEqual(sync.sync_once(racing_transport)['status'],'error')
  self.assertEqual(json.loads(self.portfolio.read_text())['cumulativePnl'],777)
