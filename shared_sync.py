"""Local publisher. Private credentials/data never enter the public Pages build."""
from __future__ import annotations
import fcntl, hashlib, json, os, threading, urllib.request, urllib.error, uuid
from urllib.parse import urlencode
from core import DATA, ROOT, atomic, read, now, validate_portfolio, LOCK
import ai
STATE=DATA/'shared-sync.json'
ALLOWED_SITE='https://ark-agent.fanhow.chatgpt.site'
ENV_KEYS=('ARK_SHARED_SITE_URL','ARK_SHARED_SERVICE_TOKEN','ARK_SHARED_SYNC_SECRET')

def settings():
    if DATA!=(ROOT/'data').resolve():return {}  # Isolated tests must never publish fixture data.
    values={}
    path=ROOT/'.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            key,sep,value=line.partition('=')
            if sep and key.strip() in ENV_KEYS:values[key.strip()]=value.strip().strip('\"\'')
    for key in ENV_KEYS:
        if os.environ.get(key):values[key]=os.environ[key]
    return values

def configured(config):return config.get('ARK_SHARED_SITE_URL')==ALLOWED_SITE and all(config.get(k) for k in ENV_KEYS)

def canonical(value):
    if isinstance(value,float) and value.is_integer():return int(value)
    if isinstance(value,list):return [canonical(v) for v in value]
    if isinstance(value,dict):return {k:canonical(v) for k,v in value.items()}
    return value

def digest(value):return hashlib.sha256(json.dumps(canonical(value),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

class SyncError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def request(config,key,body=None):
    url=config['ARK_SHARED_SITE_URL']+'/api/shared/sync?'+urlencode({'key':key})
    headers={'OAI-Sites-Authorization':'Bearer '+config['ARK_SHARED_SERVICE_TOKEN'],'X-Ark-Sync-Key':config['ARK_SHARED_SYNC_SECRET'],'Content-Type':'application/json'}
    req=urllib.request.Request(url,headers=headers,data=None if body is None else json.dumps(body,ensure_ascii=False,allow_nan=False).encode())
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ai.context()))
    try:
        with opener.open(req,timeout=25) as response:return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code==409:raise SyncError('雲端版本衝突；已保留本機資料，請管理員核對，未覆寫雲端。') from None
        if e.code in (401,403):raise SyncError('共用同步驗證未通過；請管理員檢查網站服務授權與同步設定。') from None
        raise SyncError('共用網站回傳 HTTP '+str(e.code)+'；保留本機資料，稍後重試。') from None
    except Exception:raise SyncError('目前無法連線共用網站；保留本機資料，稍後自動重試。') from None

def documents():
    if (DATA/'portfolio.json').exists():yield 'portfolio',validate_portfolio(read(DATA/'portfolio.json'))
    for kind,folder in [('journal','journal'),('brief','briefs')]:
        for path in sorted((DATA/folder).glob('????-??-??.json')):yield kind+':'+path.stem,read(path)

def local_path(key):
    import re
    if key=='portfolio':return DATA/'portfolio.json'
    if not re.fullmatch(r'(brief|journal):\d{4}-\d{2}-\d{2}',key):raise SyncError('雲端資料識別無效')
    kind,date=key.split(':');return DATA/('briefs' if kind=='brief' else 'journal')/(date+'.json')

def pull_cloud(key,cloud,expected_hash=None):
    path=local_path(key);value=cloud['value']
    if key=='portfolio':value=validate_portfolio(value)
    elif not isinstance(value,dict) or value.get('date')!=key.split(':')[1]:raise SyncError('雲端資料日期無效')
    with LOCK:
        previous=read(path)
        if (digest(previous) if previous is not None else None)!=expected_hash:raise SyncError('同步期間本機資料已修改；保留本機內容，稍後重新比對。')
        if previous is not None:atomic(DATA/'history'/('sync-'+str(uuid.uuid4())+'.json'),previous)
        atomic(path,value)
    return value

