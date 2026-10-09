export const group=(p,r)=>p.ret===null?'待更新':p.ret<=r.p1?'P1':p.ret<=r.p3?'P3':p.ret>=r.p2?'P2':'正常持有';
export function journalWaterline(p){return ['P1','P2','P3'].map(k=>{const names=p.positions.filter(x=>group(x,p.rules)===k).map(x=>x.code+' '+x.name);return k+'：'+(names.length?'核對 '+names.join('、')+' 的資料與執行紀錄；':'目前已知報酬率中沒有此分組，先補齊缺值；')+'門檻依已設定 '+p.rules[k.toLowerCase()]+'%，不另設行情價位或交易指令。';}).join('\n');}
export function finalizeJournal(text,p){
 const water=journalWaterline(p);
 const section=/^(?:\*\*)?水位行動清單[^\n]*\n[\s\S]*?(?=^(?:\*\*)?(?:船員點評|紀律提醒))/m;
 if(section.test(text))return text.replace(section,'水位行動清單\n'+water+'\n\n');
 if(text.replaceAll('**','').includes(water))return text;
 throw new Error('複盤章節格式不完整，未存入日誌，請重試。');
}
export function validateJournal(text,p,brief,day){
 const plain=text.replaceAll('**','');
 for(const line of journalWaterline(p).split('\n'))if(!plain.includes(line))throw new Error('AI 改寫了既有水位規則，未存入日誌，請重試。');
 const values=[1,2,3,day,p.positions.length,...['P1','P2','P3','正常持有','待更新'].map(k=>p.positions.filter(x=>group(x,p.rules)===k).length),p.asOf,p.totalPnl,p.cumulativePnl,...Object.values(p.rules),...p.positions.flatMap(x=>[x.code,x.name,x.shares,x.ret,x.pnl,x.value]),brief.date,...[...(brief.market||[]),...(brief.macroRadar?.items||[])].flatMap(x=>[x.label,x.value,x.change,x.asOf,x.previousAsOf]),...(brief.macroRadar?.items||[]).flatMap(x=>[x.framework,x.note])];
 const numbers=s=>[...String(s??'').matchAll(/-?\d+(?:,\d{3})*(?:\.\d+)?/g)].map(x=>Math.abs(Number(x[0].replaceAll(',',''))));
 const allowed=new Set(values.flatMap(numbers).flatMap(n=>[n,...[0,1,2].map(d=>Number(n.toFixed(d)))]));
 if(numbers(plain).some(n=>!allowed.has(n)))throw new Error('AI 含有來源未提供的數字，未存入日誌，請核對後重試。');
}
export const mergePositions=(old,rows)=>{const m=new Map(old.map(p=>[p.code,{...p}]));for(const p of rows){const q=m.get(p.code)||{};for(const [k,v] of Object.entries(p))if(v!==null&&v!=='')q[k]=v;m.set(p.code,m.has(p.code)?q:{...p});}return [...m.values()];};
export const h=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const rich=s=>h(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
export const safeURL=s=>{try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
export function ndjsonParser(onObject){let pending='';return {push(t){pending+=t;let i;while((i=pending.indexOf('\n'))>=0){const line=pending.slice(0,i).trim();pending=pending.slice(i+1);if(line)onObject(JSON.parse(line));}},end(){if(pending.trim())onObject(JSON.parse(pending));pending='';}};}
export function sseParser(onEvent){let buffer='';return {push(t){buffer+=t;buffer=buffer.replace(/\r\n/g,'\n');let i;while((i=buffer.indexOf('\n\n'))>=0){const block=buffer.slice(0,i);buffer=buffer.slice(i+2);let event='message',data=[];for(const line of block.split('\n')){if(line.startsWith('event:'))event=line.slice(6).trim();if(line.startsWith('data:'))data.push(line.slice(5).trimStart());}if(data.length)onEvent(event,JSON.parse(data.join('\n')));}},end(){if(buffer.trim())throw new Error('串流事件未完整接收');}};}
export async function consumeSSE(response,onDelta,signal){const reader=response.body.getReader(),decoder=new TextDecoder();let done=false;const parser=sseParser((event,obj)=>{if(event==='delta')onDelta(obj.text);if(event==='done')done=true;if(event==='error')throw new Error(obj.error||'串流失敗');});try{while(true){if(signal?.aborted)throw new DOMException('已停止','AbortError');const {value,done:end}=await reader.read();if(end)break;parser.push(decoder.decode(value,{stream:true}));}parser.push(decoder.decode());parser.end();if(!done)throw new Error('串流未完成，內容未自動存檔');}catch(e){await reader.cancel().catch(()=>{});throw e;}finally{reader.releaseLock();}}

export function briefEvidence(brief){if(!brief?.macroRadar)return brief;return {...brief,macroRadar:{...brief.macroRadar,items:brief.macroRadar.items.map(({history,...item})=>item)}};}
