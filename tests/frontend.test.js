import test from 'node:test';import assert from 'node:assert/strict';import {group,ndjsonParser,sseParser,rich,safeURL,mergePositions,consumeSSE} from '../lib.js';
import {journalWaterline,validateJournal,finalizeJournal} from '../lib.js';
test('journal rejects invented price levels and changed waterline rules before saving',()=>{
 const p={asOf:'2026-09-30',totalPnl:0,rules:{p1:-15,p3:-8,p2:5},positions:[{code:'0056',name:'測試',ret:null,pnl:0,shares:null,value:null}]};
 const b={date:'2026-10-08',market:[{value:49806.37,change:0.578,asOf:'2026-10-07'}]};
 const valid='Day 339，損益 0。\n'+journalWaterline(p);
 assert.doesNotThrow(()=>validateJournal(valid+' 0.58%',p,b,339));
 assert.throws(()=>validateJournal(valid+'\n支撐位約 49000 點。',p,b,339),/來源未提供/);
 assert.throws(()=>validateJournal(valid+'\n利率警戒線 5.5%。',p,b,339),/來源未提供/);
 assert.throws(()=>validateJournal(valid.replace('P1：','P1 更改：'),p,b,339),/水位規則/);
 assert.match(journalWaterline(p),/先補齊缺值/);
 const draft='已知損益 0。\n水位行動清單照規則，請執行：\nP2：觀察 49000 點。\n船員點評：依公開框架推演。\n紀律提醒：核對來源。';
 const final=finalizeJournal(draft,p);
 assert.ok(!final.includes('49000'));
 assert.ok(final.includes(journalWaterline(p)));
 assert.doesNotThrow(()=>validateJournal(final,p,b,339));
 assert.throws(()=>finalizeJournal('缺少章節',p),/章節格式/);
});
test('ret percentage units and mutually exclusive groups',()=>assert.deepEqual([-22.73,-15,-8,0,5,null].map(ret=>group({ret},{p1:-15,p3:-8,p2:5})),['P1','P1','P3','正常持有','P2','待更新']));
test('NDJSON survives arbitrary chunks and non-newline final object',()=>{const results=[];const parser=ndjsonParser(x=>results.push(x));const text='{"id":"buffett","reply":"繁體中文"}\n{"id":"wei","reply":"台積電"}';for(let i=0;i<text.length;i+=2)parser.push(text.slice(i,i+2));parser.end();assert.equal(results[0].reply,'繁體中文');assert.equal(results[1].id,'wei');});
test('SSE survives every byte boundary incl CRLF',()=>{const results=[];const p=sseParser((e,o)=>results.push([e,o]));const t='event: delta\r\ndata: {"text":"你好"}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n';for(const c of t)p.push(c);p.end();assert.deepEqual(results,[['delta',{text:'你好'}],['done',{}]]);});
test('incomplete SSE and malformed NDJSON rejected',()=>{const p=sseParser(()=>{});p.push('data: {"text":"x"}');assert.throws(()=>p.end());const n=ndjsonParser(()=>{});assert.throws(()=>n.push('not json\n'));});
test('safe markdown and URLs do not inject HTML',()=>{assert.equal(rich('**好**<img onerror="x">'),'<strong>好</strong>&lt;img onerror=&quot;x&quot;&gt;');assert.equal(safeURL('javascript:alert(1)'),'#');});
test('later nonempty values only; zero retained',()=>{const out=mergePositions([{code:'0056',ret:null,pnl:0,name:'原名'}],[{code:'0056',ret:5,pnl:null,name:''}]);assert.equal(out.length,1);assert.equal(out[0].pnl,0);assert.equal(out[0].ret,5);assert.equal(out[0].name,'原名');});

test('UTF-8 SSE survives split multibyte bytes',async()=>{const data=new TextEncoder().encode('event: delta\ndata: {"text":"臺灣繁體"}\n\nevent: done\ndata: {}\n\n');const stream=new ReadableStream({start(c){for(const b of data)c.enqueue(new Uint8Array([b]));c.close();}});let result='';await consumeSSE(new Response(stream),s=>result+=s);assert.equal(result,'臺灣繁體');});
test('missing completion event rejects partial stream',async()=>{await assert.rejects(consumeSSE(new Response('event: delta\ndata: {"text":"partial"}\n\n'),()=>{}),/串流未完成/);});

test('macro readings preserve FX direction, volatility meaning, and missing observations',async()=>{
 const {macroReading,renderMacro}=await import('../macro.js');
 assert.match(macroReading({id:'yen',value:147,change:-2}),/日圓升值/);
 assert.match(macroReading({id:'yen',value:157,change:1}),/日圓貶值/);
 assert.match(macroReading({id:'vix',value:16,change:-1}),/不能直接推論股市上漲/);
 assert.match(macroReading({id:'conditions',value:-.494,change:.016}),/較寬鬆.*相較上週走緊/);
 assert.match(macroReading({id:'gold',value:null,change:null}),/保留空值/);
 assert.match(renderMacro(null),/歷史日報尚無跨資產資料/);
 assert.match(renderMacro(null),/https:\/\/stable-value.fanhow.chatgpt.site\/sentiment/);
 assert.ok(!renderMacro({items:[{id:'gold',value:null,change:null,label:'<script>',source:'javascript:alert(1)',history:[]}]}).includes('<script>'));
});
test('macro evidence reaches AI and journal numeric guard without chart-history noise',async()=>{
 const {briefEvidence}=await import('../lib.js');
 const p={asOf:'2026-09-30',totalPnl:0,rules:{p1:-15,p3:-8,p2:5},positions:[]};
 const b={date:'2026-10-08',market:[],macroRadar:{items:[{id:'yen',label:'日圓',value:157.81,change:.114,asOf:'2026-10-02',previousAsOf:'2026-10-01',history:[{value:199.88}]}]}};
 assert.equal(briefEvidence(b).macroRadar.items[0].history,undefined);
 assert.equal(b.macroRadar.items[0].history.length,1);
 assert.doesNotThrow(()=>validateJournal(journalWaterline(p)+' 日圓 157.81，變動 0.11%。',p,b,339));
 assert.throws(()=>validateJournal(journalWaterline(p)+' 日圓目標價 162.34。',p,b,339),/來源未提供/);
});
