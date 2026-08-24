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


def get_vessels_aishub() -> List[Dict[str, Any]]:
    """AIS Hub — datos AIS gratuitos para usuarios registrados (sin clave en modo anónimo limitado)"""
    vessels = []
    try:
        # AIS Hub ofrece un endpoint JSON público para áreas de alta densidad
        # Bbox: Venezuela + Colombia + Caribe
        bbox = BBOX
        url = "https://data.aishub.net/ws.php"
        params = {
            "username": "ZS2313",  # cuenta pública de demostración
            "format": "1",
            "output": "json",
            "compress": "0",
            "latmin": bbox["lat_min"],
            "latmax": bbox["lat_max"],
            "lonmin": bbox["lon_min"],
            "lonmax": bbox["lon_max"],
        }
        headers = {"User-Agent": "CobaltoHub/9.0 OSINT"}
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            # AISHub devuelve [header_dict, [vessel_list]]
            vessels_raw = data[1] if isinstance(data, list) and len(data) > 1 else []
            for v in vessels_raw:
                lat = v.get("LATITUDE")
                lon = v.get("LONGITUDE")
                if lat is None or lon is None:
                    continue
                mmsi = str(v.get("MMSI", ""))
                name = v.get("NAME", "").strip() or f"MMSI:{mmsi}"
                is_high_interest = mmsi in TRACKING_VESSELS
                if is_high_interest:
                    name = f"🚨 {TRACKING_VESSELS[mmsi]} (Detectado)"
                vessels.append({
                    "mmsi": mmsi,
                    "name": name,
                    "vessel_type": v.get("SHIPTYPE", ""),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "speed": round(float(v.get("SOG", 0)) / 10, 1),
                    "heading": v.get("COG", 0),
                    "destination": v.get("DESTINATION", "").strip(),
                    "flag": v.get("FLAG", ""),
                    "imo": str(v.get("IMO", "")),
                    "timestamp": datetime.now().isoformat(),
                    "type": "vessel_high_interest" if is_high_interest else "vessel",
                    "priority": "CRÍTICO" if is_high_interest else "NORMAL",
                    "source": "AIS Hub",
                })
    except Exception as e:
        logger.warning(f"[VESSEL] AIS Hub error: {e}")
    return vessels


def get_vessels_myshiptracking() -> List[Dict[str, Any]]:
    """MyShipTracking — feed JSON público sin clave para área regional"""
    vessels = []
    try:
        bbox = BBOX
        url = "https://www.myshiptracking.com/requests/vesselsonmap.php"
        params = {
            "type": "json",
            "minlat": bbox["lat_min"],
            "maxlat": bbox["lat_max"],
            "minlon": bbox["lon_min"],
            "maxlon": bbox["lon_max"],
            "zoom": 5,
        }
        headers = {
            "User-Agent": "CobaltoHub/9.0 OSINT",
            "Referer": "https://www.myshiptracking.com/",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            for v in (data if isinstance(data, list) else data.get("vessels", [])):
                lat = v.get("lat") or v.get("latitude")
                lon = v.get("lon") or v.get("longitude")
                if not lat or not lon:
                    continue
                mmsi = str(v.get("mmsi", ""))
                vessels.append({
                    "mmsi": mmsi,
                    "name": (v.get("name") or v.get("shipname") or f"MMSI:{mmsi}").strip(),
                    "vessel_type": v.get("type_name") or v.get("type", ""),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "speed": float(v.get("speed") or v.get("sog") or 0),
                    "heading": float(v.get("course") or v.get("cog") or 0),
                    "destination": (v.get("destination") or "").strip(),
                    "flag": v.get("flag") or v.get("country", ""),
                    "timestamp": datetime.now().isoformat(),
                    "type": "vessel",
                    "priority": "NORMAL",
                    "source": "MyShipTracking",
                })
    except Exception as e:
        logger.warning(f"[VESSEL] MyShipTracking error: {e}")
    return vessels


# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================
def get_all_vessel_data() -> Dict[str, Any]:
    """Obtiene todos los datos de embarcaciones — fuentes reales solamente."""
    # Fuente 1: MarineTraffic (con API key si disponible)
    vessels = get_vessels_venezuela()

    # Fuente 2: AIS Hub (gratuito, datos reales)
    if not vessels:
        logger.info("[VESSEL] MarineTraffic vacío — intentando AIS Hub...")
        vessels = get_vessels_aishub()

    # Fuente 3: MyShipTracking (scraping público)
    if not vessels:
        logger.info("[VESSEL] AIS Hub vacío — intentando MyShipTracking...")
        vessels = get_vessels_myshiptracking()

    # Sin datos reales — retornar vacío honestamente
    if not vessels:
        logger.warning("[VESSEL] Sin datos AIS disponibles en este momento.")

    analysis = analyze_vessel_patterns(vessels)
    oil_routes = get_oil_routes()

    return {
        "vessels": vessels,
        "analysis": analysis,
        "ports": VENEZUELA_PORTS,
        "oil_routes": oil_routes,
        "timestamp": datetime.now().isoformat(),
        "sources_tried": ["MarineTraffic", "AIS Hub", "MyShipTracking"],
    }
