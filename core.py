"""資料驗證、庫存合併與無金鑰 CSV 匯入。Python 3.11+，僅標準函式庫。"""
from __future__ import annotations
import csv, io, json, math, os, re, tempfile, threading
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('ARK_DATA_DIR', ROOT / 'data')).resolve()
TZ = ZoneInfo('Asia/Taipei')
LOCK = threading.RLock()
IDS = ['buffett','marks','dalio','druckenmiller','wood','huang','wei','nadella']
FIELDS = ['code','name','shares','ret','pnl','value','note']

def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def today(): return datetime.now(TZ).date().isoformat()
def atomic(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def read(path, default=None):
    p=Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def valid_date(v, nullable=False):
    if v is None and nullable: return None
    if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v): raise ValueError('日期須為 YYYY-MM-DD')
    date.fromisoformat(v); return v

def number(v, label='數值'):
    if v is None: return None
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError(f'{label} 必須為有限數值或 null')
    return v

def position(p):
    if not isinstance(p,dict): raise ValueError('持股格式錯誤')
    code=str(p.get('code','')).strip().upper()
    if not re.fullmatch(r'[A-Z0-9.^-]{1,20}',code): raise ValueError('股票代號不可空白且只能使用英文、數字、.、^、-')
    name=p.get('name') or ''
    if not isinstance(name,str) or len(name)>160: raise ValueError('名稱格式錯誤')
    out={'code':code,'name':name}
    for k in ['shares','ret','pnl','value']: out[k]=number(p.get(k), k)
    if out['shares'] is not None and out['shares']<0: raise ValueError('持有數量不可為負')
    if out['value'] is not None and out['value']<0: raise ValueError('市值不可為負')
    out['note']=str(p.get('note') or '')[:4000]
    missing=[k for k in ['shares','ret','pnl','value'] if out[k] is None]
    if missing and not out['note']: out['note']='未提供欄位：'+', '.join(missing)
    return out

def merge_positions(old,new):
    merged={p['code']:dict(p) for p in old}
    for p in new:
        if p['code'] not in merged: merged[p['code']]=dict(p)
        else:
            for k,v in p.items():
                if v is not None and v!='': merged[p['code']][k]=v
    return list(merged.values())

def validate_portfolio(p):
    out={'asOf':valid_date(p.get('asOf'),True),'day':p.get('day'),'totalPnl':number(p.get('totalPnl')),'note':str(p.get('note') or ''),'rules':p.get('rules'),'updatedAt':p.get('updatedAt'),'positions':[]}
    if isinstance(out['day'],bool) or not isinstance(out['day'],int) or out['day']<0: raise ValueError('Day 必須是非負整數')
    r=out['rules']
    if not isinstance(r,dict) or any(k not in r or number(r[k]) is None for k in ['p1','p3','p2']): raise ValueError('水位規則不完整')
    if not r['p1']<r['p3']<r['p2']: raise ValueError('請維持 P1 < P3 < P2，避免規則衝突')
    if not isinstance(p.get('positions'),list) or len(p['positions'])>500: raise ValueError('持股必須為陣列且最多 500 檔')
    out['positions']=[position(x) for x in p['positions']]
    if len({x['code'] for x in out['positions']})!=len(out['positions']): raise ValueError('持股代號重複')
    return out

def group(p,r):
    v=p['ret']
    return '待更新' if v is None else 'P1' if v<=r['p1'] else 'P3' if v<=r['p3'] else 'P2' if v>=r['p2'] else '正常持有'

def save_portfolio(p):
    p=validate_portfolio(p)
    with LOCK:
        old=read(DATA/'portfolio.json')
        if old: atomic(DATA/'history'/f'{datetime.now(TZ).strftime("%Y%m%dT%H%M%S%f")}.json',old)
        p['updatedAt']=now(); atomic(DATA/'portfolio.json',p)
    return p

