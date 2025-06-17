import os
import time
import threading
import datetime
import requests
import numpy as np
from flask import Flask
import telebot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

COINS = ["bitcoin", "ethereum", "solana", "binancecoin"]
VS_CURRENCY = "usd"
LOOP_MINUTES = 10

# Validations
if not TOKEN or not CHAT_ID:
    raise Exception("❌ Telegram token or chat ID not set!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Crypto Signal Bot Running with CoinGecko"

# ====== RSI & MACD Calculation =======
def calculate_rsi(prices, period=14):
    prices = np.array(prices)
    deltas = np.diff(prices)
    gain = np.where(deltas > 0, deltas, 0)
    loss = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.convolve(gain, np.ones(period)/period, mode='valid')
    avg_loss = np.convolve(loss, np.ones(period)/period, mode='valid')
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi[-1] if len(rsi) else 50

def calculate_macd(prices, short=12, long=26, signal=9):
    short_ema = np.convolve(prices, np.ones(short)/short, mode='valid')
    long_ema = np.convolve(prices, np.ones(long)/long, mode='valid')
    macd_line = short_ema[-len(long_ema):] - long_ema
    signal_line = np.convolve(macd_line, np.ones(signal)/signal, mode='valid')
    histogram = macd_line[-len(signal_line):] - signal_line
    return macd_line[-1], signal_line[-1], histogram[-1]

# ====== Fetch Prices from CoinGecko =======
def fetch_prices(coin):
    try:
        print(f"📡 Fetching prices for {coin}")
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=7&interval=hourly"
        
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ API Error for {coin}: {response.status_code}")
            return []

        data = response.json()
        prices = [point[1] for point in data["prices"]]
        print(f"✅ Got {len(prices)} prices for {coin}")
        return prices

    except Exception as e:
        print(f"⚠️ Error fetching {coin}:", e)
        return []

# ====== Signal Generation =======
def get_signal(prices):
    rsi = calculate_rsi(prices)
    macd, signal, hist = calculate_macd(prices)
    print(f"📊 RSI: {rsi:.2f}, MACD: {macd:.2f}, Signal: {signal:.2f}, Hist: {hist:.2f}")

    if rsi < 30 and macd > signal and hist > 0:
        return "📈 STRONG BUY"
    elif rsi > 70 and macd < signal and hist < 0:
        return "📉 STRONG SELL"
    elif 45 < rsi < 55:
        return "🔁 HOLD"
    else:
        return "🤔 NEUTRAL"

# ====== Send Telegram Message =======
def send_signal(coin, price, signal):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🔔 *Signal Alert*\n"
        f"🪙 *Coin:* {coin.upper()}\n"
        f"💰 *Price:* ${price:.2f}\n"
        f"📊 *Signal:* {signal}\n"
        f"⏱️ *Time:* {now}"
    )
    try:
        print(f"📨 Sending signal for {coin}: {signal}")
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print("Telegram Error:", e)

# ====== Auto Loop =======
def signal_loop():
    while True:
        try:
            for coin in COINS:
                prices = fetch_prices(coin)
                if len(prices) < 30:
                    print(f"⚠️ Not enough data for {coin}, skipping.")
                    continue

                signal = get_signal(prices)
                current_price = prices[-1]
                send_signal(coin, current_price, signal)
                print(f"✅ {coin} signal sent: {signal}")
        except Exception as e:
            print("⚠️ Error in loop:", e)

        print(f"⏳ Sleeping {LOOP_MINUTES} mins...\n")
        time.sleep(LOOP_MINUTES * 60)

# ====== Start Loop in Thread =======
def start_bot_loop():
    print("🚀 Starting signal loop thread...")
    t = threading.Thread(target=signal_loop)
    t.daemon = True
    t.start()

# ====== Start Everything =======
start_bot_loop()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    bot.send_message(CHAT_ID, "🚀 CoinGecko Bot Successfully Deployed!")
    app.run(host="0.0.0.0", port=port)
