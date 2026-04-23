#!/usr/bin/env python3
"""台股每日晨報 — GitHub Actions 雲端版"""

import json, re, os, smtplib, base64, urllib.request, urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta

HTML_PATH  = 'index.html'
EMAIL_FROM = 'laiyingju0831@gmail.com'
EMAIL_TO   = os.environ.get('EMAIL_TO', 'laibrain168@gmail.com')
EMAIL_PASS = os.environ.get('EMAIL_PASSWORD', '')
PAGES_URL  = 'https://laiyingju.github.io/taiwan-stock-report/'

STOCKS = {
    '兆赫':  {'symbol': '2485.TW',  'entry': [62, 68],  'target15': 82.8,  'stop': 58,  'code': '2485'},
    '華邦電': {'symbol': '2344.TW',  'entry': [82, 86],  'target15': 101.2, 'stop': 76,  'code': '2344'},
    '瀧澤科': {'symbol': '6609.TWO', 'entry': [36, 39],  'target15': 46.0,  'stop': 33,  'code': '6609'},
}
US_REFS = {'SOX': '^SOX', 'SMH': 'SMH', 'NVDA': 'NVDA', 'MU': 'MU'}
WATCHLIST = {
    '旺宏':   {'symbol': '2337.TW',  'code': '2337', 'theme': 'NOR Flash',    'note': 'AI IoT / 車用記憶體，報價持續上漲'},
    '台灣大': {'symbol': '3045.TW',  'code': '3045', 'theme': '5G + AI 企業', 'note': 'AI 企業連網需求，現金流穩定高殖利率'},
    '富鼎':   {'symbol': '8261.TW',  'code': '8261', 'theme': 'AI 電源 IC',   'note': 'AI 伺服器電源管理晶片，毛利率擴張中'},
    '新唐':   {'symbol': '4919.TW',  'code': '4919', 'theme': 'AI 邊緣 MCU',  'note': 'ARM MCU for AI edge / 車用 / IoT'},
    '晶豪科': {'symbol': '3006.TW',  'code': '3006', 'theme': 'NAND 控制器',  'note': 'SSD 控制晶片，AI 儲存需求受惠'},
    '中磊':   {'symbol': '5388.TW',  'code': '5388', 'theme': 'WiFi 7 網通',  'note': 'WiFi 6/7 路由器晶片，AI 家用流量爆增'},
    '台揚':   {'symbol': '2402.TW',  'code': '2402', 'theme': 'Cable 設備',   'note': '同兆赫產業鏈，DOCSIS 升級受惠，估值較低'},
    '世界先進': {'symbol': '5347.TWO', 'code': '5347', 'theme': '特殊晶圓代工', 'note': 'BCD 製程，AI 伺服器電源 IC 主要代工廠'},
    '弘塑':   {'symbol': '6706.TW',  'code': '6706', 'theme': 'CoWoS 封裝設備','note': '外資近期調升目標價，先進封裝設備唯一純粹標的'},
    '力積電': {'symbol': '6770.TW',  'code': '6770', 'theme': '特殊 DRAM',    'note': '利基型 DRAM 晶圓代工，低基期具彈性'},
}
SUPPLY_CHAIN = {
    '台積電': '2330.TW', '環球晶': '6488.TW', '台達電': '2308.TW',
    '廣達': '2382.TW',  '智邦': '2345.TW',  '中華電': '2412.TW',
    '緯穎': '6669.TW',  '威剛': '3260.TW',  '華邦電': '2344.TW',
    '新唐': '4919.TW',  '中磊': '5388.TW',  '台揚': '2402.TW',
    '世界先進': '5347.TWO', '富鼎': '8261.TW',
    '雙鴻': '3324.TW',  '奇鋐': '3017.TW',  '旺宏': '2337.TW',
    '緯創': '3231.TW',  '遠傳': '4904.TW',  '健策': '3306.TWO',
    '力積電': '6770.TW', '晶豪科': '3006.TW',
}

def fetch_stock_data():
    import yfinance as yf
    result = {}
    end = datetime.now()
    start = end - timedelta(days=400)
    for name, info in STOCKS.items():
        try:
            hist = yf.Ticker(info['symbol']).history(start=start, end=end)
            if len(hist) == 0: continue
            closes = [round(float(p), 1) for p in hist['Close']]
            dates  = [d.strftime('%Y-%m-%d') for d in hist.index]
            current = closes[-1]
            prev    = closes[-2] if len(closes) > 1 else current
            ma5 = round(sum(closes[-5:]) / min(5, len(closes)), 1)
            result[name] = {
                'symbol': info['symbol'], 'code': info['code'],
                'dates': dates[-250:], 'prices': closes[-250:],
                'current': current, 'prev_close': prev,
                'change_pct': round((current - prev) / prev * 100, 2),
                'ma5': ma5, 'momentum': 'up' if current > ma5 else 'down',
                'entry': info['entry'], 'target15': info['target15'], 'stop': info['stop'],
            }
            print(f'  ✅ {name} {current}')
        except Exception as e:
            print(f'  ❌ {name}: {e}')
    return result

