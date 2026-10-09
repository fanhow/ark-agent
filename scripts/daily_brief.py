#!/usr/bin/env python3
import argparse,json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research import generate
from core import DATA, now
p=argparse.ArgumentParser(description='方舟每日真實來源擷取（Asia/Taipei）')
p.add_argument('--date',help='YYYY-MM-DD；未指定使用台北今天')
p.add_argument('--scheduled',action='store_true',help='僅官方核實交易日才寫 brief')
p.add_argument('--notify',action='store_true',help='嘗試 macOS 本機通知')
a=p.parse_args()
try:
 result=generate(a.date,a.scheduled)
 if 'headline' in result:
  from shared_sync import sync_once
  sync_result=sync_once()
  if sync_result.get('status')=='error':print(json.dumps({'sharedSync':sync_result},ensure_ascii=False))
  print(json.dumps({'status':result['status'],'date':result['date'],'headline':result['headline'],'aiGenerated':result['aiGenerated'],'path':str(DATA/'briefs'/f'{result["date"]}.json'),'gaps':result['gaps']},ensure_ascii=False,indent=2))
  if a.notify and sys.platform=='darwin':
   message=result['headline']+' 完整資料與大師視角狀態已更新到方舟智慧體網頁。'
   for event in result['macro'][:3]:message+=' '+event['time']+' '+event['title']
   script='on run argv\ndisplay notification (item 1 of argv) with title "方舟智慧體"\nend run'
   done=subprocess.run(['osascript','-e',script,message],capture_output=True,text=True)
   print('通知指令已送出（實際顯示依系統權限）' if done.returncode==0 else '通知不支援；結果仍已存檔')
 else:print(json.dumps(result,ensure_ascii=False,indent=2))
except Exception as e:
 print('寫入或研究失敗：'+str(e),file=sys.stderr);sys.exit(1)
