import logging
import math
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Umbrales de correlacion
CORRELATION_RADIUS_KM = 300        # radio maximo entre eventos para considerarse correlacionados
CORRELATION_TIME_WINDOW_H = 24     # ventana de tiempo maxima entre eventos (horas)
CORRELATION_MIN_EVENTS = 2         # minimo de eventos para formar un composite


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia Haversine entre dos puntos geograficos en km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _parse_ts(val) -> datetime:
    """Convierte varios formatos de timestamp a datetime."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val)
    if isinstance(val, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
            try:
                return datetime.strptime(val[:19], fmt)
            except (ValueError, IndexError):
                continue
    return datetime.now()


def _extract_events(source: str, data: dict) -> list:
    """Extrae eventos con coordenadas desde cada fuente."""
    events = []

    # Sismos (USGS)
    if source == "seismic":
        for eq in data.get("earthquakes", []):
            lat = eq.get("latitude")
            lng = eq.get("longitude")
            if lat is not None and lng is not None:
                events.append({
                    "source_type": "earthquake",
                    "id": eq.get("id", ""),
                    "title": eq.get("place", "Sismo"),
                    "latitude": lat,
                    "longitude": lng,
                    "timestamp": _parse_ts(eq.get("time", "")),
                    "magnitude": eq.get("magnitude", 0),
                    "depth": eq.get("depth", 0),
                    "severity": eq.get("alert", "info"),
                    "raw": eq,
                })

    # Alertas GDACS
    elif source == "gdacs":
        for wa in data.get("weather_alerts", []):
            lat = wa.get("latitude")
            lng = wa.get("longitude")
            if lat is not None and lng is not None:
                events.append({
                    "source_type": "weather_alert",
                    "id": wa.get("id", ""),
                    "title": wa.get("title", "Alerta meteorologica"),
                    "latitude": lat,
                    "longitude": lng,
                    "timestamp": _parse_ts(wa.get("published", "")),
                    "severity": wa.get("severity", "info"),
                    "event_type": wa.get("event_type", ""),
                    "country": wa.get("country", ""),
                    "raw": wa,
                })

    # Apagones de red (ASN) - usamos coordenadas del centro de Venezuela
    elif source == "asn":
        venezuela_center = {"lat": 6.4238, "lon": -66.5897}
        for outage in data.get("network_outages", []):
            events.append({
                "source_type": "network_outage",
                "id": outage.get("id", ""),
                "title": outage.get("title", "Apagon de red"),
                "latitude": venezuela_center["lat"],
                "longitude": venezuela_center["lon"],
                "timestamp": _parse_ts(outage.get("published", "")),
                "drop_percentage": outage.get("drop_percentage", 0),
                "provider": outage.get("provider", ""),
                "severity": outage.get("severity", "info"),
                "raw": outage,
            })

    # Eventos de seguridad / protestas / infraestructura critica
    elif source == "events":
        for sec in data.get("security_incidents", []):
            lat = sec.get("latitude")
            lng = sec.get("longitude")
            if lat is not None and lng is not None:
                events.append({
                    "source_type": "security_incident",
                    "id": sec.get("id", sec.get("link", "")),
                    "title": sec.get("title", "Incidente de seguridad"),
                    "latitude": lat,
                    "longitude": lng,
                    "timestamp": _parse_ts(sec.get("published", "")),
                    "severity": sec.get("severity", "info"),
                    "raw": sec,
                })
        for prot in data.get("protests", []):
            lat = prot.get("latitude")
            lng = prot.get("longitude")
            if lat is not None and lng is not None:
                events.append({
                    "source_type": "protest",
                    "id": prot.get("id", prot.get("link", "")),
                    "title": prot.get("title", "Protesta"),
                    "latitude": lat,
                    "longitude": lng,
                    "timestamp": _parse_ts(prot.get("published", "")),
                    "severity": prot.get("severity", "medium"),
                    "raw": prot,
                })

    return events


def correlate(seismic_data: dict, gdacs_data: dict, asn_data: dict, events_data: dict) -> List[Dict[str, Any]]:
    """
    Correlaciona eventos de multiples fuentes por proximidad geografica y temporal.
    Retorna lista de composite_events.
    """
    all_events = []
    all_events.extend(_extract_events("seismic", seismic_data if seismic_data else {}))
    all_events.extend(_extract_events("gdacs", gdacs_data if gdacs_data else {}))
    all_events.extend(_extract_events("asn", asn_data if asn_data else {}))
    all_events.extend(_extract_events("events", events_data if events_data else {}))

    if len(all_events) < CORRELATION_MIN_EVENTS:
        return []

    composite_events = []
    used_pairs = set()

    for i in range(len(all_events)):
        for j in range(i + 1, len(all_events)):
            a, b = all_events[i], all_events[j]

            # Mismo tipo de fuente -> no correlacionar
            if a["source_type"] == b["source_type"]:
                continue

            # Distancia geografica
            dist = haversine_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
            if dist > CORRELATION_RADIUS_KM:
                continue

            # Ventana de tiempo
            diff_h = abs((a["timestamp"] - b["timestamp"]).total_seconds()) / 3600
            if diff_h > CORRELATION_TIME_WINDOW_H:
                continue

            # Evitar duplicados
            pair_key = tuple(sorted([a["id"], b["id"]]))
            if pair_key in used_pairs:
                continue
            used_pairs.add(pair_key)

            severity = "critico" if "critical" in (a.get("severity", ""), b.get("severity", "")) else "urgente"

            composite_events.append({
                "type": "composite_event",
                "severity": severity,
                "title": f"Correlacion: {a['source_type']} + {b['source_type']}",
                "description": (
                    f"Eventos correlacionados a {dist:.0f}km y {diff_h:.1f}h de diferencia. "
                    f"{a['title']} | {b['title']}"
                ),
                "sources": [a["source_type"], b["source_type"]],
                "events": [a["id"], b["id"]],
                "distance_km": round(dist, 1),
                "time_delta_h": round(diff_h, 1),
                "centroid_lat": (a["latitude"] + b["latitude"]) / 2,
                "centroid_lon": (a["longitude"] + b["longitude"]) / 2,
                "timestamp": datetime.now().isoformat(),
            })

    if composite_events:
        logger.info(f"[CORRELATION] {len(composite_events)} eventos compuestos generados")

    return composite_events
