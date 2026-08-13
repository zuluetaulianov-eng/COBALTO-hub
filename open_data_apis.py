# open_data_apis.py - APIs de datos abiertos para OSINT sobre Venezuela
# Versión 1.0 - BCV, ACLED, y otras fuentes de datos públicos

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from social_public_extractor import safe_get

logger = logging.getLogger(__name__)

# ==========================================
# BCV (Banco Central de Venezuela) - Datos económicos
# ==========================================
BCV_API_BASE = "https://www.bcv.org.ve"


def get_bcv_exchange_rate() -> Dict[str, Any]:
    """Obtiene tasa de cambio oficial del BCV"""
    try:
        # El BCV no tiene API pública oficial, scraping del sitio
        url = f"{BCV_API_BASE}/"

        resp = safe_get(url)
        if resp.status_code == 200:
            import re

            patterns = [
                r"dólar\s*estadounidense.*?(\d+,\d+)",
                r"dollar.*?(\d+[.,]\d{2})",
                r"Bs\.?\s*por\s*US\$.*?(\d+[.,]\d{2})",
                r"tasa.*?(\d+[.,]\d{2})\s*Bs",
            ]
            rate = None
            for pat in patterns:
                matches = re.findall(pat, resp.text, re.IGNORECASE | re.DOTALL)
                if matches:
                    rate = matches[0].replace(",", ".")
                    break
            if rate:
                return {
                    "title": f"Tasa de cambio BCV: {rate} Bs/USD",
                    "summary": f"El Banco Central de Venezuela estableció la tasa oficial en {rate} bolívares por dólar estadounidense.",
                    "link": BCV_API_BASE,
                    "published": datetime.now().isoformat(),
                    "source": "BCV",
                    "type": "economic_data",
                    "rate": float(rate),
                    "currency": "VES/USD",
                }
    except Exception as e:
        logger.warning(f"BCV API error: {e}")

    return {}


def get_bcv_reserves() -> Dict[str, Any]:
    """Obtiene reservas internacionales del BCV"""
    try:
        url = f"{BCV_API_BASE}/estadisticas/reservas-internacionales"

        resp = safe_get(url)
        if resp.status_code == 200:
            # Extraer datos de reservas del HTML
            import re

            reserves_pattern = r"reservas.*?(\d+,\d+)\s*mil"
            matches = re.findall(reserves_pattern, resp.text, re.IGNORECASE)

            if matches:
                reserves = matches[0].replace(",", ".")
                return {
                    "title": f"Reservas BCV: {reserves} millones USD",
                    "summary": f"Las reservas internacionales de Venezuela se ubican en {reserves} millones de dólares.",
                    "link": url,
                    "published": datetime.now().isoformat(),
                    "source": "BCV",
                    "type": "economic_data",
                    "reserves": float(reserves),
                    "currency": "USD",
                }
    except Exception as e:
        logger.warning(f"BCV reserves error: {e}")

    return {}


# ==========================================
# ACLED (Armed Conflict Location & Event Data Project)
# ==========================================
ACLED_API_BASE = "https://api.acleddata.com"
ACLED_API_KEY = os.getenv("ACLED_API_KEY")


def get_acled_venezuela_events(days: int = 30) -> List[Dict[str, Any]]:
    """Obtiene eventos de conflicto en Venezuela de ACLED"""
    results = []

    if not ACLED_API_KEY:
        logger.warning("ACLED API key not configured")
        return results

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        url = f"{ACLED_API_BASE}/acled/read"
        params = {
            "key": ACLED_API_KEY,
            "iso": "VEN",
            "event_date": f"{start_date.strftime('%Y-%m-%d')}|{end_date.strftime('%Y-%m-%d')}",
            "event_date_where": "BETWEEN",
            "format": "json",
        }

        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for event in data.get("data", [])[:20]:  # Limitar a 20 eventos
                results.append(
                    {
                        "title": event.get("event_type", "Evento de conflicto"),
                        "summary": event.get("notes", "")[:280],
                        "link": f"https://acleddata.com/dashboard/#/map/{event.get('data_id', '')}",
                        "published": event.get("event_date", ""),
                        "source": "ACLED",
                        "type": "conflict_data",
                        "location": event.get("location", ""),
                        "fatalities": event.get("fatalities", 0),
                        "actor1": event.get("actor1", ""),
                        "actor2": event.get("actor2", ""),
                    }
                )
    except Exception as e:
        logger.warning(f"ACLED API error: {e}")

    return results


# ==========================================
# INE (Instituto Nacional de Estadística) - Datos demográficos
# ==========================================
INE_API_BASE = "https://www.ine.gob.ve"


def get_ine_population_data() -> Dict[str, Any]:
    """Obtiene datos demográficos del INE"""
    try:
        url = f"{INE_API_BASE}/"

        resp = safe_get(url)
        if resp.status_code == 200:
            return {
                "title": "Datos demográficos INE",
                "summary": "Estadísticas demográficas de Venezuela disponibles en el Instituto Nacional de Estadística.",
                "link": INE_API_BASE,
                "published": datetime.now().isoformat(),
                "source": "INE",
                "type": "demographic_data",
            }
    except Exception as e:
        logger.warning(f"INE API error: {e}")

    return {}


# ==========================================
# OPEC - Datos petroleros
# ==========================================
OPEC_API_BASE = "https://www.opec.org"


def get_opec_venezuela_production() -> Dict[str, Any]:
    """Obtiene datos de producción petrolera de Venezuela desde OPEC"""
    try:
        url = f"{OPEC_API_BASE}/opec_web/en/publications/338.htm"

        resp = safe_get(url)
        if resp.status_code == 200:
            # Extraer datos de producción del HTML
            import re

            production_pattern = r"Venezuela.*?(\d+\.?\d*)\s*(?:thousand|million)"
            matches = re.findall(production_pattern, resp.text, re.IGNORECASE)

            if matches:
                production = matches[0]
                return {
                    "title": f"Producción petrolera Venezuela: {production} bpd",
                    "summary": f"Según datos de la OPEC, Venezuela produce {production} barriles por día.",
                    "link": url,
                    "published": datetime.now().isoformat(),
                    "source": "OPEC",
                    "type": "energy_data",
                    "production": production,
                    "unit": "bpd",
                }
    except Exception as e:
        logger.warning(f"OPEC API error: {e}")

    return {}


# ==========================================
# Función principal para obtener todos los datos abiertos
# ==========================================
def get_all_open_data() -> Dict[str, List[Dict[str, Any]]]:
    """Obtiene datos de todas las APIs de datos abiertos"""
    return {
        "economic": [get_bcv_exchange_rate(), get_bcv_reserves(), get_opec_venezuela_production()],
        "conflict": get_acled_venezuela_events(),
        "demographic": [get_ine_population_data()],
    }