def fetch_us_data():
    import yfinance as yf
    result = {}
    for name, symbol in US_REFS.items():
        try:
            hist = yf.Ticker(symbol).history(period='5d')
            if len(hist) < 2: continue
            prev = float(hist['Close'].iloc[-2])
            last = float(hist['Close'].iloc[-1])
            chg  = round((last - prev) / prev * 100, 2)
            result[name] = {'price': round(last, 2), 'change_pct': chg, 'date': hist.index[-1].strftime('%Y-%m-%d')}
        except: pass
    return result

def fetch_watchlist_data():
    import yfinance as yf
    result = {}
    for name, info in WATCHLIST.items():
        try:
            hist = yf.Ticker(info['symbol']).history(period='5d')
            if len(hist) < 1: continue
            closes = [round(float(p), 1) for p in hist['Close']]
            current = closes[-1]; prev = closes[-2] if len(closes) > 1 else current
            result[name] = {
                'symbol': info['symbol'], 'code': info['code'],
                'theme': info['theme'], 'note': info['note'],
                'current': current, 'change_pct': round((current - prev) / prev * 100, 2),
            }
        except: pass
    return result

def fetch_supply_chain():
    import yfinance as yf
    result = {}
    for name, symbol in SUPPLY_CHAIN.items():
        try:
            h = yf.Ticker(symbol).history(period='5d')
            if len(h) < 1: continue
            closes = [round(float(p), 1) for p in h['Close']]
            current = closes[-1]; prev = closes[-2] if len(closes) > 1 else current
            result[name] = {'current': current, 'change_pct': round((current - prev) / prev * 100, 2), 'code': symbol.split('.')[0]}
        except: pass
    return result

def generate_prediction(stock_data, us_data):
    predictions = {}
    sox = us_data.get('SOX', {}).get('change_pct', 0)
    smh = us_data.get('SMH', {}).get('change_pct', 0)
    us_sent = (sox + smh) / 2
    for name, d in stock_data.items():
        c = d['current']
        pred = round(c + c * us_sent * 0.006 + c * (0.004 if d['momentum'] == 'up' else -0.003), 1)
        signal = '偏多' if pred > c else ('偏空' if pred < c * 0.99 else '盤整')
        predictions[name] = {'price': pred, 'signal': signal, 'color': 'green' if pred > c else ('red' if pred < c * 0.99 else 'orange')}
    return predictions

def update_html(stock_data, us_data, predictions, watchlist_data=None, supply_chain_data=None):
    try:
        with open(HTML_PATH, 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        print(f'❌ 找不到 {HTML_PATH}'); return False
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    payload = {
        'updated': now, 'stocks': stock_data, 'us_market': us_data,
        'predictions': predictions, 'watchlist': watchlist_data,
        'supply_chain': supply_chain_data or {},
        'ai_analysis': '（GitHub Actions 自動更新）',
    }
    new_block = '// DAILY_DATA_START\nconst DAILY_DATA = ' + json.dumps(payload, ensure_ascii=False, indent=2) + ';\n// DAILY_DATA_END'
    new_html = re.sub(r'// DAILY_DATA_START.*?// DAILY_DATA_END', new_block, html, flags=re.DOTALL)
    if new_html == html:
        print('⚠ 找不到 DAILY_DATA 標記'); return False
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f'✅ HTML 更新完成: {now}')
    return True

