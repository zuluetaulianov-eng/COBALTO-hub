# flight_tracker.py - Rastreo de vuelos en tiempo real para OSINT
# Versión 1.0 - Datos ADS-B de vuelos sobre Venezuela

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import requests

from config import REGIONAL_BBOX

logger = logging.getLogger(__name__)
# ==========================================
# CONFIGURACIÓN
# ==========================================

# Bounding box regional (Ampliada a vecinos y Caribe)
VENEZUELA_BBOX = {
    "north": REGIONAL_BBOX["lat_max"],
    "south": REGIONAL_BBOX["lat_min"],
    "west": REGIONAL_BBOX["lon_min"],
    "east": REGIONAL_BBOX["lon_max"],
}

# Aeropuertos principales de Venezuela
VENEZUELA_AIRPORTS = {
    "SVMI": {"name": "Aeropuerto Internacional de Maiquetía", "lat": 10.6012, "lon": -66.9912, "city": "Caracas"},
    "SVBM": {"name": "Aeropuerto Internacional La Chinita", "lat": 10.5564, "lon": -71.7356, "city": "Maracaibo"},
    "SVVA": {
        "name": "Aeropuerto Internacional Alberto Carnevali",
        "lat": 7.8967,
        "lon": -72.2247,
        "city": "San Cristóbal",
    },
    "SVBC": {"name": "Aeropuerto Internacional Jacinto Lara", "lat": 10.2717, "lon": -69.3367, "city": "Barquisimeto"},
    "SVMD": {"name": "Aeropuerto Internacional del Caribe", "lat": 10.8956, "lon": -63.9689, "city": "Porlamar"},
    "SVVS": {"name": "Aeropuerto Internacional Arturo Michelena", "lat": 8.3122, "lon": -63.5544, "city": "Valencia"},
    "SVPM": {
        "name": "Aeropuerto Internacional José Antonio Anzoátegui",
        "lat": 10.1667,
        "lon": -64.6833,
        "city": "Puerto La Cruz",
    },
    "SVCA": {
        "name": "Aeropuerto Internacional General José Antonio Páez",
        "lat": 7.7167,
        "lon": -70.7333,
        "city": "Acarigua",
    },
    "SVBL": {
        "name": "Aeropuerto Internacional Gral. Bartolomé Salom",
        "lat": 10.3167,
        "lon": -64.6833,
        "city": "Puerto Cabello",
    },
    "SVCO": {"name": "Aeropuerto Internacional de Carupano", "lat": 10.6833, "lon": -63.2667, "city": "Carúpano"},
}

# ==========================================
# OPENSKY NETWORK API (Datos ADS-B gratuitos)
# ==========================================
OPENSKY_API_BASE = "https://opensky-network.org/api"
OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME")
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD")

SQUAWK_EMERGENCY = {
    "7500": "hijacking",
    "7600": "radio_failure",
    "7700": "general_emergency",
}
SQUAWK_EMERGENCY_LABEL = {
    "7500": "🚨 AERONAVE SECUESTRADA",
    "7600": "⚠️ FALLA DE RADIO",
    "7700": "🚨 EMERGENCIA GENERAL",
}

_seen_emergencies = {}  # {icao24: detection_timestamp} — dedup por identidad de aeronave


def _cleanup_emergency_cache(max_age: float = 3600):
    now = time.time()
    stale = [k for k, ts in _seen_emergencies.items() if now - ts > max_age]
    for k in stale:
        del _seen_emergencies[k]
    if stale:
        logger.info(f"[FLIGHT] Limpiadas {len(stale)} aeronaves del caché de emergencias")


