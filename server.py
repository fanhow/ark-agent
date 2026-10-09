#!/usr/bin/env python3
"""Loopback-only, same-origin personal server. No credentials served to the browser."""
import argparse, base64, hashlib, json, mimetypes, os, re, secrets, struct, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from core import *
import ai
import shared_sync
TOKEN=secrets.token_urlsafe(32)
MAX_BODY=30*1024*1024
IMPORT_PROMPT='''擷取對帳單每檔持股，同代號合併，後來非空欄位補上。只回有效 JSON：
{"asOf":null,"dailyPnl":null,"totalPnl":null,"totalPnlLabel":null,"cumulativePnl":null,"cumulativePnlLabel":null,"note":"缺值原因及資料來源","positions":[{"code":"代號","name":"名稱","shares":null,"ret":null,"pnl":null,"value":null,"note":"缺值或計算來源"}]}。
看不清或沒有填 null，不猜不推算；唯一例外：成本與現值皆明確且成本非 0 時可算 (現值/成本-1)*100，必須在 note 保留成本、現值與公式。ret 數值 -22.73 代表 -22.73%。totalPnl 只取明列的總未實現損益；cumulativePnl 只取明列「累積損益（台幣）」金額，不能填報酬率、今日損益或個股損益，不由部分持股加總。截圖裁切的個股列若無完整代號則略過並註記；日期未顯示填 null。成本／持有股數同欄上下兩行時，上行為成本台幣，下行才是股數。shares 絕不能填成本金額；逗號是千位符號（如 1,586 為 1586 股），小數点保留（如 1.23 股）。直接抄錄畫面明列報酬率，不要重新計算。只有成本單位及總額可明確確認才允許計算，不要將成本總額再乘股數。dailyPnl 僅取今日損益。totalPnlLabel 與 cumulativePnlLabel 必須逐字抄下對應總額的原始欄名。畫面若只有今日損益、累積損益、股票市值，totalPnl 與 totalPnlLabel 必須為 null。不要將今日損益填入 totalPnl。逐字核對小數最後一位。保持代號的前導 0。不同日期不得合併為同一期，請於 note 說明。已知名稱僅供參考，不可當作持有證據。'''

def jpeg_size(b):
    if not b.startswith(b'\xff\xd8'):raise ValueError('頭像必須是 JPEG')
    i=2
    while i<len(b):
        if b[i]!=255:i+=1;continue
        while i<len(b) and b[i]==255:i+=1
        marker=b[i];i+=1
        if marker in [0xd8,0xd9]:continue
        size=int.from_bytes(b[i:i+2],'big')
        if size<2:break
        if marker in [0xc0,0xc1,0xc2]:return int.from_bytes(b[i+5:i+7],'big'),int.from_bytes(b[i+3:i+5],'big')
        i+=size
    raise ValueError('JPEG 無效')

def upload_type(b,ext):
    if ext in ['.csv','.tsv','.txt']:return 'text/plain'
    if ext=='.png' and b.startswith(b'\x89PNG\r\n\x1a\n'):return 'image/png'
    if ext in ['.jpg','.jpeg'] and b.startswith(b'\xff\xd8'):return 'image/jpeg'
    if ext=='.webp' and b[:4]==b'RIFF' and b[8:12]==b'WEBP':return 'image/webp'
    raise ValueError('檔案內容與支援格式不符')

