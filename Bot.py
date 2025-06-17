import os
import time
import threading
import requests
import datetime
import numpy as np
from flask import Flask
import telebot
from dotenv import load_dotenv

load_dotenv()

# === ENVIRONMENT ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

COINS = ["bitcoin", "ethereum", "solana", "binancecoin"]
LOOP_MINUTES = 10

# === VALIDATION ===
if not TOKEN:
    raise Exception("❌ TELEGRAM_BOT_TOKEN not set!")
if not CHAT_ID:
    raise Exception("❌ TELEGRAM_CHAT_ID not set!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Crypto Signal Bot Running!"

# === STRATEGIES ===
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

def fetch_prices(coin):
    try:
        url = f"https://api.coinstats.app/public/v1/charts?period=30d&coinId={coin}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ API Error for {coin}: {response.status_code}")
            return []
        data = response.json()
        prices = [point[1] for point in data["chart"]]
        print(f"✅ {coin} | Fetched {len(prices)} prices.")
        return prices
    except Exception as e:
        print(f"⚠️ Error fetching {coin}:", e)
        return []

def get_signal(prices):
    rsi = calculate_rsi(prices)
    macd, signal_line, hist = calculate_macd(prices)
    print(f"📊 RSI: {rsi:.2f}, MACD: {macd:.2f}, Signal: {signal_line:.2f}, Hist: {hist:.2f}")

    if rsi < 30 and macd > signal_line and hist > 0:
        return "📈 STRONG BUY"
    elif rsi > 70 and macd < signal_line and hist < 0:
        return "📉 STRONG SELL"
    elif 45 < rsi < 55:
        return "🔁 HOLD"
    else:
        return "🤔 NEUTRAL"

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
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        print(f"✅ {coin} | Signal Sent: {signal}")
    except Exception as e:
        print("Telegram Error:", e)

# === LOOP ===
def signal_loop():
    while True:
        try:
            for coin in COINS:
                prices = fetch_prices(coin)
                if len(prices) < 30:
                    print(f"⚠️ {coin} | Not enough data.")
                    continue
                signal = get_signal(prices)
                send_signal(coin, prices[-1], signal)
        except Exception as e:
            print("⚠️ Error in loop:", e)
        print(f"⏳ Sleeping {LOOP_MINUTES} mins...\n")
        time.sleep(LOOP_MINUTES * 60)

# === THREADING ===
def start_bot_loop():
    print("🚀 Starting signal loop thread...")
    t = threading.Thread(target=signal_loop)
    t.daemon = True
    t.start()

# === INIT ===
start_bot_loop()

if __name__ == "__main__":
    bot.send_message(CHAT_ID, "🚀 Bot Successfully Deployed!")
    app.run(host="0.0.0.0", port=10000)
