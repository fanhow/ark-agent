import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fund import validate_fund
import shared_sync as sync

def fixture():
 return {'version':1,'name':'Test','currency':'TWD','source':{'title':'Test','sheet':'每日績效','url':'https://docs.google.com/spreadsheets/d/fixture/edit','modifiedAt':'2026-01-04T00:00:00Z','importedAt':'2026-01-05T00:00:00Z'},'records':[dict(date='2026-01-03',totalAssets=1500,stockMarketValue=600,stockCost=550,fundPnl=100,holdingsPnl=50,dailyPnl=0,taiwanPnl=30,usPnl=None,screenshots='test.png',notes='')],'capital':{'initial':1000,'events':[{'date':'2026-01-02','amount':500,'note':'Fixture'}],'confirmedAt':'2026-01-04T00:00:00Z'},'notes':[]}
class FundTests(unittest.TestCase):
 def test_validation_preserves_null_zero_and_rejects_bad_source(self):
  f=fixture();self.assertEqual(validate_fund(f),f)
  for key,value in [('dailyPnl',float('nan')),('totalAssets',True),('date','2026-02-30')]:
   f=fixture();f['records'][0][key]=value
   with self.assertRaises(ValueError):validate_fund(f)
  f=fixture();f['records'].append(copy.deepcopy(f['records'][0]))
  with self.assertRaises(ValueError):validate_fund(f)
 def test_shared_fund_publish_pull_and_conflict_are_isolated(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);path=data/'fund.json';path.write_text(json.dumps(fixture()));cloud={'key':'fund:stable500','revision':0,'value':None}
   def transport(key,body=None):
    if key=='manifest':return {'documents':[{'key':'fund:stable500','revision':cloud['revision']}] if cloud['revision'] else []}
    if body:
     self.assertEqual(body['baseRevision'],cloud['revision']);cloud.update(revision=cloud['revision']+1,value=copy.deepcopy(body['value']),requestId=body['requestId'])
    return copy.deepcopy(cloud)
   with patch.object(sync,'DATA',data),patch.object(sync,'STATE',data/'state.json'),patch.object(sync,'settings',return_value={}),patch.object(sync,'configured',return_value=True):
    self.assertEqual(sync.sync_once(transport)['changed'],1);self.assertEqual(sync.sync_once(transport)['changed'],0)
    cloud['value']['records'][0]['dailyPnl']=-5;cloud['revision']=2
    self.assertEqual(sync.sync_once(transport)['changed'],1);self.assertEqual(json.loads(path.read_text())['records'][0]['dailyPnl'],-5)
    local=json.loads(path.read_text());local['records'][0]['dailyPnl']=10;path.write_text(json.dumps(local));cloud['revision']=3
    self.assertEqual(sync.sync_once(transport)['status'],'error');self.assertEqual(json.loads(path.read_text())['records'][0]['dailyPnl'],10)
