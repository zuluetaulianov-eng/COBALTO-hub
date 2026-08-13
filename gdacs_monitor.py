import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict

import requests

import config
from database import ensure_db, get_connection

logger = logging.getLogger(__name__)

GDACS_API_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

EVENT_TYPE_MAP = {
    "TC": "Ciclón Tropical",
    "FL": "Inundación",
    "WF": "Incendio Forestal",
    "VO": "Volcán",
    "DR": "Sequía",
}

ALERT_MAP = {
    "Red": "critical",
    "Orange": "warning",
    "Green": "info",
}

_SEEN_CACHE = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _centroid(coords: list, geom_type: str) -> tuple:
    if geom_type == "Point":
        return coords[1], coords[0]
    if geom_type == "Polygon" and coords and coords[0]:
        ring = coords[0]
        n = len(ring)
        if n == 0:
            return 0.0, 0.0
        lat = sum(p[1] for p in ring) / n
        lon = sum(p[0] for p in ring) / n
        return lat, lon
    return 0.0, 0.0


def _init_table():
    ensure_db()
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_gdacs_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT,
                    alert_level TEXT,
                    place TEXT,
                    latitude REAL,
                    longitude REAL,
                    seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
    except Exception as e:
        logger.error(f"[GDACS] Error creating table: {e}")


def _load_seen_cache():
    global _SEEN_CACHE
    _SEEN_CACHE = set()
    try:
        with get_connection() as conn:
            for row in conn.fetchall("SELECT event_id FROM processed_gdacs_events"):
                _SEEN_CACHE.add(row[0])
    except Exception as e:
        logger.error(f"[GDACS] Error loading cache: {e}")


def _is_processed(event_id: str) -> bool:
    global _SEEN_CACHE
    if _SEEN_CACHE is None:
        _load_seen_cache()
    return event_id in _SEEN_CACHE


def _mark_processed(event_id: str, event_type: str, alert_level: str, place: str, lat: float, lon: float):
    global _SEEN_CACHE
    if _SEEN_CACHE is not None:
        _SEEN_CACHE.add(event_id)
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_gdacs_events (event_id, event_type, alert_level, place, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, event_type, alert_level, place, lat, lon),
            )
    except Exception as e:
        logger.error(f"[GDACS] Error marking {event_id}: {e}")


def _cleanup(days: int = 3):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        with get_connection() as conn:
            cur = conn.execute("DELETE FROM processed_gdacs_events WHERE seen_at < ?", (cutoff,))
            if cur.rowcount > 0:
                logger.info(f"[GDACS] Purged {cur.rowcount} old events")
    except Exception as e:
        logger.error(f"[GDACS] Error purging: {e}")


def get_gdacs_data() -> Dict[str, Any]:
    if not getattr(config, "GDACS_MONITOR_ENABLED", True):
        return {"weather_alerts": [], "count": 0, "timestamp": ""}

    _init_table()

    target_lat = getattr(config, "SEISMIC_TARGET_LAT", 10.4806)
    target_lon = getattr(config, "SEISMIC_TARGET_LON", -66.9036)
    max_distance = getattr(config, "GDACS_MAX_DISTANCE_KM", 800)
    event_days = getattr(config, "GDACS_EVENT_DAYS", 2)

    alerts = []

    try:
        resp = requests.get(GDACS_API_URL, params={"eventdays": event_days}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[GDACS] API request failed: {e}")
        return {"weather_alerts": [], "count": 0, "timestamp": datetime.now().isoformat()}

    now_ts = datetime.now().isoformat()

    for feature in data.get("features", []):
        event_id = str(feature.get("id", ""))
        if not event_id or _is_processed(event_id):
            continue

        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        event_type = props.get("eventtype", "")
        if event_type == "EQ":
            _mark_processed(event_id, event_type, "", "", 0.0, 0.0)
            continue

        event_name = props.get("eventname", "") or ""
        alert_level = props.get("alertlevel", "Green") or "Green"
        country = props.get("country", "") or ""
        from_date = props.get("fromdate", "") or ""

        lat, lon = _centroid(geom.get("coordinates", []), geom.get("type", "Point"))

        distance = _haversine_km(target_lat, target_lon, lat, lon)
        if distance > max_distance:
            _mark_processed(event_id, event_type, alert_level, f"{event_name} {country}".strip(), lat, lon)
            continue

        readable_type = EVENT_TYPE_MAP.get(event_type, event_type)

        severity = ALERT_MAP.get(alert_level, "info")

        title_parts = [f"{readable_type}"]
        if event_name:
            title_parts.append(event_name)
        title = " - ".join(title_parts)

        sd = props.get("severitydata") or {}
        sev_val = sd.get("severity", "")
        sev_unit = sd.get("severityunit", "")
        severity_str = f"{sev_val} {sev_unit}".strip() if sev_val else ""

        alert_entry = {
            "id": f"gdacs-{event_id}",
            "event_type": event_type,
            "title": title,
            "summary": f"{readable_type} en {country}. {severity_str}".strip(),
            "description": (props.get("description", "") or "")[:200],
            "severity": severity,
            "alert_level": alert_level,
            "latitude": lat,
            "longitude": lon,
            "distance_km": round(distance, 1),
            "country": country,
            "from_date": from_date,
            "url": (props.get("url") or {}).get("report", "") if isinstance(props.get("url"), dict) else "",
            "type": "weather_alert",
            "source": "GDACS",
            "published": now_ts,
        }
        alerts.append(alert_entry)

        _mark_processed(event_id, event_type, alert_level, f"{event_name} {country}".strip(), lat, lon)

    if alerts:
        logger.info(f"[GDACS] {len(alerts)} new events within {max_distance}km of target")

    if _SEEN_CACHE and len(_SEEN_CACHE) > 5000:
        _cleanup()

    return {
        "weather_alerts": alerts,
        "count": len(alerts),
        "timestamp": now_ts,
    }
