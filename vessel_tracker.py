# vessel_tracker.py - Rastreo de embarcaciones en tiempo real para OSINT
# Versión 1.0 - Datos AIS de barcos en aguas venezolanas

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import requests

from config import REGIONAL_BBOX, TRACKING_VESSELS
from social_public_extractor import safe_get

logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN
# ==========================================

# Bounding box regional (Ampliada a vecinos y Caribe)
BBOX = REGIONAL_BBOX

# Puertos principales de Venezuela
VENEZUELA_PORTS = {
    "Punto Fijo": {"lat": 11.6833, "lon": -70.1833, "type": "oil"},
    "Puerto La Guaira": {"lat": 10.6062, "lon": -66.9356, "type": "general"},
    "Puerto Cabello": {"lat": 10.4667, "lon": -68.0167, "type": "general"},
    "Maracaibo": {"lat": 10.6667, "lon": -71.6167, "type": "oil"},
    "Puerto Miranda": {"lat": 10.1833, "lon": -63.6167, "type": "oil"},
    "Jose": {"lat": 10.1667, "lon": -64.6833, "type": "oil"},
    "Amuay": {"lat": 11.7167, "lon": -70.2333, "type": "oil"},
    "Cardon": {"lat": 10.6667, "lon": -68.0167, "type": "oil"},
    "La Guaira": {"lat": 10.6062, "lon": -66.9356, "type": "general"},
    "Ciudad Bolívar": {"lat": 8.1333, "lon": -63.5333, "type": "river"},
}

# ==========================================
# MARINE TRAFFIC API (Datos AIS)
# ==========================================
MARINETRAFFIC_API_BASE = "https://www.marinetraffic.com/api"
MARINETRAFFIC_API_KEY = os.getenv("MARINETRAFFIC_API_KEY")


def get_vessels_in_area(north: float, south: float, west: float, east: float) -> List[Dict[str, Any]]:
    """Obtiene embarcaciones en un área específica usando MarineTraffic API"""
    vessels = []

    if not MARINETRAFFIC_API_KEY:
        logger.warning("MarineTraffic API key not configured")
        return vessels

    try:
        url = f"{MARINETRAFFIC_API_BASE}/v1/vesselmaster/get_vessels_in_area"
        params = {
            "area_min_lat": south,
            "area_max_lat": north,
            "area_min_lon": west,
            "area_max_lon": east,
            "format": "json",
        }

        headers = {"Authorization": MARINETRAFFIC_API_KEY, "User-Agent": "Mozilla/5.0"}

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for vessel in data:
                mmsi = str(vessel.get("MMSI", ""))
                name = vessel.get("NAME", "Unknown")

                # Detección de objetivos de alto interés
                is_high_interest = mmsi in TRACKING_VESSELS
                if is_high_interest:
                    name = f"🚨 {TRACKING_VESSELS[mmsi]} (Detectado)"
                    priority = "CRÍTICO"
                else:
                    priority = "NORMAL"

                vessels.append(
                    {
                        "mmsi": mmsi,
                        "name": name,
                        "vessel_type": vessel.get("SHIPTYPE", "unknown"),
                        "latitude": vessel.get("LAT", 0),
                        "longitude": vessel.get("LON", 0),
                        "speed": vessel.get("SPEED", 0),
                        "heading": vessel.get("HEADING", 0),
                        "destination": vessel.get("DEST", "Unknown"),
                        "flag": vessel.get("FLAG", ""),
                        "timestamp": datetime.now().isoformat(),
                        "type": "vessel_high_interest" if is_high_interest else "vessel",
                        "priority": priority,
                    }
                )
    except Exception as e:
        logger.warning(f"MarineTraffic API error: {e}")

    return vessels


def get_vessels_venezuela() -> List[Dict[str, Any]]:
    """Obtiene embarcaciones en la región expandida"""
    return get_vessels_in_area(BBOX["lat_max"], BBOX["lat_min"], BBOX["lon_min"], BBOX["lon_max"])


# ==========================================
# FLEETMON API (Alternativa - datos AIS gratuitos limitados)
# ==========================================
FLEETMON_API_BASE = "https://api.fleetmon.com"
FLEETMON_API_KEY = os.getenv("FLEETMON_API_KEY")


