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

# === ENVIRONMENT VARIABLES ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
COINGECKO_API_URL = os.getenv("COINGECKO_API_URL", "https://api.coingecko.com/api/v3")

# === SETTINGS ===
COINS = ["bitcoin", "ethereum", "solana", "binancecoin"]
VS_CURRENCY = "usd"
LOOP_MINUTES = 10

# === BOT INIT ===
if not TOKEN or not CHAT_ID:
    raise Exception("❌ Telegram credentials not set!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

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

def fetch_prices(coin_id):
    try:
        url = f"{COINGECKO_API_URL}/coins/{coin_id}/market_chart?vs_currency={VS_CURRENCY}&days=7"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ API Error for {coin_id}: {response.status_code}")
            return []

        data = response.json()
        prices = [point[1] for point in data["prices"]]
        print(f"✅ Fetched {len(prices)} prices for {coin_id}")
        return prices

    except Exception as e:
        print(f"⚠️ Error fetching {coin_id}: {e}")
        return []

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

def send_signal(coin, price, signal):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🔔 *Crypto Signal Alert*\n"
        f"🪙 *Coin:* {coin.upper()}\n"
        f"💰 *Price:* ${price:.2f}\n"
        f"📊 *Signal:* {signal}\n"
        f"⏱️ *Time:* {now}"
    )
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        print(f"✅ Sent signal for {coin}: {signal}")
    except Exception as e:
        print("❌ Telegram Error:", e)

# === LOOP ===
def signal_loop():
    while True:
        for coin in COINS:
            prices = fetch_prices(coin)
            if len(prices) < 30:
                print(f"⚠️ Not enough data for {coin}, skipping.")
                continue

            signal = get_signal(prices)
            current_price = prices[-1]
            send_signal(coin, current_price, signal)

        print(f"⏳ Sleeping for {LOOP_MINUTES} minutes...\n")
        time.sleep(LOOP_MINUTES * 60)

# === STARTUP ===
@app.route('/')
def home():
    return "✅ Crypto Signal Bot is Running!"

def start_bot_loop():
    t = threading.Thread(target=signal_loop)
    t.daemon = True
    t.start()

# === START APP ===
start_bot_loop()
if __name__ == "__main__":
    bot.send_message(CHAT_ID, "🚀 CoinGecko Crypto Signal Bot is LIVE!")
    app.run(host="0.0.0.0", port=10000)
