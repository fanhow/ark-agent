import {accountValues,pnlTotal} from './lib.js';

export const FUND_NUMBERS=['totalAssets','stockMarketValue','stockCost','fundPnl','holdingsPnl','dailyPnl','taiwanPnl','usPnl'];
export const FUND_COLUMNS=[['date','日期'],['totalAssets','基金總資產'],['stockMarketValue','目前總持倉'],['stockCost','持倉成本'],['fundPnl','基金累計績效'],['holdingsPnl','持倉累計績效'],['dailyPnl','今日績效'],['taiwanPnl','台股累計績效'],['usPnl','美股累計績效'],['screenshots','來源截圖'],['notes','備註']];
const dateOK=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s;
const timeOK=s=>typeof s==='string'&&/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(s)&&Number.isFinite(Date.parse(s));
export function validateFund(f){
 if(!f||f.version!==1||f.currency!=='TWD'||typeof f.name!=='string'||f.name.length>100)throw Error('基金格式無效');
 if(!f.source||!timeOK(f.source.modifiedAt)||!timeOK(f.source.importedAt)||!['title','url','sheet'].every(k=>typeof f.source[k]==='string'&&f.source[k].length<=2000))throw Error('基金來源無效');
 const url=new URL(f.source.url);if(url.protocol!=='https:'||url.hostname!=='docs.google.com'||!url.pathname.startsWith('/spreadsheets/d/'))throw Error('基金來源須為 Google 試算表');
 if(!Array.isArray(f.records)||!f.records.length||f.records.length>5000||new Set(f.records.map(r=>r.date)).size!==f.records.length)throw Error('基金日期重複或筆數無效');
 for(const r of f.records){if(!dateOK(r.date)||!FUND_NUMBERS.every(k=>r[k]===null||(typeof r[k]==='number'&&Number.isFinite(r[k])))||!['screenshots','notes'].every(k=>typeof r[k]==='string'&&r[k].length<=20000))throw Error('基金明細無效');}
 if(!f.capital||typeof f.capital.initial!=='number'||!Number.isFinite(f.capital.initial)||f.capital.initial<0||!timeOK(f.capital.confirmedAt)||!Array.isArray(f.capital.events)||f.capital.events.length>1000)throw Error('本金格式無效');
 for(const e of f.capital.events)if(!dateOK(e.date)||typeof e.amount!=='number'||!Number.isFinite(e.amount)||typeof e.note!=='string'||e.note.length>2000)throw Error('入出金格式無效');
 if(f.source.live!==undefined&&typeof f.source.live!=='boolean')throw Error('基金自動更新設定無效');
 if(f.records.some(r=>r.updatedAt!==undefined&&!timeOK(r.updatedAt)))throw Error('基金欄位更新時間無效');
 if(!Array.isArray(f.notes)||f.notes.length>100||f.notes.some(n=>typeof n!=='string'||n.length>5000))throw Error('基金註記無效');
 return f;
}
export const orderedRecords=f=>[...f.records].sort((a,b)=>a.date.localeCompare(b.date));
export const capitalAt=(f,date)=>f.capital.initial+f.capital.events.filter(e=>e.date<=date).reduce((a,e)=>a+e.amount,0);
export function newer(a,b){
 if(!a?.date)return b;if(!b?.date)return a;
 if(a.date!==b.date)return a.date>b.date?a:b;
 const at=Date.parse(a.updatedAt),bt=Date.parse(b.updatedAt);
 // A missing timestamp cannot establish that an equal-date source is newer.
 return Number.isFinite(at)&&Number.isFinite(bt)&&bt>at?b:a;
}
export function fundSummary(f,p){
 const latest=orderedRecords(f).at(-1),v=accountValues(p),total=pnlTotal(p);
 const sheet={date:latest.date,updatedAt:latest.updatedAt||f.source.modifiedAt,source:'每日績效',kind:'sheet'};
 const photo={date:p.accountSnapshot?.asOf||p.asOf,updatedAt:p.accountSnapshot?.recordedAt,source:'已確認照片',kind:'photo'};
 const choose=(key,value,extra={})=>{
  const a={...photo,value,...extra},b={...sheet,value:latest[key]};
  if(a.value==null&&b.value==null)return newer(a,b);
  if(a.value==null)return b;if(b.value==null)return a;
  return newer(a,b);
 };
 return {latest,total,
  totalAssets:choose('totalAssets',v.totalAssets,{change:v.totalAssetsChange,percent:v.totalAssetsChangePercent}),
  stockMarketValue:choose('stockMarketValue',v.stockMarketValue),stockCost:choose('stockCost',v.stockCost),
  dailyPnl:choose('dailyPnl',v.dailyPnl,{percent:v.dailyPnlPercent}),
  holdingsPnl:(()=>{const a={date:p.asOf,updatedAt:p.accountSnapshot?.recordedAt,source:'網站持股加總',kind:'positions',value:total.complete?total.sum:null},b={...sheet,value:latest.holdingsPnl};return a.value==null?b:b.value==null?a:newer(a,b);})(),
  fundPnl:{...sheet,value:latest.fundPnl},taiwanPnl:{...sheet,value:latest.taiwanPnl},usPnl:{...sheet,value:latest.usPnl}
 };
}