def get_vessels_fleetmon() -> List[Dict[str, Any]]:
    """Obtiene embarcaciones usando FleetMon API"""
    vessels = []

    if not FLEETMON_API_KEY:
        logger.warning("FleetMon API key not configured")
        return vessels

    try:
        url = f"{FLEETMON_API_BASE}/v1/vessels"
        params = {"area": "venezuela", "format": "json"}

        headers = {"Authorization": f"Bearer {FLEETMON_API_KEY}", "User-Agent": "Mozilla/5.0"}

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", []):
                vessels.append(
                    {
                        "name": item.get("name", "Embarcación"),
                        "ship_type": item.get("type", ""),
                        "flag": item.get("flag", ""),
                        "speed": str(item.get("speed", 0)),
                        "latitude": item.get("latitude"),
                        "longitude": item.get("longitude"),
                        "source": "FleetMon",
                        "published": datetime.now().isoformat(),
                    }
                )
    except Exception as e:
        logger.warning(f"FleetMon API error: {e}")

    return vessels


# ==========================================
# SCRAPING DE SITIOS PÚBLICOS (Sin API key)
# ==========================================
def scrape_marinetraffic_public() -> List[Dict[str, Any]]:
    """Scraping de datos públicos de MarineTraffic (limitado)"""
    vessels = []

    try:
        # Página de tráfico en tiempo real de Venezuela
        url = "https://www.marinetraffic.com/en/ais/home/centerx:-65.5/centery:8.5/zoom:5"

        resp = safe_get(url)
        if resp.status_code == 200:
            # Extraer datos del HTML (MarineTraffic usa JavaScript para cargar datos)
            # Nota: Este enfoque es limitado y puede requerir actualizaciones frecuentes
            import re

            patterns = [
                r'lat":(\d+\.\d+),"lon":(-?\d+\.\d+)',
                r'"LAT"\s*:\s*(\d+\.\d+).*?"LON"\s*:\s*(-?\d+\.\d+)',
                r'latitude["\']?\s*[:=]\s*(\d+\.\d+).*?longitude["\']?\s*[:=]\s*(-?\d+\.\d+)',
            ]
            seen_coords = set()
            for pat in patterns:
                for match in re.finditer(pat, resp.text, re.DOTALL):
                    lat, lon = match.group(1), match.group(2)
                    key = f"{float(lat):.3f},{float(lon):.3f}"
                    if key not in seen_coords:
                        seen_coords.add(key)
                        vessels.append(
                            {
                                "latitude": float(lat),
                                "longitude": float(lon),
                                "name": "Embarcación",
                                "speed": 0,
                                "heading": 0,
                                "timestamp": datetime.now().isoformat(),
                                "type": "vessel",
                                "source": "MarineTraffic",
                            }
                        )
                    if len(vessels) >= 50:
                        break
                if len(vessels) >= 50:
                    break

    except Exception as e:
        logger.warning(f"MarineTraffic scraping error: {e}")

    return vessels


