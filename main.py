import requests, pandas as pd, ta, time, csv
from datetime import datetime
from flask import Flask
from threading import Thread

# CONFIGURACIÓN
API_KEY = "8e0049007fcf4a21aa59a904ea8af292"
INTERVAL = "5min"
TELEGRAM_TOKEN = "7099030025:AAE7LsZWHPRtUejJGcae0pDzonHwbDTL-no"
TELEGRAM_CHAT_ID = "5989911212"

# Pares que se analizarán
PARES = [
    "EUR/USD", "EUR/CAD", "EUR/CHF", "EUR/GBP", "EUR/JPY",
    "AUD/CAD", "AUD/CHF", "AUD/USD", "AUD/JPY",
    "USD/CHF", "USD/JPY", "USD/INR", "USD/CAD"
]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    requests.post(url, data=data)

def guardar_csv(fecha, par, tipo, estrategias, precio):
    with open("señales_optimizadas.csv", "a", newline="") as f:
        csv.writer(f).writerow([fecha, par, tipo, estrategias, round(precio, 5)])

def obtener_datos(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize=100&apikey={API_KEY}"
    r = requests.get(url).json()
    if "values" not in r:
        print(f"❌ Error con {symbol}")
        return None
    df = pd.DataFrame(r["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
    df["close"] = df["close"].astype(float)
    return df

def analizar(symbol):
    df = obtener_datos(symbol)
    if df is None:
        return

    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["ema9"] = ta.trend.EMAIndicator(df["close"], 9).ema_indicator()
    df["ema20"] = ta.trend.EMAIndicator(df["close"], 20).ema_indicator()

    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"] = macd.macd_diff()

    bb = ta.volatility.BollingerBands(df["close"], 20, 2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()

    u = df.iloc[-1]
    a = df.iloc[-2]
    estrategias = []

    # RSI + BB
    if 20 < u["rsi"] < 40 and u["close"] < u["bb_lower"] and u["rsi"] > a["rsi"] and u["close"] > a["close"]:
        estrategias.append("RSI+BB CALL")
    if 60 < u["rsi"] < 80 and u["close"] > u["bb_upper"] and u["rsi"] < a["rsi"] and u["close"] < a["close"]:
        estrategias.append("RSI+BB PUT")

    # Cruce de EMA
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and u["rsi"] > 50:
        estrategias.append("Cruce EMA CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and u["rsi"] < 50:
        estrategias.append("Cruce EMA PUT")

    # MACD + Momentum
    if a["macd"] < a["macd_signal"] and u["macd"] > u["macd_signal"] and u["macd_diff"] > a["macd_diff"]:
        estrategias.append("MACD CALL")
    if a["macd"] > a["macd_signal"] and u["macd"] < u["macd_signal"] and u["macd_diff"] < a["macd_diff"]:
        estrategias.append("MACD PUT")

    if estrategias:
        tipo = "CALL" if "CALL" in " ".join(estrategias) else "PUT"
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mensaje = f"📊 Señal {tipo} en {symbol}:\n" + "\n".join(estrategias)
        enviar_telegram(mensaje)
        guardar_csv(fecha, symbol, tipo, ", ".join(estrategias), u["close"])
        print(mensaje)
    else:
        print(f"[{symbol}] ❌ Sin señal clara")

def iniciar():
    while True:
        print("\n🔁 Analizando pares optimizados...\n")
        for par in PARES:
            analizar(par)
        print("⏳ Esperando 5 minutos...\n")
        time.sleep(300)

# Flask para mantener vivo el bot (Render)
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot optimizado activo con MACD, EMA y RSI+BB"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
iniciar()
