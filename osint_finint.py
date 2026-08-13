import os
import random
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

from osint_alerts import send_telegram_push

load_dotenv()

# Tasa de cambio oficial base y paralela base para generar datos realistas fluctuantes
# pero estables
BASE_BCV = float(os.getenv("BASE_BCV_RATE", "36.25"))
BASE_PARALLEL = float(os.getenv("BASE_PARALLEL_RATE", "38.90"))

def get_exchange_data() -> Dict[str, Any]:
    """
    Genera y calcula indicadores económicos tácticos en tiempo real.
    Simula telemetría en vivo del Banco Central (BCV) y el mercado paralelo (Monitoreo FININT).
    """
    now_hour = datetime.now().hour

    # Especulación variable según hora del día
    fluctuation_bcv = random.uniform(-0.05, 0.08)
    fluctuation_parallel = random.uniform(-0.1, 0.4)

    # Si es hora pico (tarde/noche), simular mayor desestabilización especulativa
    if 12 <= now_hour <= 18:
        fluctuation_parallel += random.uniform(0.3, 0.8)

    bcv_rate = round(BASE_BCV + fluctuation_bcv, 2)
    parallel_rate = round(BASE_PARALLEL + fluctuation_parallel, 2)

    divergence = round(((parallel_rate - bcv_rate) / bcv_rate) * 100, 2)

    # Nivel de riesgo económico / ataque financiero
    if divergence >= 8.5:
        risk_level = "CRÍTICO"
        risk_desc = "Ataque cambiario coordinado de alta intensidad. Desviación desestabilizadora."
    elif divergence >= 5.0:
        risk_level = "ALTA"
        risk_desc = "Tensión cambiaria moderada. Actividad especulativa en aumento."
    else:
        risk_level = "MEDIA"
        risk_desc = "Mercado cambiario estable. Comportamiento ordinario."

    # Flujos inusuales de criptoactivos en LocalBitcoins / Binance P2P simulados
    crypto_volume_millions = round(random.uniform(1.2, 5.8), 2)

    return {
        "bcv": bcv_rate,
        "parallel": parallel_rate,
        "divergence": divergence,
        "risk_level": risk_level,
        "risk_desc": risk_desc,
        "crypto_volume": crypto_volume_millions,
        "timestamp": datetime.now().isoformat()
    }

def get_finint_data() -> Dict[str, Any]:
    """
    Formatea las alertas e informes del Radar FININT para el Dashboard central de Cobalto Hub.
    """
    items = []
    data = get_exchange_data()

    # 1. Entrada de Estado Cambiario General
    items.append({
        "title": f"🪙 Monitoreo de Divisas: Oficial (BCV) {data['bcv']} | Paralelo {data['parallel']}",
        "summary": f"Desviación cambiaria del {data['divergence']}%. Riesgo FININT: {data['risk_level']}. {data['risk_desc']} Volumen de cripto-remesas P2P: {data['crypto_volume']}M USD.",
        "link": "https://www.bcv.org.ve",
        "published": data["timestamp"],
        "source": "🪙 Radar FININT (BCV/Económico)",
        "type": "cyber_alert" if data["risk_level"] in ["ALTA", "CRÍTICO"] else "finint_info",
        "severity": data["risk_level"]
    })

    # Auto-desencadenar Telegram push si hay riesgo crítico
    if data["risk_level"] in ["ALTA", "CRÍTICO"]:
        try:
            send_telegram_push(items[-1])
        except Exception:
            pass

    # 2. Alerta específica de inyección financiera o fuga en cripto
    if data["crypto_volume"] > 4.0:
        items.append({
            "title": f"[ALTA] ⚠️ FININT: Flujo inusual de capitales P2P Cripto ({data['crypto_volume']}M USD)",
            "summary": "Anomalía detectada en Binance P2P/USDT: Incremento inusual en la compra masiva de activos estables en la última hora. Correlación de cobertura cambiaria activa.",
            "link": "https://p2p.binance.com",
            "published": data["timestamp"],
            "source": "🪙 Radar FININT (Cripto)",
            "type": "cyber_alert",
            "severity": "ALTA"
        })

    # 3. Alerta de desviación crítica si supera el 8.5%
    if data["divergence"] >= 8.5:
        items.append({
            "title": f"[CRÍTICO] 🔥 FININT: Ataque Cambiario y Distorsión Especulativa Extrema ({data['divergence']}%)",
            "summary": f"Divergencia crítica detectada entre la tasa de cambio oficial BCV ({data['bcv']}) y el mercado especulativo paralelos ({data['parallel']}). Indicios de manipulación narrativa y bots coordinados de amplificación económica.",
            "link": "https://www.bcv.org.ve",
            "published": data["timestamp"],
            "source": "🪙 Radar FININT (Especulación)",
            "type": "cyber_alert",
            "severity": "CRÍTICO"
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {
            "🪙 Radar FININT": items
        },
        "count": len(items)
    }

if __name__ == "__main__":
    print("=== TEST RADAR FININT ===")
    d = get_finint_data()
    print(f"Total Alertas: {d['count']}")
    for src, items in d["sources"].items():
        for i in items:
            try:
                print(f"[{i.get('severity', 'INFO')}] {i['title']}")
                print(f"  -> {i['summary']}")
            except UnicodeEncodeError:
                clean_title = i['title'].encode("ascii", "ignore").decode("ascii")
                clean_summary = i['summary'].encode("ascii", "ignore").decode("ascii")
                print(f"[{i.get('severity', 'INFO')}] {clean_title}")
                print(f"  -> {clean_summary}")
