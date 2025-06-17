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
print("✅ DEBUG | Loading environment variables...")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
print("✅ DEBUG | TELEGRAM_BOT_TOKEN:", TOKEN)
print("✅ DEBUG | TELEGRAM_CHAT_ID:", CHAT_ID)

COINS = ["bitcoin", "ethereum", "solana", "binancecoin"]
VS_CURRENCY = "usd"
INTERVAL = "1h"
LOOP_MINUTES = 10

# === VALIDATION ===
if not TOKEN:
    raise Exception("❌ TELEGRAM_BOT_TOKEN not set!")
if not CHAT_ID:
    raise Exception("❌ TELEGRAM_CHAT_ID not set!")

print("✅ DEBUG | Initializing Telegram bot...")
bot = telebot.TeleBot(TOKEN)

# === FLASK SETUP ===
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
        print(f"📡 DEBUG | Fetching prices for {coin}")
        url = f"https://api.coinstats.app/public/v1/charts?period=7d&coinId={coin}"
        response = requests.get(url)

        print("📄 DEBUG | Status Code:", response.status_code)
        print("📄 DEBUG | Response Text:", response.text[:200])

        if response.status_code != 200:
            print(f"❌ API Error for {coin}: {response.status_code}")
            return []

        data = response.json()
        prices = [point[1] for point in data["chart"]]
        print(f"✅ DEBUG | Fetched {len(prices)} prices for {coin}")
        return prices

    except Exception as e:
        print(f"⚠️ Error fetching {coin}:", e)
        return []
        
def get_signal(prices):
    rsi = calculate_rsi(prices)
    macd, signal, hist = calculate_macd(prices)

    print(f"📊 DEBUG | RSI: {rsi:.2f}, MACD: {macd:.2f}, Signal: {signal:.2f}, Hist: {hist:.2f}")

    if rsi < 30 and macd > signal and hist > 0:
        return "📈 STRONG BUY"
    elif rsi > 70 and macd < signal and hist < 0:
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
        print(f"📨 DEBUG | Sending signal for {coin}: {signal}")
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print("Telegram Error:", e)

# === AUTO LOOP FUNCTION ===
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

# === BACKGROUND THREAD FOR LOOP ===
def start_bot_loop():
    print("🚀 DEBUG | Starting signal loop thread...")
    t = threading.Thread(target=signal_loop)
    t.daemon = True
    t.start()

# === START EVERYTHING ===
if __name__ == "__main__":
    start_bot_loop()
    print("🌐 DEBUG | Running Flask server...")
    bot.send_message(CHAT_ID, "🚀 Bot Successfully Deployed!")  # ✅ Correctly placed & fixed
    app.run(host="0.0.0.0", port=10000)
    start_bot_loop()
    print("🌐 DEBUG | Running Flask server...")
    app.run(host="0.0.0.0", port=10000)
