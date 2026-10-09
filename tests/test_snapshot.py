import unittest,copy
from core import *
class SnapshotTests(unittest.TestCase):
 def test_summary_and_partial_updates(self):
  p=read(ROOT/'data/portfolio.initial.json'); vals=dict(zip(ACCOUNT_FIELDS,[-7,-.64,15,4.05,100,90,200,0,0]))
  x=commit_import(p,{'asOf':p['asOf'],'positions':[],**vals},'merge')
  self.assertEqual(x['positions'],validate_portfolio(p)['positions']);self.assertEqual(x['accountSnapshot']['values'],vals)
  self.assertNotEqual(x['cumulativePnl'],vals['stockMarketValue']-vals['stockCost'])
  y=commit_import(x,{'asOf':'2026-10-08','positions':[{'code':'0056','pnl':2}]},'merge')
  self.assertEqual(y['accountSnapshot'],x['accountSnapshot'])
  z=commit_import(y,{'asOf':'2026-10-08','positions':[],'dailyPnl':0},'merge')
  self.assertEqual(z['accountSnapshot']['values']['dailyPnl'],0);self.assertIsNone(z['accountSnapshot']['values']['cumulativePnl'])
  for val in ['1',True,float('nan')]:
   bad=copy.deepcopy(z);bad['accountSnapshot']['values']['dailyPnl']=val
   with self.assertRaises(ValueError):validate_portfolio(bad)
 def test_conflicting_photos_reject(self):
  with self.assertRaises(ValueError):merge_account({'dailyPnl':1},{'dailyPnl':2})
