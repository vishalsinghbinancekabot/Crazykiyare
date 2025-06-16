import requests
import time
import numpy as np
import telebot
import os  # ← ADD THIS

# ==== CONFIGURATION ====
COINS = ['bitcoin', 'ethereum', 'solana', 'binancecoin']
VS_CURRENCY = 'usd'
API_URL = 'https://api.coingecko.com/api/v3/coins/'
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # ✅ Use env variable
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID")      # ✅ Use env variable
CHECK_INTERVAL = 300  # in seconds

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ==== SIGNAL STRATEGY ====
def get_price_data(coin_id, days=2, interval='hourly'):
    url = f'{API_URL}{coin_id}/market_chart?vs_currency={VS_CURRENCY}&days={days}&interval={interval}'
    response = requests.get(url)
    data = response.json()
    prices = [p[1] for p in data['prices']]
    return prices

def calculate_rsi(prices, period=14):
    prices = np.array(prices)
    deltas = np.diff(prices)
    gain = np.where(deltas > 0, deltas, 0)
    loss = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.convolve(gain, np.ones(period), 'valid') / period
    avg_loss = np.convolve(loss, np.ones(period), 'valid') / period
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi[-1]

def calculate_macd(prices, short_period=12, long_period=26, signal_period=9):
    prices = np.array(prices)
    short_ema = np.convolve(prices, np.ones(short_period)/short_period, mode='valid')
    long_ema = np.convolve(prices, np.ones(long_period)/long_period, mode='valid')
    macd_line = short_ema[-len(long_ema):] - long_ema
    signal_line = np.convolve(macd_line, np.ones(signal_period)/signal_period, mode='valid')
    if len(signal_line) == 0:
        return 0, 0
    return macd_line[-1], signal_line[-1]

def generate_signal(prices):
    if len(prices) < 30:
        return "Not enough data"
    rsi = calculate_rsi(prices)
    macd, signal = calculate_macd(prices)
    if rsi < 30 and macd > signal:
        return "🔼 BUY"
    elif rsi > 70 and macd < signal:
        return "🔽 SELL"
    else:
        return "⏸️ HOLD"

# ==== TELEGRAM ALERT ====
def send_signal_message(coin, price, signal):
    message = f"📊 *{coin.upper()} SIGNAL*\nPrice: ${price:.2f}\nSignal: {signal}\n🔗 Chart: https://www.coingecko.com/en/coins/{coin}"
    bot.send_message(TELEGRAM_USER_ID, message, parse_mode="Markdown")

# ==== MAIN LOOP ====
def run_bot():
    while True:
        for coin in COINS:
            try:
                prices = get_price_data(coin)
                if not prices:
                    continue
                current_price = prices[-1]
                signal = generate_signal(prices)
                if "BUY" in signal or "SELL" in signal:
                    send_signal_message(coin, current_price, signal)
                print(f"{coin.upper()}: {signal} at ${current_price:.2f}")
            except Exception as e:
                print(f"Error with {coin}: {e}")
        time.sleep(CHECK_INTERVAL)

# ==== START ====
if __name__ == "__main__":
    run_bot()
