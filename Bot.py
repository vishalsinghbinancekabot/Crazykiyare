import requests
import time
import numpy as np
import telebot
import os
from flask import Flask
import threading

# ==== ENVIRONMENT VARIABLES ====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")  # string

# ==== CONFIGURATION ====
COINS = ['bitcoin', 'ethereum', 'solana', 'binancecoin']
VS_CURRENCY = 'usd'
API_URL = 'https://api.coingecko.com/api/v3/coins/'
CHECK_INTERVAL = 300  # 5 minutes

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ==== FLASK KEEP-ALIVE ====
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

# ==== SIGNAL STRATEGY ====
def get_price_data(coin_id, days=2, interval='hourly'):
    url = f'{API_URL}{coin_id}/market_chart?vs_currency={VS_CURRENCY}&days={days}&interval={interval}'
    response = requests.get(url)
    data = response.json()
    prices = [p[1] for p in data['prices']]
    return prices

def analyze_trend(prices):
    short_avg = np.mean(prices[-3:])
    long_avg = np.mean(prices[-12:])
    if short_avg > long_avg * 1.01:
        return 'BUY'
    elif short_avg < long_avg * 0.99:
        return 'SELL'
    else:
        return 'HOLD'

def check_and_send_signals():
    while True:
        for coin in COINS:
            try:
                prices = get_price_data(coin)
                signal = analyze_trend(prices)
                message = f"📊 {coin.upper()} Signal: {signal}"
                bot.send_message(chat_id=TELEGRAM_USER_ID, text=message)
                time.sleep(5)
            except Exception as e:
                print(f"Error for {coin}: {e}")
        time.sleep(CHECK_INTERVAL)

# ==== START BOT ====
threading.Thread(target=check_and_send_signals).start()
