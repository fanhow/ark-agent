#!/usr/bin/env python3
"""Scheduled cloud fetch -> explicitly public market-only snapshot; no portfolio data."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import ROOT, DATA, atomic, today
from research import generate, validate_brief

def publish(brief):
 validate_brief(brief)
 allowed=['date','generatedAt','headline','stance','market','macroRadar','macro','recap','radio','board','lenses','sources','calendar','status','note','gaps','aiGenerated']
 public={k:brief[k] for k in allowed if k in brief}
 target=ROOT/'public/briefs';atomic(target/(brief['date']+'.json'),public)
 index=[]
 for p in sorted(target.glob('????-??-??.json'),reverse=True):
  item=json.loads(p.read_text());index.append({k:item[k] for k in ['date','headline','generatedAt']})
 atomic(target/'index.json',index)
 return public
if __name__=='__main__':
 result=generate(scheduled=True)
 if result.get('status')=='blocked':raise SystemExit('交易日曆不可核實，保留前次網站資料')
 if result.get('status')=='skipped':print('官方休市，未新增日報')
 else:
  result=publish(result);print(json.dumps({'date':result['date'],'status':result['status'],'aiGenerated':result['aiGenerated']},ensure_ascii=False))
