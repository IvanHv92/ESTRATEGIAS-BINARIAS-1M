import requests, pandas as pd, ta, time, csv
from datetime import datetime
from flask import Flask
from threading import Thread

# CONFIGURACIÓN
API_KEY = "8e0049007fcf4a21aa59a904ea8af292"
INTERVAL = "1min"
TELEGRAM_TOKEN = "7099030025:AAE7LsZWHPRtUejJGcae0pDzonHwbDTL-no"
TELEGRAM_CHAT_ID = "5989911212"

# Pares de divisas a analizar
PARES = [
    "EUR/USD", "EUR/CAD", "EUR/CHF", "EUR/GBP", "EUR/JPY",
    "AUD/CAD", "AUD/CHF", "AUD/USD", "AUD/JPY",
    "USD/CHF", "USD/JPY", "USD/INR", "USD/CAD"
]

# Función para enviar señal por Telegram
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    requests.post(url, data=data)

# Guardar señales en CSV
def guardar_csv(fecha, par, tipo, estrategias, precio):
    with open("senales_filtradas.csv", "a", newline="") as f:
        csv.writer(f).writerow([fecha, par, tipo, estrategias, round(precio, 5)])

# Obtener datos desde TwelveData
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

# Lógica de análisis por par
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

    ema20_pendiente = u["ema20"] - a["ema20"]

    # Estrategia 1: Cruce EMA puro con pendiente
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and ema20_pendiente > 0:
        estrategias.append("Cruce EMA CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and ema20_pendiente < 0:
        estrategias.append("Cruce EMA PUT")

    # Estrategia 2: Cruce EMA + RSI más estricta
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and u["rsi"] > 55 and ema20_pendiente > 0:
        estrategias.append("Cruce EMA + RSI CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and u["rsi"] < 45 and ema20_pendiente < 0:
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

# Ciclo principal del bot
def iniciar():
    while True:
        print("\n🔁 Analizando pares con estrategia estricta EMA y EMA+RSI...\n")
        for par in PARES:
            analizar(par)
        print("⏳ Esperando 2 minutos...\n")
        time.sleep(120)

# Servidor web para mantener activo en Render
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot optimizado activo con estrategias estrictas (EMA + EMA/RSI filtradas)"

# Ejecutar servidor y bot
Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
iniciar()