def get_flights_over_venezuela() -> List[Dict[str, Any]]:
    """Obtiene vuelos activos sobre Venezuela usando OpenSky Network"""
    _cleanup_emergency_cache()
    flights = []

    try:
        # API de OpenSky para vuelos en bounding box
        url = f"{OPENSKY_API_BASE}/states/all"
        params = {
            "lamin": VENEZUELA_BBOX["south"],
            "lomin": VENEZUELA_BBOX["west"],
            "lamax": VENEZUELA_BBOX["north"],
            "lomax": VENEZUELA_BBOX["east"],
        }

        # Si hay credenciales, usar autenticación para más datos
        auth = None
        if OPENSKY_USERNAME and OPENSKY_PASSWORD:
            auth = (OPENSKY_USERNAME, OPENSKY_PASSWORD)

        resp = requests.get(url, params=params, auth=auth, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            states = data.get("states", [])

            for state in states:
                # Formato de OpenSky: [icao24, callsign, origin_country, time_position,
                # last_contact, longitude, latitude, baro_altitude, on_ground, velocity,
                # true_track, vertical_rate, sensors, geo_altitude, squawk, spi, position_source]

                if len(state) >= 17:
                    icao24 = state[0]
                    callsign = state[1] if state[1] else "N/A"
                    origin_country = state[2]
                    longitude = state[5]
                    latitude = state[6]
                    altitude = state[7] if state[7] else 0
                    on_ground = state[8]
                    velocity = state[9] if state[9] else 0
                    heading = state[10] if state[10] else 0
                    squawk = str(state[14] or "").strip()
                    is_emergency = squawk in SQUAWK_EMERGENCY and icao24 not in _seen_emergencies

                    # Solo incluir vuelos con posición válida
                    if latitude and longitude:
                        entry = {
                            "icao24": icao24,
                            "callsign": callsign,
                            "origin_country": origin_country,
                            "latitude": latitude,
                            "longitude": longitude,
                            "altitude": altitude,
                            "on_ground": on_ground,
                            "velocity": velocity,
                            "heading": heading,
                            "squawk": squawk,
                            "is_emergency": is_emergency,
                            "emergency_type": SQUAWK_EMERGENCY.get(squawk, ""),
                            "emergency_label": SQUAWK_EMERGENCY_LABEL.get(squawk, ""),
                            "type": "flight",
                            "timestamp": datetime.now().isoformat(),
                        }
                        flights.append(entry)
                        if is_emergency:
                            _seen_emergencies[icao24] = time.time()

    except Exception as e:
        logger.warning(f"OpenSky API error: {e}")

    return flights


def get_arrivals_departures(airport_code: str) -> Dict[str, List[Dict[str, Any]]]:
    """Obtiene llegadas y salidas de un aeropuerto específico"""
    result = {"arrivals": [], "departures": []}

    if airport_code not in VENEZUELA_AIRPORTS:
        return result

    try:
        airport = VENEZUELA_AIRPORTS[airport_code]

        # Bounding box pequeño alrededor del aeropuerto (aprox 50km)
        bbox_radius = 0.5
        url = f"{OPENSKY_API_BASE}/states/all"
        params = {
            "lamin": airport["lat"] - bbox_radius,
            "lomin": airport["lon"] - bbox_radius,
            "lamax": airport["lat"] + bbox_radius,
            "lomax": airport["lon"] + bbox_radius,
        }

        auth = None
        if OPENSKY_USERNAME and OPENSKY_PASSWORD:
            auth = (OPENSKY_USERNAME, OPENSKY_PASSWORD)

        resp = requests.get(url, params=params, auth=auth, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            states = data.get("states", [])

            for state in states:
                if len(state) >= 17:
                    callsign = state[1] if state[1] else "N/A"
                    origin_country = state[2]
                    longitude = state[5]
                    latitude = state[6]
                    altitude = state[7] if state[7] else 0
                    on_ground = state[8]
                    velocity = state[9] if state[9] else 0

                    if latitude and longitude:
                        flight_info = {
                            "callsign": callsign,
                            "origin_country": origin_country,
                            "latitude": latitude,
                            "longitude": longitude,
                            "altitude": altitude,
                            "velocity": velocity,
                            "timestamp": datetime.now().isoformat(),
                        }

                        # Clasificar como llegada o salida basado en velocidad y altitud
                        if on_ground and velocity < 50:
                            result["arrivals"].append(flight_info)
                        elif altitude > 1000 and velocity > 150:
                            result["departures"].append(flight_info)

    except Exception as e:
        logger.warning(f"Airport flights error: {e}")

    return result


# ==========================================
# FLIGHTRADAR24 (Alternativa - requiere API key)
# ==========================================
FLIGHTRADAR24_API_BASE = "https://api.flightradar24.com/common/v1"
FLIGHTRADAR24_API_KEY = os.getenv("FLIGHTRADAR24_API_KEY")


def get_flights_flightradar24() -> List[Dict[str, Any]]:
    """Obtiene vuelos usando FlightRadar24 API (requiere API key)"""
    flights = []

    if not FLIGHTRADAR24_API_KEY:
        return flights

    try:
        url = f"{FLIGHTRADAR24_API_BASE}/airport.json"
        params = {
            "code": "SVMI",
            "plugin": "schedule",
            "plugin-setting[schedule][mode]": "departures",
            "plugin-setting[schedule][timestamp]": int(datetime.now().timestamp()),
        }

        headers = {"Authorization": f"Bearer {FLIGHTRADAR24_API_KEY}", "User-Agent": "Mozilla/5.0"}

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", []):
                flights.append(
                    {
                        "callsign": item.get("flight", "N/A"),
                        "origin_country": item.get("airport", {}).get("origin", {}).get("name", "?"),
                        "latitude": item.get("trail", [{}])[0].get("lat", 0),
                        "longitude": item.get("trail", [{}])[0].get("lng", 0),
                        "altitude": item.get("altitude", 0),
                        "velocity": item.get("speed", 0),
                        "heading": item.get("heading", 0),
                        "type": "flight",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
    except Exception as e:
        logger.warning(f"FlightRadar24 API error: {e}")

    return flights


# ==========================================
# ANÁLISIS DE PATRONES DE VUELO
# ==========================================
def analyze_flight_patterns(flights: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analiza patrones en los vuelos detectados"""
    if not flights:
        return {}

    analysis = {
        "total_flights": len(flights),
        "by_country": {},
        "by_altitude": {"low": 0, "medium": 0, "high": 0},
        "avg_altitude": 0,
        "avg_velocity": 0,
        "on_ground": 0,
        "in_air": 0,
        "military_flights": 0,
        "suspicious_flights": [],
    }

    total_altitude = 0
    total_velocity = 0

    for flight in flights:
        # Por país de origen
        country = flight.get("origin_country", "Unknown")
        analysis["by_country"][country] = analysis["by_country"].get(country, 0) + 1

        # Por altitud
        altitude = flight.get("altitude", 0)
        if altitude < 5000:
            analysis["by_altitude"]["low"] += 1
        elif altitude < 20000:
            analysis["by_altitude"]["medium"] += 1
        else:
            analysis["by_altitude"]["high"] += 1

        total_altitude += altitude

        # Velocidad
        velocity = flight.get("velocity", 0)
        total_velocity += velocity

        # En tierra vs aire
        if flight.get("on_ground", False):
            analysis["on_ground"] += 1
        else:
            analysis["in_air"] += 1

        # Vuelos militares (callsigns con patrones específicos)
        callsign = flight.get("callsign", "")
        if callsign and (callsign.startswith("MIL") or callsign.startswith("F-") or callsign.startswith("V-")):
            analysis["military_flights"] += 1

        # Vuelos sospechosos (altitud muy baja, velocidad inusual, etc.)
        if altitude > 0 and altitude < 1000 and velocity > 200:
            analysis["suspicious_flights"].append(
                {"callsign": callsign, "reason": "Low altitude high speed", "altitude": altitude, "velocity": velocity}
            )

    if flights:
        analysis["avg_altitude"] = total_altitude / len(flights)
        analysis["avg_velocity"] = total_velocity / len(flights)

    return analysis


def get_flights_adsbexchange() -> List[Dict[str, Any]]:
    """Fuente alternativa ADS-B real: ADS-B Exchange (público, sin API key)"""
    flights = []
    try:
        # Endpoint real de datos en bbox para región Venezuela/Colombia/Caribe
        data_url = (
            f"https://globe.adsbexchange.com/re-api/?bounds="
            f"{VENEZUELA_BBOX['south']:.1f},{VENEZUELA_BBOX['north']:.1f},"
            f"{VENEZUELA_BBOX['west']:.1f},{VENEZUELA_BBOX['east']:.1f}"
        )
        headers = {
            "User-Agent": "CobaltoHub/9.0 OSINT",
            "Referer": "https://globe.adsbexchange.com/",
        }
        resp = requests.get(data_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            for ac in data.get("ac", []):
                lat = ac.get("lat")
                lon = ac.get("lon")
                if lat is None or lon is None:
                    continue
                flights.append({
                    "icao24": ac.get("hex", ""),
                    "callsign": (ac.get("flight") or ac.get("r") or "N/A").strip(),
                    "origin_country": ac.get("cou", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": ac.get("alt_baro") or ac.get("alt_geom") or 0,
                    "on_ground": ac.get("alt_baro") == "ground",
                    "velocity": ac.get("gs", 0),
                    "heading": ac.get("track", 0),
                    "squawk": str(ac.get("squawk") or ""),
                    "model": ac.get("t", ""),
                    "registration": ac.get("r", ""),
                    "is_emergency": str(ac.get("squawk") or "") in SQUAWK_EMERGENCY,
                    "emergency_label": SQUAWK_EMERGENCY_LABEL.get(str(ac.get("squawk") or ""), ""),
                    "type": "flight",
                    "source": "ADS-B Exchange",
                    "timestamp": datetime.now().isoformat(),
                })
    except Exception as e:
        logger.warning(f"[FLIGHT] ADS-B Exchange error: {e}")
    return flights


def get_all_flight_data() -> Dict[str, Any]:
    """Obtiene todos los datos de vuelos disponibles — fuentes reales solamente."""
    # Fuente 1: OpenSky Network (más confiable, soporta auth)
    flights = get_flights_over_venezuela()

    # Fuente 2: ADS-B Exchange (fallback real, sin auth)
    if not flights:
        logger.info("[FLIGHT] OpenSky vacío — intentando ADS-B Exchange...")
        flights = get_flights_adsbexchange()

    # Sin datos reales — retornar vacío honestamente
    if not flights:
        logger.warning("[FLIGHT] Sin datos ADS-B disponibles en este momento.")

    analysis = analyze_flight_patterns(flights)

    return {
        "flights": flights,
        "analysis": analysis,
        "airports": VENEZUELA_AIRPORTS,
        "timestamp": datetime.now().isoformat(),
        "sources_tried": ["OpenSky Network", "ADS-B Exchange"],
    }