def send_email(stock_data, us_data, predictions, watchlist_data=None):
    if not EMAIL_PASS:
        print('⚠ 無 EMAIL_PASSWORD，跳過發信'); return
    today = datetime.now().strftime('%Y-%m-%d')
    stock_rows = ''
    for name, d in stock_data.items():
        chg = d['change_pct']; color = '#27ae60' if chg >= 0 else '#e74c3c'
        arrow = '▲' if chg >= 0 else '▼'
        pred = predictions.get(name, {})
        stock_rows += f'<tr><td style="padding:10px;border-bottom:1px solid #eee;font-weight:700">{name}（{d["code"]}）</td><td style="padding:10px;border-bottom:1px solid #eee;font-weight:700">${d["current"]}</td><td style="padding:10px;border-bottom:1px solid #eee;color:{color};font-weight:700">{arrow}{abs(chg):.2f}%</td><td style="padding:10px;border-bottom:1px solid #eee">${pred.get("price","—")}（{pred.get("signal","—")}）</td></tr>'
    us_rows = ''
    for name, d in us_data.items():
        chg = d['change_pct']; color = '#27ae60' if chg >= 0 else '#e74c3c'
        arrow = '▲' if chg >= 0 else '▼'
        us_rows += f'<tr><td style="padding:8px;border-bottom:1px solid #eee">{name}</td><td style="padding:8px;border-bottom:1px solid #eee">{d.get("price","—")}</td><td style="padding:8px;border-bottom:1px solid #eee;color:{color}">{arrow}{abs(chg):.2f}%</td></tr>'
    wl_rows = ''
    if watchlist_data:
        for name, d in watchlist_data.items():
            chg = d['change_pct']; color = '#27ae60' if chg >= 0 else '#e74c3c'
            arrow = '▲' if chg >= 0 else '▼'
            wl_rows += f'<tr><td style="padding:8px;border-bottom:1px solid #eee">{name}（{d["code"]}）</td><td style="padding:8px;border-bottom:1px solid #eee;color:#555">{d["theme"]}</td><td style="padding:8px;border-bottom:1px solid #eee">${d["current"]}</td><td style="padding:8px;border-bottom:1px solid #eee;color:{color}">{arrow}{abs(chg):.2f}%</td></tr>'
    wl_section = f'<h2 style="color:#333;border-bottom:2px solid #43a047;padding-bottom:8px;margin-top:28px">👀 觀察名單</h2><table style="width:100%;border-collapse:collapse;margin-bottom:24px"><tr style="background:#f5f5f5"><th style="padding:8px;text-align:left">股票</th><th style="padding:8px;text-align:left">主題</th><th style="padding:8px;text-align:left">現價</th><th style="padding:8px;text-align:left">漲跌</th></tr>{wl_rows}</table>' if wl_rows else ''
    html_body = f"""<html><body style="font-family:'PingFang TC',Arial,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#222">
  <div style="background:linear-gradient(135deg,#e53935,#1e88e5);padding:24px 28px;border-radius:16px;color:white;margin-bottom:24px">
    <h1 style="margin:0;font-size:1.5rem;letter-spacing:2px">📊 台股每日晨報</h1>
    <p style="margin:6px 0 0;opacity:0.85;font-size:0.95rem">{today} ｜ 兆赫 · 華邦電 · 瀧澤科</p>
  </div>
  <h2 style="color:#333;border-bottom:2px solid #e53935;padding-bottom:8px">🇹🇼 主力持股</h2>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px"><tr style="background:#f5f5f5"><th style="padding:10px;text-align:left">股票</th><th style="padding:10px;text-align:left">現價</th><th style="padding:10px;text-align:left">漲跌</th><th style="padding:10px;text-align:left">今日預測</th></tr>{stock_rows}</table>
  <h2 style="color:#333;border-bottom:2px solid #1e88e5;padding-bottom:8px">🇺🇸 美股前一日</h2>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px"><tr style="background:#f5f5f5"><th style="padding:8px;text-align:left">指數/股票</th><th style="padding:8px;text-align:left">收盤價</th><th style="padding:8px;text-align:left">漲跌</th></tr>{us_rows}</table>
  {wl_section}
  <div style="text-align:center;margin:24px 0 8px">
    <a href="{PAGES_URL}" style="display:inline-block;background:linear-gradient(135deg,#e53935,#1e88e5);color:white;text-decoration:none;padding:14px 36px;border-radius:50px;font-size:1.05rem;font-weight:700;letter-spacing:1px">📊 開啟完整互動報告</a>
    <div style="margin-top:8px;font-size:0.8rem;color:#aaa">{PAGES_URL}</div>
  </div>
  <div style="background:#fff8e1;border-radius:12px;padding:14px 18px;font-size:0.82rem;color:#795548;margin-top:8px;line-height:1.7">
    ⏱ 每日 08:30 自動更新（平日）｜ 純屬參考，理性操作 🙏
  </div>
</body></html>"""
    msg = MIMEMultipart('mixed')
    msg['Subject'] = f'📊 台股晨報 {today} ｜ 兆赫 · 華邦電 · 瀧澤科'
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.ehlo(); s.starttls(); s.login(EMAIL_FROM, EMAIL_PASS); s.send_message(msg)
        print(f'✅ 晨報已發送至 {EMAIL_TO}')
    except Exception as e:
        print(f'❌ 發信失敗：{e}')

if __name__ == '__main__':
    print(f'\n{"="*50}\n📊 台股晨報更新 — {datetime.now().strftime("%Y-%m-%d %H:%M")}\n{"="*50}\n')
    print('🇹🇼 抓取台股...')
    stock_data = fetch_stock_data()
    print('\n🇺🇸 抓取美股...')
    us_data = fetch_us_data()
    print('\n👀 抓取觀察名單...')
    watchlist_data = fetch_watchlist_data()
    print('\n🔗 抓取供應鏈...')
    supply_chain_data = fetch_supply_chain()
    if stock_data:
        predictions = generate_prediction(stock_data, us_data)
        update_html(stock_data, us_data, predictions, watchlist_data, supply_chain_data)
        send_email(stock_data, us_data, predictions, watchlist_data)
    print(f'\n{"="*50}\n')
