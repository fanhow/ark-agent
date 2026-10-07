import {h,safeURL} from './lib.js';

const RESEARCH='https://stable-value.fanhow.chatgpt.site/sentiment';
const fmt=(n,d=2)=>Number.isFinite(n)?n.toLocaleString('zh-TW',{maximumFractionDigits:d,minimumFractionDigits:d}):'待更新';
const link=(url,label)=>`<a href="${h(safeURL(url))}" target="_blank" rel="noopener noreferrer">${h(label)} ↗</a>`;

export function macroReading(item){
 if(!Number.isFinite(item.value))return '來源尚未取得，保留空值；請先查看完整研究或稍後更新。';
 if(!Number.isFinite(item.change))return '只有單期數值，尚無法比較方向。';
 if(item.id==='yen')return item.change<0?'USD/JPY 下降，代表日圓升值；仍須核對美日利差與政策。':item.change>0?'USD/JPY 上升，代表日圓貶值；本期不宜將日圓視為已發揮避險效果。':'USD/JPY 持平；沒有明確的單期匯率方向。';
 if(item.id==='vix')return item.change>0?'預期波動升高；再對照金融情勢與穩盈的波動率期限結構。':item.change<0?'預期波動下降；仍需核對信用市場，不能直接推論股市上漲。':'預期波動持平；仍需對照金融情勢與期限結構。';
 if(item.id==='conditions')return (item.value>0?'高於歷史平均，金融情勢較緊。':item.value<0?'低於歷史平均，金融情勢較寬鬆。':'與歷史平均相同。')+(item.change>0?'相較上週走緊，仍須區分變動與水準。':item.change<0?'相較上週放鬆，仍不代表沒有風險。':'與上週持平。');
 if(item.id==='realYield')return item.change>0?'實質殖利率上升，無息黃金的機會成本增加。':item.change<0?'實質殖利率下降，無息黃金的機會成本降低。':'實質殖利率持平；再觀察美元與資金需求。';
 if(item.id==='oil')return '先分辨供給衝擊與需求變化；油價漲跌本身不足以判定景氣或避險成效。';
 if(item.id==='dollar')return '搭配實質利率與商品看美元壓力；廣義美元指數的成分與 DXY 不同。';
 return '把金價與實質利率、美元一起看；只有價格變動，還不能確認背後原因。';
}

function sparkline(item){
 const points=(item.history||[]).filter(p=>Number.isFinite(p.value));
 if(points.length<2)return '<div class="macro-chart-empty small muted">歷史走勢待更新</div>';
 const min=Math.min(...points.map(p=>p.value)),max=Math.max(...points.map(p=>p.value));
 const coords=points.map((p,i)=>`${(i/(points.length-1)*280+4).toFixed(1)},${(max===min?30:52-(p.value-min)/(max-min)*44).toFixed(1)}`).join(' ');
 return `<svg class="macro-spark" viewBox="0 0 288 60" role="img" aria-label="${h(item.label)}：${h(points[0].date)} 至 ${h(points.at(-1).date)}，${points.length} 筆觀測；各圖獨立刻度"><path d="M4 56H284"/><polyline points="${coords}"/></svg><span class="macro-chart-caption">${h(points[0].date)} — ${h(points.at(-1).date)} · 各圖獨立刻度</span>`;
}

function card(item){
 const precision=item.id==='conditions'?3:2,available=Number.isFinite(item.value),change=Number.isFinite(item.change)?`${item.change>0?'↑ +':item.change<0?'↓ ':''}${fmt(item.change,precision)} ${h(item.changeUnit)}`:'變動待更新';
 return `<article class="macro-card" data-macro-id="${h(item.id)}"><div class="macro-card-top"><span class="eyebrow">${h(item.role)}</span><span class="macro-age">${available?`距盤勢日 ${h(item.ageDays)} 天`:'來源待更新'}</span></div><h3>${h(item.label)}</h3><div class="macro-value mono">${fmt(item.value,precision)} <span>${available?h(item.unit):''}</span></div><div class="macro-change mono">${change}</div><div class="small muted">觀測 ${h(item.asOf||'待更新')} · 比較 ${h(item.previousAsOf||'待更新')}</div>${sparkline(item)}<p class="macro-reading">${h(macroReading(item))}</p><details><summary>用途、限制與來源</summary><p>${h(item.framework)}</p>${item.contract?`<p>來源標示合約：${h(item.contract)}</p>`:''}<p>${h(item.note)}</p><p>擷取 ${h(item.fetchedAt||'待更新')}</p><div class="macro-links">${link(item.source,'行情資料')}${link(item.reference,'指標說明')}</div></details></article>`;
}

export function renderMacro(radar){
 const items=radar?.items||[],main=items.filter(x=>['gold','oil','yen','vix'].includes(x.id)),drivers=items.filter(x=>['realYield','conditions','dollar'].includes(x.id));
 return `<section class="panel macro-panel" aria-labelledby="macro-radar-title"><div class="section-head"><div><div class="eyebrow">CROSS-ASSET RADAR</div><h2 id="macro-radar-title">避險資產與總經雷達</h2></div><span class="small muted">看條件，也看風險傳導</span></div>
 <p class="macro-intro">黃金看機會成本，原油看供需，日圓看利差，VIX 看波動。把它們放在一起，辨識風險來自哪裡。</p>
 <a class="research-bridge" href="${RESEARCH}" target="_blank" rel="noopener noreferrer"><span><span class="eyebrow">穩盈公允價值 · 共用研究入口</span><strong>開啟完整市場情緒研究 ↗</strong><span>VIX9D／VIX／VIX3M、期限結構與資金流觀點</span></span><span class="research-arrow" aria-hidden="true">↗</span></a>
 <p class="small muted">完整研究沿用穩盈原頁與登入權限；此處為每日獨立行情摘要，更新時間可能不同。</p>
 ${items.length?`<div class="macro-cards">${main.map(card).join('')}</div><div class="macro-driver-heading"><h3>再看三個背後的推力</h3><span class="small muted">利率 × 金融情勢 × 美元</span></div><div class="macro-cards macro-drivers">${drivers.map(card).join('')}</div>`:'<p class="empty">這份歷史日報尚無跨資產資料；可先開啟穩盈研究，或切換至最新盤勢。</p>'}
 <div class="actions"><button data-macro-ask>請船員解讀這些指標 ↗</button></div><details class="macro-scenarios"><summary>怎麼把指標放在一起看？</summary><div class="scenario-grid"><div><h3>供給衝擊與通膨</h3><p>原油上升時，核對供給中斷與通膨消息。若利率同升，股票與債券可能一起承壓，黃金也未必同步受益。</p></div><div><h3>成長放緩與信用壓力</h3><p>VIX 上升、每週金融情勢也走緊，值得進一步查核企業融資與景氣；原油若走弱，也要分辨需求與供給原因。</p></div><div><h3>套利平倉與流動性</h3><p>日圓升值伴隨波動上升時，留意套利部位平倉的可能性；需要同日證據，不能只靠兩條走勢確認因果。</p></div></div><p class="small muted">以上為條件式觀察框架，未判定目前屬於哪種情境，也不直接改動庫存水位規則。</p></details>
 <p class="macro-footnote small muted">${h(radar?.note||'各來源依實際觀測日期顯示，缺資料不補成零。')} 基點是百分之一個百分點；所有變動比較前次有效觀測，並非股市漲跌訊號。</p></section>`;
}
