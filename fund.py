"""Validate private imported fund snapshots; never infer missing financial values."""
from core import valid_date, number
from datetime import datetime
from urllib.parse import urlparse

FIELDS=('totalAssets','stockMarketValue','stockCost','fundPnl','holdingsPnl','dailyPnl','taiwanPnl','usPnl')
def timestamp(v):
    if not isinstance(v,str) or 'T' not in v or datetime.fromisoformat(v.replace('Z','+00:00')).tzinfo is None:raise ValueError('基金時間須含時區')
def validate_fund(f):
    if not isinstance(f,dict) or f.get('version')!=1 or f.get('currency')!='TWD' or not isinstance(f.get('name'),str) or len(f['name'])>100:raise ValueError('基金格式無效')
    source=f.get('source',{})
    for k in ('title','url','sheet'):
        if not isinstance(source.get(k),str) or len(source[k])>2000:raise ValueError('基金來源無效')
    url=urlparse(source['url'])
    if url.scheme!='https' or url.hostname!='docs.google.com' or not url.path.startswith('/spreadsheets/d/'):raise ValueError('基金來源無效')
    timestamp(source.get('modifiedAt'));timestamp(source.get('importedAt'))
    if 'live' in source and not isinstance(source['live'],bool):raise ValueError('基金自動更新設定無效')
    rows=f.get('records')
    if not isinstance(rows,list) or not 1<=len(rows)<=5000:raise ValueError('基金明細筆數無效')
    dates=set()
    for row in rows:
        if 'updatedAt' in row:timestamp(row['updatedAt'])
        date=valid_date(row.get('date'))
        if date in dates:raise ValueError('基金日期重複')
        dates.add(date)
        for k in FIELDS:
            if k not in row:raise ValueError('基金明細缺少欄位')
            number(row[k],k)
        for k in ('screenshots','notes'):
            if not isinstance(row.get(k),str) or len(row[k])>20000:raise ValueError('基金明細註記無效')
    capital=f.get('capital',{})
    initial=number(capital.get('initial'))
    if initial is None or initial<0:raise ValueError('本金格式無效')
    timestamp(capital.get('confirmedAt'))
    events=capital.get('events')
    if not isinstance(events,list) or len(events)>1000:raise ValueError('入出金格式無效')
    for event in events:
        valid_date(event.get('date'))
        if number(event.get('amount')) is None or not isinstance(event.get('note'),str) or len(event['note'])>2000:raise ValueError('入出金格式無效')
    if not isinstance(f.get('notes'),list) or len(f['notes'])>100 or any(not isinstance(n,str) or len(n)>5000 for n in f['notes']):raise ValueError('基金註記無效')
    return f