def commit_import(current, incoming, mode, older=None):
    if mode not in ['merge','replace']: raise ValueError('請選擇完整取代或局部更新')
    d=valid_date(incoming.get('asOf'),True)
    if not d: raise ValueError('請確認資料日期後再更新')
    if current['asOf'] and d<current['asOf'] and older!='accept': raise ValueError('日期較舊：須在預覽明確選擇接受，否則保留目前資料與 Day')
    ps=[position(x) for x in incoming.get('positions',[])]
    if not ps: raise ValueError('沒有可更新的持股')
    out=dict(current)
    out['positions']=merge_positions(current['positions'],ps) if mode=='merge' else merge_positions([],ps)
    out['asOf']=d
    out['day']=current['day']+(1 if current['asOf'] and d>current['asOf'] else 0)
    out['totalPnl']=number(incoming.get('totalPnl'))
    out['note']='使用者已確認匯入；'+str(incoming.get('note') or '')
    if mode=='merge' and out['totalPnl'] is None:
        out['totalPnl']=current['totalPnl']
        out['note']+=f'；總損益沿用 {current["asOf"]}，未由部分持股補算，待核對。'
    if current['asOf'] and d<current['asOf']: out['note']+='；明確接受較舊日期，保留 Day 不遞增。'
    return validate_portfolio(out)

ALIASES={
 'code':['code','代號','股票代號','證券代號','商品代號'], 'name':['name','名稱','股票名稱','證券名稱','商品名稱'],
 'shares':['shares','股數','庫存股數','持有數量','數量'], 'ret':['ret','報酬率','報酬率(%)','報酬率％','報酬率%','損益率','損益率(%)'],
 'pnl':['pnl','損益','未實現損益','預估損益'], 'value':['value','市值','現值','參考市值'],
 'asOf':['asOf','日期','資料日期','對帳日期'], 'totalPnl':['totalPnl','總損益','總未實現損益'], 'note':['note','備註']}
def parse_num(s):
    s=str(s or '').strip().replace(',','').replace('，','').replace('%','').replace('％','').replace('−','-')
    if s in ['', '-', '--', 'N/A', 'null','待更新']: return None
    if s.startswith('(') and s.endswith(')'): s='-'+s[1:-1]
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)',s): raise ValueError('無法辨識數值：'+s[:40])
    return number(float(s))
def decode_text(b):
    for enc in ['utf-8-sig','big5','cp950']:
        try: return b.decode(enc),enc
        except UnicodeDecodeError: pass
    raise ValueError('無法以 UTF-8 或 Big5 解碼，請另存 CSV UTF-8')
def parse_csv(text):
    lines=text.strip().splitlines()
    if not lines: return {'asOf':None,'totalPnl':None,'positions':[],'note':'無文字資料'}
    header=next((i for i,l in enumerate(lines) if any(a in l for a in ALIASES['code'])),None)
    if header is None: return {'asOf':None,'totalPnl':None,'positions':[],'note':'未找到標準代號欄，需使用 AI 辨識或手動編輯'}
    part='\n'.join(lines[header:]); delim='\t' if '\t' in lines[header] else ','
    rows=csv.DictReader(io.StringIO(part),delimiter=delim)
    mapping={k:next((h for h in (rows.fieldnames or []) if h.strip().lstrip('\ufeff') in a),None) for k,a in ALIASES.items()}
    out={'asOf':None,'totalPnl':None,'positions':[],'note':'標準欄位直接擷取；未推算缺值。ret 採百分比數值。'}
    for i,row in enumerate(rows,header+2):
        vals={k:row.get(h,'') if h else '' for k,h in mapping.items()}
        d=vals.get('asOf','').strip()
        if d:
            d=d.replace('/','-'); parts=d.split('-')
            if len(parts)==3 and all(s.isdigit() for s in parts):
                y,m,dy=map(int,parts); d=f'{y+1911 if y<1911 else y:04d}-{m:02d}-{dy:02d}'
            d=valid_date(d)
            if out['asOf'] and out['asOf']!=d: raise ValueError('同一檔案含不同日期，請拆開匯入')
            out['asOf']=d
        if vals.get('totalPnl','').strip(): out['totalPnl']=parse_num(vals['totalPnl'])
        code=vals['code'].strip().strip("'\"")
        if not code: continue
        if code in ['合計','總計','TOTAL']:
            if vals['pnl'].strip():out['totalPnl']=parse_num(vals['pnl'])
            continue
        p={'code':code,'name':vals['name'],'note':vals.get('note','')}
        for k in ['shares','ret','pnl','value']: p[k]=parse_num(vals[k])
        out['positions']=merge_positions(out['positions'],[position(p)])
    return out
