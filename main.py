import requests, pandas as pd, ta, time, csv
from datetime import datetime
from flask import Flask
from threading import Thread

# CONFIGURACIÓN
API_KEY = "8e0049007fcf4a21aa59a904ea8af292"
INTERVAL = "1min"
TELEGRAM_TOKEN = "7099030025:AAE7LsZWHPRtUejJGcae0pDzonHwbDTL-no"
TELEGRAM_CHAT_ID = "5989911212"

# Lista de pares (excluye EUR/JPY por bajo rendimiento)
PARES = [
    "EUR/USD", "EUR/CAD", "EUR/CHF", "EUR/GBP",
    "AUD/USD", "AUD/CHF", "AUD/CAD",
    "USD/CHF", "USD/JPY", "USD/CAD", "USD/INR", "USD/BDT", "USD/MXN", "GBP/JPY"
]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    requests.post(url, data=data)

def guardar_csv(fecha, par, tipo, estrategias, precio):
    with open("senales_optimizadas.csv", "a", newline="") as f:
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
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    return df

def vela_fuerte(row):
    cuerpo = abs(row["close"] - row["open"])
    mecha_total = row["high"] - row["low"]
    if mecha_total == 0:
        return False
    proporcion = cuerpo / mecha_total
    return proporcion >= 0.5

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

    if not vela_fuerte(u):
        print(f"[{symbol}] ❌ Vela débil, sin señal")
        return
    if u["rsi"] > 70 or u["rsi"] < 30:
        print(f"[{symbol}] ❌ RSI extremo, sin señal")
        return

    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and ema20_pendiente > 0.0003:
        estrategias.append("Cruce EMA CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and ema20_pendiente < -0.0003:
        estrategias.append("Cruce EMA PUT")

    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and u["rsi"] > 55 and ema20_pendiente > 0.0003:
        estrategias.append("Cruce EMA + RSI CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and u["rsi"] < 45 and ema20_pendiente < -0.0003:
        estrategias.append("Cruce EMA + RSI PUT")

    if estrategias:
        tipo = "CALL" if "CALL" in " ".join(estrategias) else "PUT"
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mensaje = f"📊 Señal {tipo} en {symbol}:
" + "\n".join(estrategias)
        enviar_telegram(mensaje)
        guardar_csv(fecha, symbol, tipo, ", ".join(estrategias), u["close"])
        print(mensaje)
    else:
        print(f"[{symbol}] ❌ Sin señal clara")

def iniciar():
    while True:
        print("\n🔁 Analizando pares con mejoras aplicadas...\n")
        for par in PARES:
            analizar(par)
        print("⏳ Esperando 2 minutos...\n")
        time.sleep(120)

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot activo con filtros de pendiente, vela fuerte y RSI"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
iniciar()