class Handler(BaseHTTPRequestHandler):
    server_version='ArkLocal/1.0'
    def log_message(self,fmt,*args):
        # 不記錄請求內容、憑證或庫存。
        print(now(),fmt%args,flush=True)
    def security(self,write=False):
        host=self.headers.get('Host','')
        if host not in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']:raise PermissionError('僅接受本機主機名稱')
        origin=self.headers.get('Origin')
        if origin and origin not in [f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}']:raise PermissionError('拒絕跨來源請求')
        if self.headers.get('Sec-Fetch-Site')=='cross-site':raise PermissionError('拒絕跨網站請求')
        if write and self.headers.get('X-Ark-Token')!=TOKEN:raise PermissionError('本機操作驗證失敗，請重新整理頁面')
    def respond(self,obj,status=200):
        body=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.headers_common('application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def headers_common(self,ctype):
        self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    def body(self):
        if self.headers.get_content_type()!='application/json':raise ValueError('僅接受 application/json')
        n=int(self.headers.get('Content-Length','0'))
        if n<=0 or n>MAX_BODY:raise ValueError('請求過大或為空')
        obj=json.loads(self.rfile.read(n))
        if not isinstance(obj,dict):raise ValueError('請求必須為 JSON 物件')
        return obj
    def dispatch(self,method):
        try:
            self.security(method!='GET');u=urlparse(self.path);path=unquote(u.path);q=parse_qs(u.query)
            if method=='GET':self.get(path,q);return
            b=self.body()
            if path=='/api/ask' and method=='POST':
                if not ai.configured():self.respond({'error':'未設定 AI 金鑰'},503);return
                result=ai.call(b.get('prompt'),b.get('images'),bool(b.get('stream')),bool(b.get('json')))
                if b.get('stream'):
                    self.send_response(200);self.headers_common('text/event-stream; charset=utf-8');self.end_headers()
                    try:
                        with result:
                            for chunk in ai.deltas(result):self.event('delta',{'text':chunk})
                        self.event('done',{})
                    except (BrokenPipeError,ConnectionResetError):return
                    except Exception as e:self.event('error',{'error':str(e)})
                else:self.respond({'text':result})
            elif path=='/api/portfolio' and method=='PUT':self.respond(save_portfolio(b))
            elif path.startswith('/api/journal/') and method=='PUT':
                d=valid_date(path.rsplit('/',1)[1]);text=b.get('text')
                if not isinstance(text,str) or not text.strip() or len(text)>100000:raise ValueError('日誌文字無效')
                day=b.get('day')
                if type(day)!=int or day<0:raise ValueError('Day 無效')
                obj={'date':d,'day':day,'text':text,'totalPnl':number(b.get('totalPnl')),'createdAt':now()}
                with LOCK:
                    old=read(DATA/'journal'/f'{d}.json')
                    if old:atomic(DATA/'history'/f'journal-{datetime.now(TZ).strftime("%Y%m%dT%H%M%S%f")}.json',old)
                    atomic(DATA/'journal'/f'{d}.json',obj)
                self.respond(obj)
            elif path=='/api/avatars':
                id=b.get('id')
                if id not in IDS:raise ValueError('未知人物')
                with LOCK:
                    avatars=read(DATA/'avatars.json',{})
                    if method=='DELETE':
                        (DATA/'avatars'/f'{id}.jpg').unlink(missing_ok=True);avatars.pop(id,None)
                    elif method=='POST':
                        raw=base64.b64decode(b.get('data',''),validate=True)
                        if len(raw)>400000:raise ValueError('頭像過大')
                        w,h=jpeg_size(raw)
                        if w!=h or w>400 or w<1:raise ValueError('頭像需為最大 400px 正方形 JPEG')
                        (DATA/'avatars'/f'{id}.jpg').write_bytes(raw);avatars[id]='/data/avatars/'+id+'.jpg?v='+str(int(datetime.now(TZ).timestamp()))
                    else:raise ValueError('不支援的方法')
                    atomic(DATA/'avatars.json',avatars)
                self.respond(avatars)
            elif path=='/api/uploads' and method=='POST':
                name=Path(str(b.get('name','')).replace('\\','/')).name[:200];ext=Path(name).suffix.lower();raw=base64.b64decode(b.get('data',''),validate=True)
                if not raw or len(raw)>10*1024*1024:raise ValueError('每檔上限 10 MB')
                media=upload_type(raw,ext);id=hashlib.sha256(raw).hexdigest();meta={'id':id,'name':name,'media_type':media,'size':len(raw)}
                if media=='text/plain':meta['text'],meta['encoding']=decode_text(raw)
                with LOCK:
                    if not (DATA/'uploads'/id).exists():(DATA/'uploads'/id).write_bytes(raw)
                    atomic(DATA/'uploads'/f'{id}.json',meta)
                self.respond(meta)
            elif path=='/api/import/preview' and method=='POST':self.respond(self.preview(b))
            elif path=='/api/import/commit' and method=='POST':
                with LOCK:
                    current=read(DATA/'portfolio.json')
                    if b.get('baseUpdatedAt')!=current.get('updatedAt'):self.respond({'error':'庫存已在別處變更，請重新預覽'},409);return
                    self.respond(save_portfolio(commit_import(current,b.get('preview',{}),b.get('mode'),b.get('older'))))
            elif path=='/api/briefs/run' and method=='POST':
                from research import generate
                if not RESEARCH_LOCK.acquire(blocking=False):self.respond({'error':'每日研究已在執行中'},409);return
                try:self.respond(generate())
                finally:RESEARCH_LOCK.release()
            else:self.respond({'error':'找不到端點'},404)
        except PermissionError as e:self.respond({'error':str(e)},403)
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.respond({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            print(type(e).__name__,str(e),flush=True);self.respond({'error':'作業未完成：'+type(e).__name__},500)
    def event(self,name,obj):self.wfile.write(('event: '+name+'\ndata: '+json.dumps(obj,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
    def preview(self,b):
        result={'asOf':None,'totalPnl':None,'cumulativePnl':None,'positions':[],'note':''};parts=[];images=[]
        files=b.get('files',[])
        if not isinstance(files,list) or len(files)>30:raise ValueError('一次最多 30 個檔案')
        for id in dict.fromkeys(files):
            if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{64}',id):raise ValueError('檔案 ID 無效')
            meta=read(DATA/'uploads'/f'{id}.json')
            if not meta:raise ValueError('找不到上傳檔')
            if meta['media_type']=='text/plain':parts.append((meta['name'],meta['text']))
            else:images.append({'media_type':meta['media_type'],'data':base64.b64encode((DATA/'uploads'/id).read_bytes()).decode()})
        if b.get('text'):parts.append(('貼上文字',str(b['text'])[:200000]))
        if len(images)>3:raise ValueError('每批最多 3 張截圖，請分批辨識')
        unknown=[];dates=[]
        for name,text in parts:
            parsed=parse_csv(text)
            if not parsed['positions']:unknown.append(name+'\n'+text)
            result['positions']=merge_positions(result['positions'],parsed['positions'])
            if parsed['asOf']:dates.append(parsed['asOf']);result['asOf']=parsed['asOf']
            if parsed['totalPnl'] is not None:result['totalPnl']=parsed['totalPnl']
            if parsed.get('cumulativePnl') is not None:result['cumulativePnl']=parsed['cumulativePnl']
            result['note']+=name+'：'+parsed['note']+'；'
        if images or unknown:
            if not ai.configured():raise ValueError('未設定 AI 金鑰：截圖與非標準文字需 OPENAI_API_KEY；標準 CSV 可直接辨識')
            refs=[{'code':p['code'],'name':p['name']} for p in read(DATA/'portfolio.json')['positions']]
            extracted=ai.parse_json(ai.call(IMPORT_PROMPT+'\n已知名稱：'+json.dumps(refs,ensure_ascii=False)+'\n文字：'+ '\n'.join(unknown),images,json_mode=True))
            result['positions']=merge_positions(result['positions'],[position(x) for x in extracted.get('positions',[])])
            if extracted.get('asOf'):dates.append(valid_date(extracted['asOf']));result['asOf']=extracted['asOf']
            if extracted.get('totalPnl') is not None and '未實現' in str(extracted.get('totalPnlLabel') or '') and '今日' not in str(extracted.get('totalPnlLabel') or ''):result['totalPnl']=number(extracted['totalPnl'])
            if extracted.get('cumulativePnl') is not None:result['cumulativePnl']=number(extracted['cumulativePnl'])
            result['note']+=str(extracted.get('note') or '')
        if len(set(dates))>1:raise ValueError('批次含不同資料日期，請依日期拆開匯入')
        if not result['positions'] and result['cumulativePnl'] is None:raise ValueError('未辨識出持股，請提供含代號欄位的 CSV 或設定 AI 金鑰')
        if result['asOf'] is None:result['note']+='資料日期未提供，請於預覽確認。'
        if result['totalPnl'] is None:result['note']+='總損益未提供；不由部分持股加總。'
        return result
    def get(self,path,q):
        if path=='/api/shared/status':self.respond(shared_sync.public_status());return
        if path=='/api/status':self.respond({'aiConfigured':ai.configured(),'model':ai.model(),'csrfToken':TOKEN,'timezone':'Asia/Taipei','today':today(),'lastRun':read(DATA/'last-run.json'),'schedule':read(DATA/'schedule.json')});return
        if path=='/api/portfolio':self.respond(read(DATA/'portfolio.json'));return
        if path=='/api/portfolio/previous':
            current=read(DATA/'portfolio.json');files=sorted((DATA/'history').glob('[0-9]*.json'),reverse=True)
            older=[read(f) for f in files]
            older=[p for p in older if p.get('asOf') and current.get('asOf') and p['asOf']<current['asOf']]
            self.respond(max(older,key=lambda p:p['asOf']) if older else None);return
        if path=='/api/avatars':self.respond(read(DATA/'avatars.json',{}));return
        if path=='/api/briefs':
            limit=min(365,max(1,int(q.get('limit',['100'])[0])));self.respond([{'date':p.stem,'headline':read(p)['headline'],'generatedAt':read(p)['generatedAt']} for p in sorted((DATA/'briefs').glob('????-??-??.json'),reverse=True)[:limit]]);return
        if path.startswith('/api/briefs/'):
            d=valid_date(path.rsplit('/',1)[1]);obj=read(DATA/'briefs'/f'{d}.json');self.respond(obj if obj else {'error':'查不到／待更新'},200 if obj else 404);return
        if path=='/api/journal':self.respond([read(p) for p in sorted((DATA/'journal').glob('????-??-??.json'),reverse=True)]);return
        allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/styles.css':'styles.css','/crew.json':'crew.json','/lib.js':'lib.js','/macro.js':'macro.js','/storage.js':'storage.js','/config.json':'config.json'}
        if path in allowed:p=ROOT/allowed[path]
        elif re.fullmatch(r'/assets/(buffett|marks|dalio|druckenmiller|wood|huang|wei|nadella)\.svg',path):p=ROOT/path[1:]
        elif re.fullmatch(r'/data/avatars/(buffett|marks|dalio|druckenmiller|wood|huang|wei|nadella)\.jpg',path):p=DATA/'avatars'/Path(path).name
        else:self.respond({'error':'找不到檔案'},404);return
        if not p.is_file():self.respond({'error':'找不到檔案'},404);return
        raw=p.read_bytes();self.send_response(200);self.headers_common(mimetypes.guess_type(str(p))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):self.dispatch('GET')
    def do_POST(self):self.dispatch('POST')
    def do_PUT(self):self.dispatch('PUT')
    def do_DELETE(self):self.dispatch('DELETE')
RESEARCH_LOCK=threading.Lock()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    for d in ['briefs','journal','avatars','uploads','history','cache','logs']:(DATA/d).mkdir(parents=True,exist_ok=True)
    os.chmod(DATA,0o700)
    if not (DATA/'portfolio.json').exists():atomic(DATA/'portfolio.json',read(ROOT/'data/portfolio.initial.json'))
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    shared_sync.start_background()
    print(f'方舟智慧體 http://127.0.0.1:{a.port} · AI {"已設定" if ai.configured() else "未設定金鑰"}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