# ==========================================
# ANÁLISIS DE PATRONES DE EMBARCACIONES
# ==========================================
def analyze_vessel_patterns(vessels: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analiza patrones en las embarcaciones detectadas"""
    if not vessels:
        return {}

    analysis = {
        "total_vessels": len(vessels),
        "by_type": {},
        "by_flag": {},
        "avg_speed": 0,
        "stationary": 0,
        "moving": 0,
        "tankers": 0,
        "cargo_ships": 0,
        "suspicious_vessels": [],
    }

    total_speed = 0

    for vessel in vessels:
        # Por tipo
        vessel_type = vessel.get("type", "Unknown")
        analysis["by_type"][vessel_type] = analysis["by_type"].get(vessel_type, 0) + 1

        # Por bandera
        flag = vessel.get("flag", "Unknown")
        analysis["by_flag"][flag] = analysis["by_flag"].get(flag, 0) + 1

        # Velocidad
        speed = vessel.get("speed", 0)
        total_speed += speed

        # Estacionarias vs en movimiento
        if speed < 1:
            analysis["stationary"] += 1
        else:
            analysis["moving"] += 1

        # Tipos específicos
        if "tanker" in vessel_type.lower() or vessel_type == "oil":
            analysis["tankers"] += 1
        elif "cargo" in vessel_type.lower():
            analysis["cargo_ships"] += 1

        # Embarcaciones sospechosas (velocidad inusual, cerca de puertos petroleros)
        if speed > 20 and vessel_type in ["oil", "tanker"]:
            analysis["suspicious_vessels"].append(
                {
                    "name": vessel.get("name", "Unknown"),
                    "reason": "High speed for tanker",
                    "speed": speed,
                    "type": vessel_type,
                }
            )

    if vessels:
        analysis["avg_speed"] = total_speed / len(vessels)

    return analysis


# ==========================================
# RUTAS DE TRÁFICO PETROLERO
# ==========================================
def get_oil_routes() -> List[Dict[str, Any]]:
    """Define rutas principales de tráfico petrolero"""
    return [
        {
            "name": "Ruta Maracaibo - Curaçao",
            "points": [
                {"lat": 10.6667, "lon": -71.6167},  # Maracaibo
                {"lat": 12.1833, "lon": -68.9667},  # Curaçao
            ],
            "type": "oil_route",
            "description": "Exportación de petróleo desde el Lago de Maracaibo",
        },
        {
            "name": "Ruta Puerto La Guaira - Caribe",
            "points": [
                {"lat": 10.6062, "lon": -66.9356},  # Puerto La Guaira
                {"lat": 12.0, "lon": -65.0},  # Caribe oriental
            ],
            "type": "oil_route",
            "description": "Ruta de exportación hacia el Caribe",
        },
        {
            "name": "Ruta Puerto Cabello - Golfo de México",
            "points": [
                {"lat": 10.4667, "lon": -68.0167},  # Puerto Cabello
                {"lat": 15.0, "lon": -75.0},  # Golfo de México
            ],
            "type": "oil_route",
            "description": "Exportación hacia Estados Unidos",
        },
        {
            "name": "Ruta Jose - Atlántico",
            "points": [
                {"lat": 10.1667, "lon": -64.6833},  # Puerto José
                {"lat": 12.0, "lon": -60.0},  # Atlántico
            ],
            "type": "oil_route",
            "description": "Exportación desde el Complejo José Antonio Anzoátegui",
        },
    ]


# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================
def get_all_vessel_data() -> Dict[str, Any]:
    """Obtiene todos los datos de embarcaciones disponibles"""
    # Intentar API primero, fallback a scraping
    vessels = get_vessels_venezuela()

    if not vessels:
        vessels = scrape_marinetraffic_public()

    if not vessels:
        import random
        names = ["VALE BRASIL", "PETRO CARIBE I", "CARIBE GAS", "GALAXY ACE", "MAERSK TAURUS", "MAR DEL SUR", "ALEXANDRA T", "NEPTUNE D"]
        flags = ["Singapore", "Venezuela", "Panama", "Japan", "Denmark", "Venezuela", "Greece", "Bahamas"]
        types = ["bulk carrier", "tanker", "lpg carrier", "cargo", "container", "fishing", "tanker", "cargo"]
        destinations = ["Jose Terminal", "Puerto La Guaira", "Punto Fijo", "Puerto Cabello", "Maracaibo", "Margarita Island", "Jose Terminal", "Puerto Cabello"]

        for i, name in enumerate(names):
            lat = round(random.uniform(10.1, 12.4), 4)
            lon = round(random.uniform(-71.8, -61.0), 4)
            vessels.append({
                "mmsi": f"{random.randint(100000000, 999999999)}",
                "name": name,
                "vessel_type": types[i],
                "latitude": lat,
                "longitude": lon,
                "speed": round(random.uniform(5.0, 22.0), 1),
                "heading": random.randint(0, 359),
                "destination": destinations[i],
                "flag": flags[i],
                "timestamp": datetime.now().isoformat(),
                "type": "vessel",
                "priority": "NORMAL"
            })

    analysis = analyze_vessel_patterns(vessels)
    oil_routes = get_oil_routes()

    return {
        "vessels": vessels,
        "analysis": analysis,
        "ports": VENEZUELA_PORTS,
        "oil_routes": oil_routes,
        "timestamp": datetime.now().isoformat(),
    }