def sync_once(transport=None):
    config=settings()
    if not configured(config):return {'configured':False,'status':'not_configured'}
    DATA.mkdir(parents=True,exist_ok=True)
    with (DATA/'shared-sync.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'configured':True,'status':'running'}
        state=read(STATE,{'documents':{}});state.setdefault('documents',{});errors=[];changed=0
        send=transport or (lambda key,body=None:request(config,key,body))
        try:
            manifest=send('manifest').get('documents',[]);remote={d['key']:d for d in manifest}
            local=dict(documents())
            for key in sorted(set(local)|set(remote)):
                value=local.get(key)
                entry=state['documents'].setdefault(key,{});target=digest(value) if value is not None else None
                if entry.get('hash')==target and not entry.get('pending') and remote.get(key,{}).get('revision',0)==entry.get('revision',0):continue
                try:
                    cloud=send(key);pending=entry.get('pending')
                    if not pending and cloud.get('value') is not None and (value is None or (entry.get('hash')==target and cloud['revision']>entry.get('revision',0))):
                        # Pull only when there are no unpublished local edits.
                        value=pull_cloud(key,cloud,target);entry.update(hash=digest(value),revision=cloud['revision']);entry.pop('error',None);state['lastSuccessAt']=now();changed+=1;atomic(STATE,state);continue
                    if pending:
                        # Recover a lost success response before sending a newer local version.
                        if cloud.get('requestId')==pending['requestId'] and digest(cloud['value'])==digest(pending['value']):
                            entry.update(hash=digest(pending['value']),revision=cloud['revision']);entry.pop('pending',None);pending=None
                        elif cloud['revision']!=pending['baseRevision']:raise SyncError('雲端版本已變更；保留雙方資料，請管理員核對。')
                    if not pending:
                        if cloud.get('value') is not None and digest(cloud['value'])==target:
                            entry.update(hash=target,revision=cloud['revision']);entry.pop('error',None);state['lastSuccessAt']=now();atomic(STATE,state);continue
                        if cloud['revision']!=entry.get('revision',0):raise SyncError('發現尚未核對的雲端版本；保留本機與雲端資料，未自動覆寫。')
                        pending={'key':key,'value':value,'baseRevision':cloud['revision'],'requestId':str(uuid.uuid4())};entry['pending']=pending;atomic(STATE,state)
                    result=send(key,pending);check=send(key)
                    if check.get('requestId')!=pending['requestId'] or check['revision']!=result['revision'] or digest(check['value'])!=digest(pending['value']):raise SyncError('同步回讀未一致；保留待同步資料，稍後重新核對。')
                    entry.update(hash=digest(pending['value']),revision=check['revision']);entry.pop('pending',None);entry.pop('error',None);changed+=1;state['lastSuccessAt']=now()
                except SyncError as e:entry['error']=str(e);errors.append(key+'：'+str(e))
                atomic(STATE,state)
        except SyncError as e:errors.append(str(e))
        except Exception:
            errors.append('本機資料讀取或驗證失敗；請檢查資料檔格式。')
        state.update(lastCheckedAt=now(),errors=errors,status='error' if errors else 'synced');atomic(STATE,state)
        return {'configured':True,'status':state['status'],'changed':changed,'errors':errors,'lastSuccessAt':state.get('lastSuccessAt')}

def public_status():
    config=settings();state=read(STATE,{})
    if not configured(config):return {'configured':False,'status':'not_configured'}
    pending=0
    try:
        for key,value in documents():
            if state.get('documents',{}).get(key,{}).get('hash')!=digest(value):pending+=1
    except Exception:pending+=1
    return {'configured':True,'status':'pending' if pending and state.get('status')!='error' else state.get('status','pending'),'pending':pending,'lastSuccessAt':state.get('lastSuccessAt'),'errors':state.get('errors',[]),'siteUrl':ALLOWED_SITE,'portfolioUpdatedAt':read(DATA/'portfolio.json',{}).get('updatedAt')}

def start_background():
    def loop():
        while True:
            try:sync_once()
            except Exception:pass  # Never log credentials or private request bodies.
            threading.Event().wait(15)
    worker=threading.Thread(target=loop,name='ark-shared-publisher',daemon=True);worker.start();return worker

if __name__=='__main__':print(json.dumps(sync_once(),ensure_ascii=False))
