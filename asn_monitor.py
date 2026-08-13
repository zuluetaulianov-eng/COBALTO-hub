import logging
import statistics
import time
from datetime import datetime
from typing import Any, Dict

import requests

import config

logger = logging.getLogger(__name__)

TARGET_ASNS = {
    "8048": "CANTV (Backbone Nacional)",
    "8046": "Telefónica Movistar",
    "19324": "Corporación Digitel",
    "21826": "Inter / Telemic",
}

IODA_API_URL = "https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/asn/{asn}"

# Ventana deslizante: cuántos puntos recientes promediar (3 ≈ 15 min)
RECENT_WINDOW = 3

_seen_outages = {}  # { "asn": timestamp }


def _cleanup_cache(max_age: float = 10800):
    now = time.time()
    stale = [k for k, ts in _seen_outages.items() if now - ts > max_age]
    for k in stale:
        del _seen_outages[k]


def _fetch_asn_signal(asn: str) -> tuple:
    """
    Retorna (mu_recent, mu_base, drop_pct).
    Modelo de ventanas deslizantes:
      - mu_recent: media de los últimos RECENT_WINDOW puntos (tráfico actual)
      - mu_base:   media de todo el histórico de 24h excepto la ventana reciente
      - drop_pct:  caída porcentual relativa, 0 si no hay caída
    """
    until = int(time.time())
    start = until - 86400

    try:
        resp = requests.get(
            IODA_API_URL.format(asn=asn),
            params={"from": start, "until": until, "signal": "active"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[ASN] IODA error AS{asn}: {e}")
        return None, None, 0.0

    if not data.get("data"):
        return None, None, 0.0

    ping_values = None
    for entry in data["data"][0]:
        if entry.get("datasource") == "ping-slash24":
            ping_values = entry.get("values", [])
            break

    if not ping_values:
        return None, None, 0.0

    clean = [v for v in ping_values if v is not None]
    if len(clean) < 12:
        return None, None, 0.0

    recent = clean[-RECENT_WINDOW:]
    baseline = clean[:-RECENT_WINDOW]
    if not baseline or not recent:
        return None, None, 0.0

    mu_recent = statistics.mean(recent)
    mu_base = statistics.mean(baseline)
    if mu_base == 0:
        return None, None, 0.0

    drop_pct = ((mu_base - mu_recent) / mu_base) * 100 if mu_recent < mu_base else 0.0
    return round(mu_recent, 1), round(mu_base, 1), round(drop_pct, 1)


def get_network_outages() -> Dict[str, Any]:
    if not getattr(config, "ASN_MONITOR_ENABLED", True):
        return {"network_outages": [], "count": 0, "timestamp": ""}

    _cleanup_cache()

    drop_threshold = getattr(config, "ASN_DROP_THRESHOLD", 30.0)
    outages = []

    for asn, name in TARGET_ASNS.items():
        mu_recent, mu_base, drop_pct = _fetch_asn_signal(asn)

        if mu_recent is None or drop_pct < drop_threshold:
            continue

        now = time.time()
        if asn in _seen_outages and now - _seen_outages[asn] < 10800:
            continue

        _seen_outages[asn] = now

        severity = "critical" if drop_pct > (drop_threshold * 1.5) else "warning"

        entry = {
            "id": f"outage-as{asn}",
            "asn": asn,
            "provider": name,
            "severity": severity,
            "title": f"Falla de Conectividad: {name}",
            "summary": f"Caída del {drop_pct}% en tráfico activo AS{asn}. "
                       f"Línea base (24h): {mu_base} subredes → Media actual: {mu_recent} subredes.",
            "drop_percentage": drop_pct,
            "current_value": mu_recent,
            "baseline_avg": mu_base,
            "type": "network_outage",
            "source": "IODA/GeorgiaTech",
            "published": datetime.now().isoformat(),
        }
        outages.append(entry)
        logger.warning(f"[ASN] 🚨 {name} (AS{asn}): {drop_pct}% de caída (umbral: {drop_threshold}%)")

    return {"network_outages": outages, "count": len(outages), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
