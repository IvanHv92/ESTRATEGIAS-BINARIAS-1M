import requests, pandas as pd, ta, time, csv
from datetime import datetime
from flask import Flask
from threading import Thread

# CONFIGURACIÓN
API_KEY = "8e0049007fcf4a21aa59a904ea8af292"
INTERVAL = "2min"
TELEGRAM_TOKEN = "7099030025:AAE7LsZWHPRtUejJGcae0pDzonHwbDTL-no"
TELEGRAM_CHAT_ID = "5989911212"

# Pares que se analizarán
PARES = [
    "EUR/USD", "EUR/CAD", "EUR/CHF", "EUR/GBP", "EUR/JPY",
    "AUD/CAD", "AUD/CHF", "AUD/USD", "AUD/JPY",
    "USD/CHF", "USD/JPY", "USD/INR", "USD/CAD",
    "GBP/JPY", "USD/BDT", "USD/EGP", "USD/MXN"
]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    requests.post(url, data=data)

def guardar_csv(fecha, par, tipo, estrategias, precio):
    with open("senales_registro.csv", "a", newline="") as f:
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

    u = df.iloc[-1]
    a = df.iloc[-2]
    estrategias = []

    # Cruce EMA sola
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"]:
        estrategias.append("Cruce EMA CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"]:
        estrategias.append("Cruce EMA PUT")

    # Cruce EMA + RSI
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and u["rsi"] > 50:
        estrategias.append("Cruce EMA + RSI CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and u["rsi"] < 50:
        estrategias.append("Cruce EMA + RSI PUT")

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
        print("\n🔁 Analizando todos los pares...\n")
        for par in PARES:
            analizar(par)
        print("⏳ Esperando 2 minutos...\n")
        time.sleep(120)

# Flask para mantener activo en Render
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot activo con estrategias: Cruce EMA y Cruce EMA + RSI (cada 2 min)"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
iniciar()