# app.py — نسخه بهینه‌شده برای لود سریع‌تر و تجربه کاربری بهتر
from flask import Flask, send_from_directory, jsonify
import json
import threading
import time
from data_fetcher import get_top_coins_with_volume, get_ohlc
from indicators import rsi

app = Flask(__name__, static_folder='.')

# تنظیمات پیش‌فرض
DEFAULT_CONFIG = {
    "scan_interval": 120,        # هر 2 دقیقه اسکن کامل
    "min_volume_usd": 5000000,
    "price_change_1h_min": 5.0,
    "rsi_oversold": 30,
    "rsi_overbought": 70
}

signals_data = {"last_update": "در حال دریافت داده...", "coins": []}

def quick_rsi_signal(coin):
    """سیگنال سریع فقط با RSI و تغییر قیمت (بدون MACD برای سرعت)"""
    symbol_id = coin.get("id")
    symbol = coin.get("symbol", "").upper()
    price = coin.get("current_price", 0)
    change_1h = coin.get("price_change_percentage_1h_in_currency", 0)
    volume = coin.get("total_volume", 0)

    if not symbol_id or price <= 0:
        return None

    # فقط 20 کندل برای RSI سریع
    closes = get_ohlc(symbol_id, days=1)
    current_rsi = rsi(closes) if len(closes) >= 20 else 50

    signal = "NEUTRAL"
    if current_rsi < DEFAULT_CONFIG["rsi_oversold"] and change_1h > 0:
        signal = "PUMP"
    elif current_rsi > DEFAULT_CONFIG["rsi_overbought"] and change_1h < 0:
        signal = "DUMP"

    return {
        "symbol": f"{symbol}/USDT",
        "price": round(price, 6),
        "change_1h": round(change_1h, 2),
        "volume": round(volume, 0),
        "rsi": round(current_rsi, 2),
        "macd_hist": 0.0,
        "signal": signal
    }

def full_scan():
    """اسکن کامل (با MACD) هر 2 دقیقه"""
    global signals_data
    while True:
        try:
            coins = get_top_coins_with_volume(DEFAULT_CONFIG["min_volume_usd"])
            all_data = []
            for coin in coins[:80]:
                try:
                    symbol_id = coin.get("id")
                    symbol = coin.get("symbol", "").upper()
                    price = coin.get("current_price", 0)
                    change_1h = coin.get("price_change_percentage_1h_in_currency", 0)
                    volume = coin.get("total_volume", 0)

                    if not symbol_id or price <= 0:
                        continue

                    closes = get_ohlc(symbol_id, days=1)
                    current_rsi = rsi(closes) if len(closes) >= 30 else 50
                    # محاسبه MACD فقط در اسکن کامل
                    from indicators import macd
                    macd_val, signal_val = macd(closes) if len(closes) >= 30 else (0, 0)

                    all_data.append({
                        "symbol": f"{symbol}/USDT",
                        "price": round(price, 6),
                        "change_1h": round(change_1h, 2),
                        "volume": round(volume, 0),
                        "rsi": round(current_rsi, 2),
                        "macd_hist": round(macd_val - signal_val, 6),
                        "signal": "PUMP" if (current_rsi < DEFAULT_CONFIG["rsi_oversold"] and change_1h > 0) else
                                  "DUMP" if (current_rsi > DEFAULT_CONFIG["rsi_overbought"] and change_1h < 0) else "NEUTRAL"
                    })
                except:
                    continue

            signals_data = {
                "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
                "coins": all_data
            }
            print(f"✅ اسکن کامل شد: {len(all_data)} ارز")
        except Exception as e:
            print(f"❌ خطا در اسکن کامل: {e}")
        time.sleep(DEFAULT_CONFIG["scan_interval"])

def initial_quick_scan():
    """اسکن سریع در ابتدای راه‌اندازی — فقط برای نمایش سریع داده"""
    global signals_data
    print("⚡ شروع اسکن اولیه سریع...")
    try:
        coins = get_top_coins_with_volume(DEFAULT_CONFIG["min_volume_usd"])
        all_data = []
        for coin in coins[:50]:  # فقط 50 تا برای سرعت
            result = quick_rsi_signal(coin)
            if result:
                all_data.append(result)
        signals_data = {
            "last_update": "داده‌های اولیه آماده شد (در حال بروزرسانی کامل...)",
            "coins": all_data
        }
        print(f"🚀 اسکن اولیه: {len(all_data)} ارز آماده شد")
    except Exception as e:
        print(f"⚠️ خطا در اسکن اولیه: {e}")
        signals_data = {
            "last_update": "خطا در دریافت داده — در حال تلاش مجدد...",
            "coins": []
        }

# راه‌اندازی
threading.Thread(target=full_scan, daemon=True).start()
initial_quick_scan()  # این اول اجرا می‌شه

@app.route('/')
def dashboard():
    return send_from_directory('.', 'dashboard.html')

@app.route('/signals.json')
def signals():
    return jsonify(signals_data)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
