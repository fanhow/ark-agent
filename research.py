"""可重跑的真實來源擷取；所有失敗與資料日期皆保留，不以 AI 代替上網。"""
from __future__ import annotations
import concurrent.futures, csv, html, io, json, re, urllib.request
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
from core import DATA, ROOT, TZ, now, today, atomic, read, valid_date
import ai
UA='Mozilla/5.0 (compatible; ArkLocalResearch/1.0)'

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/csv,text/html,application/rss+xml,*/*'})
    with urllib.request.urlopen(request,context=ai.context(),timeout=22) as r:
        b=r.read(5_000_001)
        if len(b)>5_000_000: raise ValueError('來源超過讀取上限')
        return b.decode('utf-8-sig')

def calendar(day):
    d=datetime.fromisoformat(day).date(); u=f'https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear={d.year-1911}'
    try:
        raw=json.loads(fetch(u))
        if str(raw.get('queryYear')) not in [str(d.year),str(d.year-1911)] or len(raw.get('data',[]))<10: raise ValueError('日曆年份或資料不完整')
        # 開始交易日與最後交易日是開市註記，其餘列為休市或僅交割。
        holidays={x[0]:x[1] for x in raw['data'] if '交易日' not in x[1]}
        is_open=d.weekday()<5 and day not in holidays
        result={'date':day,'isTradingDay':is_open,'status':'verified','note':holidays.get(day,'週末休市' if d.weekday()>=5 else '官方年度日曆列為交易日；臨時停市仍以證交所公告為準'),'source':u,'fetchedAt':now()}
        atomic(DATA/'cache'/f'calendar-{d.year}.json',{'source':u,'fetchedAt':now(),'data':raw})
        return result
    except Exception as e:
        return {'date':day,'isTradingDay':None,'status':'unavailable','note':'交易日曆查不到／待更新；排程不猜測開市。'+type(e).__name__,'source':u,'fetchedAt':now()}

def roc(s):
    y,m,d=map(int,s.split('/'));return f'{y+1911:04d}-{m:02d}-{d:02d}'
def num(v):return float(str(v).replace(',','').replace('X','').strip())
def empty(label,u,error):return {'label':label,'value':None,'change':None,'dir':0,'note':'查不到／待更新：'+str(error),'asOf':None,'source':u,'fetchedAt':now()}
def market_tw(day,stock=False):
    label='台積電' if stock else '台股加權'; target=datetime.fromisoformat(day).date()
    base='https://www.twse.com.tw/rwd/zh/afterTrading/'+('STOCK_DAY?stockNo=2330&' if stock else 'FMTQIK?')
    u=base+'date='+day.replace('-','')+'&response=json'
    try:
        rows=json.loads(fetch(u)).get('data',[])
        valid=[r for r in rows if roc(r[0])<day]
        if not valid:
            p=target.replace(day=1)-timedelta(days=1);u=base+f'date={p:%Y%m%d}&response=json'
            valid=[r for r in json.loads(fetch(u)).get('data',[]) if roc(r[0])<day]
        r=max(valid,key=lambda x:roc(x[0])); value=num(r[6 if stock else 4]);diff=num(r[7 if stock else 5]); change=round(diff/(value-diff)*100,3)
        return {'label':label,'value':value,'change':change,'dir':(diff>0)-(diff<0),'note':'前次可取得的已收盤資料；非即時行情','asOf':roc(r[0]),'source':u,'fetchedAt':now(),'unit':'元' if stock else '點'}
    except Exception as e:return empty(label,u,type(e).__name__)

def market_us(symbol,label,day):
    u='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')+'?interval=1d&range=1mo'
    try:
        o=json.loads(fetch(u))['chart']['result'][0]; tz=ZoneInfo('America/New_York'); cutoff=min(datetime.now(TZ),datetime.fromisoformat(day+'T23:59:59').replace(tzinfo=TZ)); points=[]
        for ts,v in zip(o['timestamp'],o['indicators']['quote'][0]['close']):
            d=datetime.fromtimestamp(ts,tz)
            # 日 K 包含未收盤資料；僅納入 NY 16:15 後已結束的交易日。
            if v is not None and d.replace(hour=16,minute=15,second=0)<cutoff:points.append((d.date().isoformat(),v))
        if len(points)<2:raise ValueError('沒有兩期已收盤資料')
        (d,v),(pd,p)=points[-1],points[-2];ch=round((v/p-1)*100,3)
        return {'label':label,'value':round(v,2),'change':ch,'dir':(ch>0)-(ch<0),'note':'Yahoo Finance 已收盤日 K；日期為美東交易日。資料延遲可能存在。','asOf':d,'source':u,'fetchedAt':now(),'unit':'點'}
    except Exception as e:return empty(label,u,type(e).__name__)

def rate(day,series,label):
    start=(datetime.fromisoformat(day)-timedelta(days=21)).date().isoformat();u=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}&coed={day}'
    try:
        rows=list(csv.DictReader(io.StringIO(fetch(u))));rows=[r for r in rows if r.get(series) not in [None,'','.'] and (r.get('DATE') or r.get('observation_date',''))<day]
        r=rows[-1];d=r.get('DATE') or r.get('observation_date');v=num(r[series]);ch=round(v-num(rows[-2][series]),3) if len(rows)>1 else None
        return {'label':label,'value':v,'change':ch,'dir':0,'note':'官方序列最新可得觀測；變動為百分點，發布可能落後','asOf':d,'source':u,'fetchedAt':now(),'unit':'%'}
    except Exception as e:return empty(label,u,type(e).__name__)

def policy_rate(day):
    u='https://markets.newyorkfed.org/api/rates/unsecured/effr/last/10.json'
    try:
        rows=json.loads(fetch(u))['refRates'];r=next(r for r in rows if r['effectiveDate']<day)
        return {'label':'聯邦基金有效利率','value':number_rate(r['percentRate']),'change':None,'dir':0,'note':'紐約 Fed EFFR，非 FOMC 目標區間；前值變動待更新','asOf':r['effectiveDate'],'source':u,'fetchedAt':now(),'unit':'%'}
    except Exception as e:return empty('聯邦基金有效利率',u,type(e).__name__)
def number_rate(x):return float(x)

def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s or ''))).strip()
def radio(day):
    lookup='https://itunes.apple.com/lookup?id=1569167575&country=tw';feed='https://feeds.soundon.fm/podcasts/049c00d3-d675-461e-9a11-522694633cdb.xml'
    try:
        catalog=json.loads(fetch(lookup));meta=catalog['results'][0]
        if meta['collectionId']!=1569167575:raise ValueError('Podcast ID 不符')
        # 只接受已核實的 SoundOn host，避免外來 feed 將請求轉向本機。
        feed=meta['feedUrl']
        if urllib.parse.urlparse(feed).hostname!='feeds.soundon.fm':raise ValueError('RSS 網域變更，待重新核實')
        root=ET.fromstring(fetch(feed)); candidates=[]
        cutoff=min(datetime.now(TZ),datetime.fromisoformat(day+'T23:59:59').replace(tzinfo=TZ))
        for item in root.findall('./channel/item'):
            try:d=parsedate_to_datetime(item.findtext('pubDate')).astimezone(TZ)
            except Exception:continue
            if d<=cutoff:candidates.append((d,item))
        d,item=max(candidates,key=lambda x:x[0]);desc=clean(item.findtext('description'))
        return {'title':item.findtext('title'),'date':d.date().isoformat(),'points':[],'note':('已核實 Apple ID 對應「'+meta['collectionName']+'」。僅讀 RSS 簡介，未收聽音訊。'+(' AI 摘要未設定。' if not ai.configured() else '')+' 最新可得集數不一定為今日。'),'url':item.findtext('link') or meta['collectionViewUrl'],'description':desc[:5000],'source':feed,'fetchedAt':now()}
    except Exception as e:return {'title':None,'date':None,'points':[],'note':'舟聲電台查不到／待更新：'+type(e).__name__,'url':None,'source':feed,'fetchedAt':now()}

def parse_ics(text,day,source):
    text=re.sub(r'\r?\n[ \t]','',text); target=datetime.fromisoformat(day).date(); monday=target-timedelta(days=target.weekday());last=monday+timedelta(days=7);out=[]
    for block in text.split('BEGIN:VEVENT')[1:]:
        title=re.search(r'^SUMMARY:(.+)$',block,re.M);ds=re.search(r'^DTSTART([^:]*):([^\r\n]+)',block,re.M)
        if not title or not ds:continue
        s=ds[2].strip()
        try:
            dt=datetime.strptime(s.rstrip('Z'),'%Y%m%dT%H%M%S').replace(tzinfo=ZoneInfo('UTC') if s.endswith('Z') else ZoneInfo('America/New_York')).astimezone(TZ)
        except ValueError:continue
        if not monday<=dt.date()<last:continue
        t=title[1].strip().replace('\\,',',').replace('\\n',' ')
        important=3 if any(x in t.lower() for x in ['gross domestic','personal income','consumer price','employment situation']) else 2
        out.append({'title':t,'time':dt.isoformat(timespec='minutes'),'importance':important,'consensus':None,'previous':None,'actual':None,'impact':'發布可能影響成長、通膨與利率預期；影響方向須依實際數據判斷。','note':'官方排程；預期值、前值與實際值查不到／待更新。','source':source,'dataDate':day,'fetchedAt':now()})
    return out

def events(day):
    sources={'BEA':'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics','BLS':'https://www.bls.gov/schedule/news_release/bls.ics'}
    out=[];coverage=[]
    for label,u in sources.items():
        try:
            parsed=parse_ics(fetch(u),day,u);out+=parsed
            coverage.append({'title':label+' 經濟行事曆','url':u,'status':'ok','note':f'本週擷取 {len(parsed)} 筆；不表示所有總經事件皆已涵蓋','fetchedAt':now()})
        except Exception as e:coverage.append({'title':label+' 經濟行事曆','url':u,'status':'unavailable','note':'查不到／待更新：'+type(e).__name__,'fetchedAt':now()})
    extra, extra_sources=official_context(day)
    out+=extra;coverage+=extra_sources
    return sorted(out,key=lambda x:(x['time'] is None, (x['time'] or '')[:10]!=day,-x['importance'],x['time'] or '')),coverage

def generate(day=None,scheduled=False):
    day=valid_date(day or today());cal=calendar(day)
    if scheduled and cal['isTradingDay'] is not True:
        result={'status':'skipped' if cal['isTradingDay'] is False else 'blocked','calendar':cal,'generatedAt':now()}
        atomic(DATA/'last-run.json',result);return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        jobs=[pool.submit(market_tw,day),pool.submit(market_tw,day,True),pool.submit(market_us,'^GSPC','S&P 500',day),pool.submit(market_us,'^IXIC','那斯達克',day),pool.submit(rate,day,'DGS10','美國 10 年債殖利率'),pool.submit(policy_rate,day),pool.submit(market_us,'^DJI','道瓊',day),pool.submit(market_us,'^SOX','費城半導體',day)]
        radiop=pool.submit(radio,day);eventp=pool.submit(events,day)
        markets=[j.result() for j in jobs];radio_data=radiop.result();macro,coverage=eventp.result()
    sources=[{'title':x['label'],'url':x['source'],'dataDate':x['asOf'],'fetchedAt':x['fetchedAt'],'status':'ok' if x['value'] is not None else 'unavailable'} for x in markets]
    sources+=coverage+[{'title':'證交所開休市日曆','url':cal['source'],'dataDate':day,'fetchedAt':cal['fetchedAt']},{'title':'方舟運算 RSS','url':radio_data['source'],'dataDate':radio_data['date'],'fetchedAt':radio_data['fetchedAt']}]
    crew=read(ROOT/'crew.json',[])
    lenses={p['id']:{'stance':None,'take':'依其公開框架，可關注'+p['framework']+'。今日 AI 推演查不到／待更新，未設定金鑰或尚未完成。','watch':p['watch']} for p in crew}
    valid=[x for x in markets if x['value'] is not None]
    recap=[]
    for x in markets[2:4]+markets[6:]:
        recap.append(f'{x["label"]}：{x["asOf"]} 收盤 {x["value"]:,.2f}，漲跌 {x["change"]:+.2f}%。' if x['value'] is not None else x['label']+'：查不到／待更新。')
    brief={'date':day,'generatedAt':now(),'headline':f'已整理 {len(valid)} 項可取得的市場資料。先確認各項資料日期，再檢視風險與紀律。','stance':{'score':None,'label':'盤勢立場待研究'},'market':markets[:6],'macro':macro,'recap':recap,'radio':radio_data,'board':{'status':'unavailable','note':'看板為 App 會員限定，今日未納入；Threads @arkerationapp 查不到／待更新。','items':[]},'lenses':lenses,'sources':sources,'calendar':cal,'status':'partial','note':'真實來源擷取完成，但總經覆蓋尚未齊全。所有金額與漲跌僅代表標示日期，利率用中性色。','gaps':['總經排程採 BLS、BEA 與 Fed 官方來源；空白不代表今天沒有重大事件','ISM／初領失業金／零售／台灣出口／央行／外資與國際事件的完整自動研究仍待接可靠資料源；Fed 談話僅取官方已發布項目','總經市場預期值及實際公布值待可靠來源','Spotify ID 尚未確認可用；會員看板與 Threads 未讀取','未定義崩跌、連續未執行與規則優先順序；衝突時不產生交易指令']}
    if ai.configured():
        try:
            prompt='依提供的真實資料產出 JSON {"headline":字串,"stance":{"score":-2到2或null,"label":字串},"lenses":{每個id:{"stance":-2到2或null,"take":80至130字,"watch":字串}},"radioPoints":陣列}。8 人逐一依其公開框架推演，不虛構不同意見。資料不足可全部待更新，勿編造今日事件或人物現職。Podcast 僅依 description 摘要；不延伸原文。所有數值與日期只能引用提供資料。資料日期落後時明說。\n人物：'+json.dumps(crew,ensure_ascii=False)+'\n今日來源：'+json.dumps(brief,ensure_ascii=False)
            result=ai.parse_json(ai.call(prompt,json_mode=True))
            candidate=dict(brief)
            for k in ['headline','stance','lenses']:candidate[k]=result[k]
            validate_brief(candidate)
            for v in candidate['lenses'].values():
                if not isinstance(v.get('take'),str) or not isinstance(v.get('watch'),str):raise ValueError('人物推演格式不完整')
            points=result.get('radioPoints',[])
            if not isinstance(points,list) or any(not isinstance(x,str) for x in points):raise ValueError('Podcast 摘要格式無效')
            for k in ['headline','stance','lenses']:brief[k]=candidate[k]
            brief['radio']['points']=points;brief['aiGenerated']=True
        except Exception as e:brief['gaps'].append('AI 推演未完成：'+str(e));brief['aiGenerated']=False
    else:brief['aiGenerated']=False;brief['gaps'].append('未設定 AI API 金鑰：大師每日推演與 AI 摘要待更新')
    validate_brief(brief)
    path=DATA/'briefs'/f'{day}.json'
    try:atomic(path,brief)
    except Exception:
        print(json.dumps(brief,ensure_ascii=False,indent=2));raise
    atomic(DATA/'last-run.json',{'status':'partial','date':day,'generatedAt':now(),'path':str(path),'calendar':cal})
    return brief

def validate_brief(b):
    valid_date(b['date'])
    for k in ['generatedAt','headline','stance','market','macro','recap','radio','board','lenses','sources']:
        if k not in b:raise ValueError('Brief 缺少欄位 '+k)
    for s in [b['stance']['score']]+[v['stance'] for v in b['lenses'].values()]:
        if s is not None and (isinstance(s,bool) or s not in [-2,-1,0,1,2]):raise ValueError('盤勢分數超出範圍')
    if set(b['lenses'])!=set(['buffett','marks','dalio','druckenmiller','wood','huang','wei','nadella']):raise ValueError('人物推演資料不完整')
    for x in b['market']:
        for k in ['label','value','change','dir','note','asOf','source','fetchedAt']:
            if k not in x:raise ValueError('市場資料缺少 '+k)
    return b


def official_context(day):
    target=datetime.fromisoformat(day).date();monday=target-timedelta(days=target.weekday());last=monday+timedelta(days=7)
    events_out=[];sources=[]
    urls={'Fed 已發布演說':'https://www.federalreserve.gov/feeds/speeches.xml','FOMC 會議日曆':'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'}
    for label,url in urls.items():
        try:
            raw=fetch(url);count=0
            if '演說' in label:
                root=ET.fromstring(raw)
                for item in root.findall('./channel/item'):
                    try:dt=parsedate_to_datetime(item.findtext('pubDate')).astimezone(TZ)
                    except Exception:continue
                    if not monday<=dt.date()<last or dt>datetime.now(TZ):continue
                    events_out.append({'title':'Fed 已發布演說：'+clean(item.findtext('title')),'time':dt.isoformat(timespec='minutes'),'importance':2,'consensus':None,'previous':None,'actual':None,'impact':'僅列官方演說標題與發布時間，未將標題推論為利率立場。','note':'此時間是 RSS 公布時間，不是未來演說預告；非數據項目，預期值與前值不適用。','source':item.findtext('link') or url,'dataDate':dt.date().isoformat(),'fetchedAt':now()});count+=1
            else:
                marker=str(target.year)+' FOMC Meetings'
                if marker not in raw:raise ValueError('未取得當年日曆')
                section=raw.split(marker,1)[1].split('panel panel-default',1)[0]
                pairs=re.findall(r'fomc-meeting__month[^>]*>.*?<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)',section,re.S)
                if not pairs:raise ValueError('FOMC 日曆格式變更')
                for month,days in pairs:
                    try:
                        monthnum=datetime.strptime(month.strip(),'%B').month;end=int(re.findall(r'\d+',days)[-1]);d=target.replace(month=monthnum,day=end)
                    except Exception:continue
                    if not monday<=d<last:continue
                    # 官方這頁未載發布時刻；保留日期與未知時間，不臆測 14:00。
                    events_out.append({'title':f'FOMC 會議（美東 {target.year}-{monthnum:02d}-{days.strip()}）','time':None,'importance':3,'consensus':None,'previous':None,'actual':None,'impact':'關注政策聲明；官方此頁未列發表時刻，台北時間待更新。','note':'會議日期來自 Fed；未假定政策結果或發布時間。','source':url,'dataDate':day,'fetchedAt':now()});count+=1
            sources.append({'title':label,'url':url,'dataDate':day,'status':'ok','note':f'本週 {count} 筆已核實紀錄','fetchedAt':now()})
        except Exception as e:sources.append({'title':label,'url':url,'dataDate':None,'status':'unavailable','note':'查不到／待更新：'+type(e).__name__,'fetchedAt':now()})
    return events_out,sources
