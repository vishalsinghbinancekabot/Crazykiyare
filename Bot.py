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
VS_CURRENCY = "usd"
INTERVAL = "1h"
LOOP_MINUTES = 10

# === VALIDATION ===
if not TOKEN:
    raise Exception("❌ TELEGRAM_BOT_TOKEN not set!")
if not CHAT_ID:
    raise Exception("❌ TELEGRAM_CHAT_ID not set!")

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
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency={VS_CURRENCY}&days=2&interval={INTERVAL}"
        data = requests.get(url).json()
        prices = [point[1] for point in data["prices"]]
        return prices
    except Exception as e:
        print(f"⚠️ Error fetching {coin}:", e)
        return []

def get_signal(prices):
    rsi = calculate_rsi(prices)
    macd, signal, hist = calculate_macd(prices)

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
    t = threading.Thread(target=signal_loop)
    t.daemon = True
    t.start()

# === START EVERYTHING ===
if __name__ == "__main__":
    start_bot_loop()
    app.run(host="0.0.0.0", port=10000)
