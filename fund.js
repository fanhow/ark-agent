import {h,safeURL} from './lib.js';
import {FUND_COLUMNS,FUND_NUMBERS,validateFund,orderedRecords,capitalAt,fundSummary} from './fund-model.js';
const money=n=>n==null?'未提供':n.toLocaleString('zh-TW',{maximumFractionDigits:2});
const sign=n=>n==null?'未提供':(n>0?'+':'')+money(n);
const tone=n=>n>0?'up':n<0?'down':'';
const stamp=s=>new Date(s).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
const day=s=>Date.parse(s+'T00:00:00Z');
const provenance=v=>`${v.date||'日期未知'} · ${v.source}`;
let range='all',selectedDate=null;

export function renderFund(root,f,p){
 if(!f){root.hidden=true;return false;}
 validateFund(f);root.hidden=false;
 const opened=[...root.querySelectorAll('details[open]')].map(e=>e.className);
 const s=fundSummary(f,p),all=orderedRecords(f),last=all.at(-1);
 const records=range==='30'?all.filter(r=>day(last.date)-day(r.date)<=29*86400000):all;
 const principal=capitalAt(f,s.totalAssets.date||last.date);
 const card=(label,metric,detail='')=>`<article class="fund-stat"><span>${h(label)}</span><strong class="mono ${tone(metric.value)}">${sign(metric.value)}</strong><small>${h(provenance(metric))}${detail?'<br>'+h(detail):''}</small></article>`;
 const metricTitle=s.holdingsPnl.kind==='positions'?'總未實現損益（持股加總）':'總未實現損益';
 root.innerHTML=`<div class="fund-heading"><div><span class="eyebrow">STABLE 500 · FUND OVERVIEW</span><h2>${h(f.name)}・基金成長紀錄</h2><p>試算表截至 ${h(last.date)} · 新台幣 · ${f.source.live?'隨原表更新':'已匯入資料'}</p></div><a class="fund-source-link" href="${h(safeURL(f.source.url))}" target="_blank" rel="noopener noreferrer">查看原始試算表 ↗</a></div>
 <p id="fund-source-status" class="fund-source-status" role="status"></p><div class="fund-overview"><article class="fund-assets"><span>基金總資產 <small>TWD</small></span><strong class="mono">${money(s.totalAssets.value)}</strong><p>${h(provenance(s.totalAssets))}</p><span class="fund-principal">累計投入本金 <b class="mono">${money(principal)}</b></span></article><div class="fund-key-stats">
 ${card('今日損益',s.dailyPnl,s.dailyPnl.kind==='photo'&&s.dailyPnl.percent!=null?'今日損益率 '+sign(s.dailyPnl.percent)+'%':'原表：今日績效')}
 ${card(metricTitle,s.holdingsPnl,s.holdingsPnl.kind==='sheet'?'原表：持倉累計績效；採原表合計':s.total.complete?`${s.total.available} 檔已確認持股加總`:`僅 ${s.total.available}／${s.total.count} 檔有值，總額未提供`)}
 <article class="fund-stat"><span>股票市值</span><strong class="mono">${money(s.stockMarketValue.value)}</strong><small>${h(provenance(s.stockMarketValue))}<br>原表：目前總持倉</small></article>
 <article class="fund-stat"><span>持倉成本</span><strong class="mono">${money(s.stockCost.value)}</strong><small>${h(provenance(s.stockCost))}</small></article>
 </div></div>
 <p class="fund-scope-note">基金曲線依原表的帳戶總資產，包含原表已計入的現金與持倉。當日持股加總只反映未結清庫存；原表目前沒有獨立的「已實現損益」欄位，因此不自行推算結清成果。</p><section class="panel fund-chart-panel" aria-label="基金總資產成長曲線"><div class="fund-chart-head"><div><h3>資產成長曲線</h3><p class="small muted">總資產含入出金變動，不等於投資報酬率。</p></div><div class="fund-range" role="group" aria-label="曲線期間"><button data-fund-range="all" aria-pressed="${range==='all'}">全部紀錄</button><button data-fund-range="30" aria-pressed="${range==='30'}">近 30 日</button></div></div>
 <div class="fund-legend"><span><i class="asset-line"></i>基金總資產</span><span><i class="capital-line"></i>累計投入本金</span><span><i class="carry-line"></i>原表沿用前次資產</span></div>
 <div class="fund-chart-scroll"><div class="fund-chart" id="fund-chart"></div></div><div class="fund-readout" id="fund-readout" aria-live="polite"></div>
 <div class="fund-deposits">${f.capital.events.map(e=>`<span class="fund-event-date">${h(e.date)}</span><strong>${e.amount>=0?'入金':'出金'} ${sign(e.amount)} 元</strong><span>${h(e.note)}</span>`).join('')}</div>
 <p class="small muted fund-chart-note">橫軸依實際日期間隔；僅連接已記錄日期，沒有紀錄的日子不補值。縱軸為萬元，範圍依顯示期間調整。</p></section>
 <div class="fund-extra-stats">${card('基金累計績效',s.fundPnl,'保留原表定義，與持倉損益分列')}${card('台股累計績效',s.taiwanPnl)}${card('美股累計績效',s.usPnl)}</div>
 <details class="fund-history panel"><summary>每日績效明細 <span>${all.length} 筆 · ${all[0].date} — ${last.date} · 原表 11 個欄位</span></summary><p class="small muted">金額單位：新台幣。空白保留為「未提供」，沿用數值與來源備註均保留。</p><div class="fund-table-wrap" tabindex="0" role="region" aria-label="每日績效明細，可左右捲動"><table><thead><tr>${FUND_COLUMNS.map(([,label])=>`<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${[...all].reverse().map(r=>`<tr>${FUND_COLUMNS.map(([k])=>`<td class="${FUND_NUMBERS.includes(k)?'mono':'fund-text'}">${h(FUND_NUMBERS.includes(k)?money(r[k]):r[k]||'未提供')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>
 <details class="fund-method panel"><summary>資料來源、合併規則與核對事項</summary><p>來源：${h(f.source.title)}／${h(f.source.sheet)}。資料更新 ${h(stamp(f.source.importedAt))}；${f.source.updateBasis==='observed-content-change'?'確認原表內容變更':'原表檔案更新'} ${h(stamp(f.source.modifiedAt))}（台北時間）。${f.source.live?'網站直接讀取這張試算表既有的唯讀入口，每 60 秒檢查。原表的變更會重畫曲線，無須重新上傳照片或部署網站；連線失敗時明示資料尚未更新。':'目前為匯入資料，之後的修改須再次匯入。'}</p><p>同義欄位只顯示一份：總資產＝基金總資產；股票市值＝目前總持倉；今日損益＝今日績效；總未實現損益＝持倉累計績效。基金累計績效另列，避免混為同一指標。</p><p>先比較資料日期；同日再比較照片記錄時間與原表該日數值的更新時間。自動讀取時，以網站首次確認該日數字有變更的時間作為更新依據，不把每次檢查當成新資料。這些時間不代表行情時間；缺值才保留另一來源，並逐欄標明來源日期。原表沒有提供的百分比，不套用舊照片的百分比。</p><p>下方庫存仍依已確認的持股快照（${h(p.asOf||'日期待確認')}）。${s.total.complete?'其未實現損益加總為 '+sign(s.total.sum)+' 元':'目前只有 '+s.total.available+'／'+s.total.count+' 檔有損益'}；若總覽採較新的原表持倉合計，兩者可能不同。試算表未核對的個股 OCR 不會覆蓋已確認庫存。</p><p>本金依使用者確認：原投入 ${money(f.capital.initial)} 元，${f.capital.events.map(e=>h(e.date)+' '+(e.amount>=0?'入金':'出金')+' '+sign(e.amount)+' 元').join('；')}。本金線只包含已知資金紀錄，未以資產變動推算報酬率。</p><ul>${f.notes.map(n=>`<li>${h(n)}</li>`).join('')}</ul></details>`;
 root.querySelectorAll('[data-fund-range]').forEach(b=>b.onclick=()=>{range=b.dataset.fundRange;selectedDate=null;renderFund(root,f,p);root.querySelector(`[data-fund-range="${range}"]`).focus();});
 for(const detail of root.querySelectorAll('details'))detail.open=opened.includes(detail.className);
 updateFundStatus(root,f);drawChart(root,f,records);
 return true;
}

function drawChart(root,f,rows){
 const mobile=matchMedia('(max-width:650px)').matches;
 const W=mobile?420:1000,H=mobile?290:310,left=mobile?44:72,right=mobile?16:24,top=25,bottom=48;
 const start=day(rows[0].date),end=day(rows.at(-1).date),x=d=>left+(day(d)-start)/(end-start||1)*(W-left-right);
 const candidates=rows.flatMap(r=>[r.totalAssets,capitalAt(f,r.date)]).filter(v=>v!=null);
 const step=500000,lo=Math.max(0,Math.floor((Math.min(...candidates)-100000)/step)*step),hi=Math.ceil((Math.max(...candidates)+100000)/step)*step;
 const y=v=>top+(hi-v)/(hi-lo||1)*(H-top-bottom);
 let grid='';for(let v=lo;v<=hi;v+=step)grid+=`<line x1="${left}" y1="${y(v)}" x2="${W-right}" y2="${y(v)}" class="fund-gridline"/><text x="${left-12}" y="${y(v)+4}" text-anchor="end">${money(v/10000)}</text>`;
 const ticks=[0,Math.floor((rows.length-1)/3),Math.floor(2*(rows.length-1)/3),rows.length-1];
 grid+=[...new Set(ticks)].map(i=>`<text x="${x(rows[i].date)}" y="${H-16}" text-anchor="middle">${rows[i].date.slice(5).replace('-','/')}</text>`).join('');
 let segments='';for(let i=1;i<rows.length;i++){const a=rows[i-1],b=rows[i];if(a.totalAssets==null||b.totalAssets==null)continue;segments+=`<path d="M${x(a.date)},${y(a.totalAssets)} L${x(b.date)},${y(b.totalAssets)}" class="fund-asset-path ${/沿用前次/.test(b.notes)?'carried':''}"/>`;}
 let capitalPath=`M${left},${y(capitalAt(f,rows[0].date))}`;
 const events=[...f.capital.events].sort((a,b)=>a.date.localeCompare(b.date)).filter(e=>day(e.date)>start&&day(e.date)<=end);
 for(const e of events)capitalPath+=` H${x(e.date)} V${y(capitalAt(f,e.date))}`;
 capitalPath+=` H${W-right}`;
 const markers=f.capital.events.filter(e=>day(e.date)>=start&&day(e.date)<=end).map(e=>`<line x1="${x(e.date)}" x2="${x(e.date)}" y1="${top}" y2="${H-bottom}" class="fund-event-line"/><text x="${x(e.date)-8}" y="${top+12}" text-anchor="end">${e.date.slice(5).replace('-','/')} ${e.amount>=0?'入金':'出金'}</text>`).join('');
 root.querySelector('#fund-chart').innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="基金總資產與投入本金曲線，縱軸 ${lo/10000} 至 ${hi/10000} 萬元；可用下方日期控制查閱數字"><text x="${left}" y="14">萬元</text>${grid}${markers}<path d="${capitalPath}" class="fund-capital-path"/>${segments}${rows.filter(r=>r.totalAssets!=null).map(r=>`<circle cx="${x(r.date)}" cy="${y(r.totalAssets)}" r="${/沿用前次/.test(r.notes)?3:4}" class="fund-point"><title>${h(r.date)}：${money(r.totalAssets)} 元</title></circle>`).join('')}<line id="fund-cursor" y1="${top}" y2="${H-bottom}" class="fund-cursor"/></svg><label class="fund-date-control">查閱日期 <input id="fund-date-slider" type="range" min="0" max="${rows.length-1}" value="${rows.length-1}" aria-label="查閱基金歷史日期"></label>`;
 const show=i=>{const r=rows[i];selectedDate=r.date;root.querySelector('#fund-date-slider').value=i;root.querySelector('#fund-date-slider').setAttribute('aria-valuetext',`${r.date}，總資產 ${money(r.totalAssets)} 元`);const cursor=root.querySelector('#fund-cursor');cursor.setAttribute('x1',x(r.date));cursor.setAttribute('x2',x(r.date));root.querySelector('#fund-readout').innerHTML=`<strong>${h(r.date)}</strong><span>基金總資產 <b class="mono">${money(r.totalAssets)}</b></span><span>投入本金 <b class="mono">${money(capitalAt(f,r.date))}</b></span>${/沿用前次/.test(r.notes)?'<span class="fund-carried">資產沿用前次紀錄</span>':''}`;};
 const slider=root.querySelector('#fund-date-slider');slider.oninput=()=>show(Number(slider.value));
 root.querySelector('#fund-chart svg').onpointermove=e=>{const box=e.currentTarget.getBoundingClientRect(),px=(e.clientX-box.left)/box.width*W;let nearest=0;rows.forEach((r,i)=>{if(Math.abs(x(r.date)-px)<Math.abs(x(rows[nearest].date)-px))nearest=i;});show(nearest);};
 show(Math.max(0,selectedDate?rows.findIndex(r=>r.date===selectedDate):rows.length-1));
}

export function updateFundStatus(root,f){
 const node=root.querySelector('#fund-source-status');if(!node)return;
 const live=f?.liveSource;node.classList.toggle('source-stale',live?.status==='stale');
 node.textContent=!f?.source?.live?'已匯入試算表資料':live?.status==='ok'?'已連線 Google 試算表 · 每 60 秒檢查 · 最近確認 '+stamp(live.checkedAt)+'（台北）':live?.status==='stale'?'試算表尚未更新 · '+live.error+'；保留上次成功資料，稍後重試。':'正在確認 Google 試算表更新…';
}
