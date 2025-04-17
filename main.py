import requests, pandas as pd, ta, time, csv
from datetime import datetime
from flask import Flask
from threading import Thread

# CONFIGURACIÓN
API_KEY = "8e0049007fcf4a21aa59a904ea8af292"
INTERVAL = "1min"
TELEGRAM_TOKEN = "7099030025:AAE7LsZWHPRtUejJGcae0pDzonHwbDTL-no"
TELEGRAM_CHAT_ID = "5989911212"

PARES = [
    "EUR/USD", "EUR/CAD", "EUR/CHF", "EUR/GBP", "EUR/JPY",
    "AUD/CAD", "AUD/CHF", "AUD/USD", "AUD/JPY",
    "USD/CHF", "USD/JPY", "USD/INR", "USD/CAD",
    "GBP/JPY", "USD/BDT", "USD/MXN",
    "CAD/JPY", "GBP/CAD", "CAD/CHF", "NZD/CAD", "EUR/AUD"
]

ULTIMAS_SENIALES = {}

# ENVÍO A TELEGRAM
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    requests.post(url, data=data)

def guardar_csv(fecha, par, tipo, estrategias, precio, expiracion):
    with open("senales_estrategia_nueva.csv", "a", newline="") as f:
        csv.writer(f).writerow([fecha, par, tipo, estrategias, round(precio, 5), expiracion])

# OBTENER DATOS
def obtener_datos(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize=100&apikey={API_KEY}"
    r = requests.get(url).json()
    if "values" not in r:
        print(f"❌ Error al obtener datos de {symbol}")
        return None
    df = pd.DataFrame(r["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    return df

# ANALIZAR CON 3 INDICADORES
# Indicadores: MACD, Estocástico, CCI
def analizar(symbol):
    df = obtener_datos(symbol)
    if df is None:
        return

    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    estoc = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=14, smooth_window=3)
    df["%k"] = estoc.stoch()
    df["%d"] = estoc.stoch_signal()

    df["cci"] = ta.trend.CCIIndicator(df["high"], df["low"], df["close"], window=20).cci()

    u = df.iloc[-1]
    a = df.iloc[-2]
    estrategias = []

    # MACD cruzando al alza/abajo
    if a["macd"] < a["macd_signal"] and u["macd"] > u["macd_signal"]:
        estrategias.append("MACD CALL")
    elif a["macd"] > a["macd_signal"] and u["macd"] < u["macd_signal"]:
        estrategias.append("MACD PUT")

    # Estocástico
    if u["%k"] > u["%d"] and u["%k"] < 80:
        estrategias.append("Estocástico CALL")
    elif u["%k"] < u["%d"] and u["%k"] > 20:
        estrategias.append("Estocástico PUT")

    # CCI
    if u["cci"] > 100:
        estrategias.append("CCI CALL")
    elif u["cci"] < -100:
        estrategias.append("CCI PUT")

    # VALIDACIÓN: las 3 deben coincidir
    tipo = None
    if all("CALL" in e for e in estrategias) and len(estrategias) == 3:
        tipo = "CALL"
    elif all("PUT" in e for e in estrategias) and len(estrategias) == 3:
        tipo = "PUT"

    if tipo:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mensaje = (
            f"📊 Nueva estrategia {tipo} en {symbol} ({fecha}):\n"
            + "\n".join(estrategias) +
            "\n⏱️ Expiración sugerida: 5 minutos\n"
            "📈 Confianza: ⭐⭐⭐"
        )
        enviar_telegram(mensaje)
        guardar_csv(fecha, symbol, tipo, ", ".join(estrategias), u["close"], "5 min")
        print(mensaje)
    else:
        print(f"[{symbol}] ❌ Sin confirmación clara entre los 3 indicadores")

def iniciar():
    while True:
        print("⏳ Analizando todos los pares...")
        for par in PARES:
            analizar(par)
        print("🕒 Esperando 2 minutos...\n")
        time.sleep(120)

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot activo: MACD + Estocástico + CCI (1min, 5min exp.)"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
iniciar()
