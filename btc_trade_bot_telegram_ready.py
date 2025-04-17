
import pandas as pd
import requests
import schedule
import time
from binance.client import Client
from datetime import datetime, timedelta
import pytz

# Cấu hình
API_KEY = ''
API_SECRET = ''
TELEGRAM_BOT_TOKEN = '7649149703:AAEdfU1rPOlTNJpXa_6nAe_kQK5TuOGMR8U'
TELEGRAM_CHAT_ID = '142194645'

client = Client(API_KEY, API_SECRET)

# Lấy dữ liệu nến 6h
def get_klines():
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=10)
    klines = client.get_klines(
        symbol='BTCUSDT',
        interval=Client.KLINE_INTERVAL_6HOUR,
        start_str=start_time.strftime('%d %b %Y %H:%M:%S'),
        end_str=end_time.strftime('%d %b %Y %H:%M:%S')
    )
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'trades', 'taker_buy_vol', 'taker_buy_qav', 'ignore'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # Chuyển sang giờ GMT+7
    df['open_time'] = df['open_time'].dt.tz_localize('UTC').dt.tz_convert('Asia/Bangkok')
    
    return df

# Phân loại volume
def classify_volume(df):
    df['vol_avg'] = df['volume'].rolling(window=20).mean()
    def vol_type(row):
        if row['volume'] < 0.5 * row['vol_avg']:
            return 'thấp'
        elif row['volume'] <= row['vol_avg']:
            return 'vừa'
        else:
            return 'cao'
    df['vol_type'] = df.apply(vol_type, axis=1)
    return df

# So sánh hướng nến
def candle_direction(row):
    return 'tăng' if row['close'] > row['open'] else 'giảm'

# Phân tích chiến lược
def analyze(df):
    df['dir'] = df.apply(candle_direction, axis=1)
    today = df[df['open_time'].dt.date == datetime.now(pytz.timezone("Asia/Bangkok")).date()]
    yesterday = df[df['open_time'].dt.date == (datetime.now(pytz.timezone("Asia/Bangkok")).date() - timedelta(days=1))]
    
    if len(today) < 2 or len(yesterday) < 4:
        return "Không đủ dữ liệu để phân tích."

    msg = f"📊 Dự báo BTC 6H - {datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M')}:\n"
    
    n1, n2 = today.iloc[0], today.iloc[1]
    n3t, n4t = yesterday.iloc[2], yesterday.iloc[3]

    # Rule 1: 4t vol thấp → nến 1 hôm nay ngược hướng 3t
    if n4t['vol_type'] == 'thấp':
        expected = 'tăng' if n3t['dir'] == 'giảm' else 'giảm'
        msg += f"• Nến 4 hôm trước có KL thấp → Dự đoán nến 1 hôm nay sẽ {expected}:\n"

    # Rule 2: 4t và 1 vol thấp → nến 2 cùng hướng 3t
    if n4t['vol_type'] == 'thấp' and n1['vol_type'] == 'thấp':
        msg += f"• Nến 4t & 1 vol thấp → Dự đoán nến 2 hôm nay sẽ {n3t['dir']}:\n"

    # Rule 3: nến 2 vol thấp → nến 3 cùng hướng nến 1
    if n2['vol_type'] == 'thấp':
        msg += f"• Nến 2 vol thấp → Dự đoán nến 3 hôm nay sẽ {n1['dir']}:\n"

    return msg

# Gửi tin nhắn Telegram
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload)
        print(f"📨 Telegram status: {r.status_code}, response: {r.text}")
    except Exception as e:
        print(f"❌ Lỗi gửi telegram: {e}")

# Tổng hợp và gửi
def job():
    try:
        df = get_klines()
        df = classify_volume(df)
        message = analyze(df)
        send_telegram(message)
    except Exception as e:
        send_telegram(f"❌ Lỗi khi chạy bot: {e}")

# Gửi tin nhắn khi khởi động bot
send_telegram("🤖 Bot dự đoán 6H bắt đầu...")

# Lên lịch chạy mỗi 6 tiếng (giờ GMT+7)
schedule.every().day.at("07:05").do(job)
schedule.every().day.at("13:05").do(job)
schedule.every().day.at("19:05").do(job)
schedule.every().day.at("01:05").do(job)

print("⏳ Bot đã sẵn sàng chạy tự động mỗi 6 tiếng...")

while True:
    schedule.run_pending()
    time.sleep(60)
