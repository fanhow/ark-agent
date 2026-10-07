"""Public cross-asset observations; units, dates and conditional readings stay explicit."""
import concurrent.futures
import csv
import io
import json
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SENTIMENT_URL = 'https://stable-value.fanhow.chatgpt.site/sentiment'
SPECS = [
    dict(id='gold', label='黃金期貨', series='GC=F', unit='美元／金衡盎司', changeUnit='%', role='分散風險',
         framework='黃金沒有利息收入，應搭配實質利率、美元與避險需求觀察；流動性緊縮時也可能被賣出。期貨有轉倉與基差，不等同現貨或持有報酬。',
         reference='https://www.gold.org/goldhub/research/relevance-of-gold-as-a-strategic-asset'),
    dict(id='oil', label='WTI 原油現貨', series='DCOILWTICO', unit='美元／桶', changeUnit='%', role='通膨與供需',
         framework='原油可反映供給衝擊與需求景氣。供給中斷可能推高油價；衰退需求減弱時可能下跌，不是通用避險資產。',
         reference='https://www.eia.gov/finance/markets/products/trade.php'),
    dict(id='yen', label='日圓 USD/JPY', series='DEXJPUS', unit='日圓／美元', changeUnit='%', role='利差與套利平倉',
         framework='報價是每美元可換多少日圓：數值下降＝日圓升值。觀察美日利差、央行政策與套利平倉；日圓並非每次市場下跌都會升值。',
         reference='https://www.bis.org/publ/qtrpdf/r_qt2409a.pdf'),
    dict(id='vix', label='VIX 波動率', series='VIXCLS', unit='點', changeUnit='點', role='選擇權風險定價',
         framework='VIX 反映 S&P 500 未來約 30 天的年化隱含波動率。上升表示預期波動加大，不是下跌機率；下降也不保證股市上漲。VIX 指數不能直接持有。',
         reference='https://www.cboe.com/tradable-products/vix/'),
    dict(id='realYield', label='美國 10 年實質殖利率', series='DFII10', unit='%', changeUnit='基點', role='持有黃金的機會成本',
         framework='使用通膨連結公債殖利率。上升通常提高持有無息黃金的機會成本，也可能壓抑長期成長股估值；不是唯一驅動因素。',
         reference='https://fred.stlouisfed.org/series/DFII10'),
    dict(id='conditions', label='Chicago Fed 金融情勢', series='NFCI', unit='標準差', changeUnit='標準差', role='每週信用與流動性',
         framework='Chicago Fed NFCI 為每週指數，整合風險、信用與槓桿。正值表示比歷史平均緊縮，負值表示較寬鬆；變動與水準不同，不能將負值當作沒有風險。',
         reference='https://www.chicagofed.org/research/data/nfci/background'),
    dict(id='dollar', label='Fed 廣義美元指數', series='DTWEXBGS', unit='指數', changeUnit='%', role='全球資金與匯率',
         framework='貿易加權的廣義美元指數，不是 DXY。美元轉強可提高非美元買方購買美元計價商品的成本，應與利率及資金需求一起解讀。',
         reference='https://fred.stlouisfed.org/series/DTWEXBGS'),
]


def observation(spec, points, day, fetched_at, source, note, contract=None):
    # Ignore future rows, missing values and duplicates; never convert unavailable to zero.
    cutoff = datetime.fromisoformat(day).date()
    clean = {}
    for d, v in points:
        date = datetime.fromisoformat(d).date()
        if date < cutoff and isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v):
            clean[d] = v
    points = sorted(clean.items())
    if not points:
        raise ValueError('沒有可用觀測')
    d, value = points[-1]
    prior = points[-2] if len(points) > 1 else None
    change = None
    if prior:
        if spec['changeUnit'] == '%':
            if prior[1] > 0:
                change = (value / prior[1] - 1) * 100
        else:
            change = (value - prior[1]) * (100 if spec['changeUnit'] == '基點' else 1)
    return {**spec, 'value': value, 'change': round(change, 3) if change is not None else None,
            'asOf': d, 'previousAsOf': prior[0] if prior else None,
            'ageDays': (cutoff - datetime.fromisoformat(d).date()).days,
            'source': source, 'fetchedAt': fetched_at, 'note': note, 'contract': contract,
            'history': [{'date': date, 'value': val} for date, val in points[-21:]],
            'status': 'available'}


def collect_one(spec, day, fetch, fetched_at, clock):
    start = (datetime.fromisoformat(day) - timedelta(days=180)).date().isoformat()
    source = (f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={spec["series"]}&cosd={start}&coed={day}'
              if spec['id'] != 'gold' else
              'https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1d&range=3mo')
    try:
        if spec['id'] == 'gold':
            data = json.loads(fetch(source))['chart']['result'][0]
            meta = data['meta']
            if meta.get('instrumentType') != 'FUTURE' or meta.get('currency') != 'USD':
                raise ValueError('黃金報價種類或幣別改變')
            tz = ZoneInfo(meta['exchangeTimezoneName'])
            # Futures trade beyond the equity close. Exclude the exchange's entire
            # current calendar day; do not reuse the NY 16:15 equity-close assumption.
            exchange_day = clock.astimezone(tz).date().isoformat()
            points = [(datetime.fromtimestamp(ts, tz).date().isoformat(), v)
                      for ts, v in zip(data['timestamp'], data['indicators']['quote'][0]['close'])
                      if datetime.fromtimestamp(ts, tz).date().isoformat() < exchange_day]
            note = 'Yahoo Finance GC=F 日 K；保守排除交易所當日資料。連續報價可能換月，單次漲跌不是可實現持有報酬。'
            return observation(spec, points, day, fetched_at, source, note, meta.get('shortName'))
        rows = csv.DictReader(io.StringIO(fetch(source)))
        points = [(r.get('DATE') or r.get('observation_date'), float(r[spec['series']]))
                  for r in rows if r.get(spec['series']) not in (None, '', '.')]
        note = ('每週資料，變動比較上期週值。' if spec['id'] == 'conditions' else '') + 'FRED 最新可取得的歷史觀測；發布可能落後，非即時報價。變動比較相鄰有效觀測，未必是前一個曆日。'
        return observation(spec, points, day, fetched_at, source, note)
    except Exception as error:
        return {**spec, 'value': None, 'change': None, 'asOf': None, 'previousAsOf': None,
                'ageDays': None, 'source': source, 'fetchedAt': fetched_at,
                'note': '查不到／待更新：' + type(error).__name__, 'history': [], 'status': 'unavailable'}


def collect(day, fetch, fetched_at, clock=None):
    clock = clock or datetime.now(ZoneInfo('Asia/Taipei'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        items = list(pool.map(lambda spec: collect_one(spec, day, fetch, fetched_at, clock), SPECS))
    return {'items': items, 'researchUrl': SENTIMENT_URL,
            'note': '各市場觀測日期不同，請勿視為同日同步訊號。箭頭只表示數值變動，沒有合成買賣分數。歷史資料可能修訂，不作當時可知資料的回測。'}
