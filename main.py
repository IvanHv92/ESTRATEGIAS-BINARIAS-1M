import requests, pandas as pd, ta, time, csv
from datetime import datetime
from flask import Flask
from threading import Thread

# CONFIGURACIÓN
API_KEY = "8e0049007fcf4a21aa59a904ea8af292"
INTERVAL = "5min"
TELEGRAM_TOKEN = "7099030025:AAE7LsZWHPRtUejJGcae0pDzonHwbDTL-no"
TELEGRAM_CHAT_ID = "5989911212"

PARES = [
    "EUR/USD", "EUR/CAD", "EUR/CHF", "EUR/GBP", "EUR/JPY",
    "AUD/CAD", "AUD/CHF", "AUD/USD", "AUD/JPY",
    "USD/CHF", "USD/JPY", "USD/INR", "USD/CAD",
    "GBP/JPY", "USD/BDT", "USD/EGP", "USD/MXN"
]

ULTIMAS_SENIALES = {}

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    requests.post(url, data=data)

def guardar_csv(fecha, par, tipo, estrategias, precio, expiracion):
    with open("senales_final.csv", "a", newline="") as f:
        csv.writer(f).writerow([fecha, par, tipo, estrategias, round(precio, 5), expiracion])

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

def analizar(symbol):
    df = obtener_datos(symbol)
    if df is None:
        return

    # Bollinger Bands
    try:
        bb = ta.volatility.BollingerBands(df["close"], 20, 2)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()
    except Exception as e:
        print(f"⚠️ Error calculando BB en {symbol}: {e}")
        return

    if "bb_upper" not in df.columns or "bb_lower" not in df.columns:
        print(f"⚠️ No se generaron bandas de Bollinger en {symbol}")
        return

    u = df.iloc[-1]
    a = df.iloc[-2]

    # Filtro de consolidación
    rango_bb = (u["bb_upper"] - u["bb_lower"]) / u["close"]
    variacion = (df["high"].max() - df["low"].min()) / u["close"]
    if rango_bb < 0.01 or variacion < 0.01:
        print(f"⚠️ Señal ignorada en {symbol} por consolidación")
        return

    # Anti-martingala
    ahora = datetime.now()
    if symbol in ULTIMAS_SENIALES:
        delta = (ahora - ULTIMAS_SENIALES[symbol]).total_seconds()
        if delta < 300:
            print(f"⛔ Señal ignorada en {symbol} por anti-martingala")
            return

    # Indicadores
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["ema9"] = ta.trend.EMAIndicator(df["close"], 9).ema_indicator()
    df["ema20"] = ta.trend.EMAIndicator(df["close"], 20).ema_indicator()

    adx = ta.trend.ADXIndicator(high=df["high"], low=df["low"], close=df["close"])
    df["adx"] = adx.adx()
    df["+di"] = adx.adx_pos()
    df["-di"] = adx.adx_neg()

    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    estrategias = []

    # 1. Cruce EMA
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"]:
        estrategias.append("Cruce EMA CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"]:
        estrategias.append("Cruce EMA PUT")

    # 2. EMA + RSI
    if a["ema9"] < a["ema20"] and u["ema9"] > u["ema20"] and u["rsi"] > 50:
        estrategias.append("EMA + RSI CALL")
    if a["ema9"] > a["ema20"] and u["ema9"] < u["ema20"] and u["rsi"] < 50:
        estrategias.append("EMA + RSI PUT")

    # 3. RSI + MACD
    if a["macd"] < a["macd_signal"] and u["macd"] > u["macd_signal"] and u["rsi"] > 50:
        estrategias.append("RSI + MACD CALL")
    if a["macd"] > a["macd_signal"] and u["macd"] < u["macd_signal"] and u["rsi"] < 50:
        estrategias.append("RSI + MACD PUT")

    # 4. ADX + EMA
    if u["adx"] > 20:
        if u["+di"] > u["-di"] and u["ema9"] > u["ema20"]:
            estrategias.append("ADX + EMA CALL")
        if u["-di"] > u["+di"] and u["ema9"] < u["ema20"]:
            estrategias.append("ADX + EMA PUT")

    # Validación
    if len(estrategias) >= 2:
        tipo = "CALL" if "CALL" in " ".join(estrategias) else "PUT"
        fuerza = len(estrategias)
        expiracion = "5 min" if fuerza >= 3 else "3 min"
        fecha = ahora.strftime("%Y-%m-%d %H:%M:%S")
        estrellas = "⭐" * fuerza
        mensaje = (
            f"📊 Señal {tipo} en {symbol}:\n"
            f"{fecha}\n"
            + "\n".join(estrategias) +
            f"\n⏱️ Expiración sugerida: {expiracion}\n"
            f"📈 Confianza: {estrellas}"
        )
        enviar_telegram(mensaje)
        guardar_csv(fecha, symbol, tipo, ", ".join(estrategias), u["close"], expiracion)
        ULTIMAS_SENIALES[symbol] = ahora
        print(mensaje)
    else:
        print(f"[{symbol}] ❌ Señal débil (menos de 2 estrategias)")

def iniciar():
    while True:
        print("⏳ Analizando todos los pares...")
        for par in PARES:
            analizar(par)
        print("🕒 Esperando 2 minutos...\n")
        time.sleep(120)

# Flask para mantener activo en Render
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot activo con estrategias: EMA, EMA+RSI, MACD+RSI, ADX+EMA y filtros avanzados"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
iniciar()
