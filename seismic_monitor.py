import logging
import math
from datetime import datetime
from typing import Any, Dict

import requests

import config
from database import ensure_db, get_connection

logger = logging.getLogger(__name__)

USGS_ALL_DAY_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

_SEEN_CACHE = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _init_seismic_table():
    ensure_db()
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_seismic_events (
                    event_id TEXT PRIMARY KEY,
                    magnitude REAL,
                    place TEXT,
                    latitude REAL,
                    longitude REAL,
                    seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
    except Exception as e:
        logger.error(f"[SEISMIC] Error creating table: {e}")


def _is_event_processed(event_id: str) -> bool:
    global _SEEN_CACHE
    if _SEEN_CACHE is None:
        _load_seen_cache()
    return event_id in _SEEN_CACHE


def _load_seen_cache():
    global _SEEN_CACHE
    _SEEN_CACHE = set()
    try:
        with get_connection() as conn:
            rows = conn.fetchall("SELECT event_id FROM processed_seismic_events")
            for row in rows:
                _SEEN_CACHE.add(row[0])
    except Exception as e:
        logger.error(f"[SEISMIC] Error loading seen cache: {e}")


def _mark_event_processed(event_id: str, magnitude: float, place: str, lat: float, lon: float):
    global _SEEN_CACHE
    if _SEEN_CACHE is not None:
        _SEEN_CACHE.add(event_id)
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_seismic_events (event_id, magnitude, place, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                (event_id, magnitude, place, lat, lon),
            )
    except Exception as e:
        logger.error(f"[SEISMIC] Error marking event {event_id}: {e}")


def _cleanup_old_events(days: int = 3):
    cutoff = (datetime.now() - __import__("datetime").timedelta(days=days)).isoformat()
    try:
        with get_connection() as conn:
            cur = conn.execute("DELETE FROM processed_seismic_events WHERE seen_at < ?", (cutoff,))
            if cur.rowcount > 0:
                logger.info(f"[SEISMIC] Purged {cur.rowcount} old events")
    except Exception as e:
        logger.error(f"[SEISMIC] Error purging: {e}")


def get_seismic_data() -> Dict[str, Any]:
    if not getattr(config, "SEISMIC_MONITOR_ENABLED", True):
        return {"earthquakes": [], "count": 0, "timestamp": ""}

    _init_seismic_table()

    target_lat = getattr(config, "SEISMIC_TARGET_LAT", 10.4806)
    target_lon = getattr(config, "SEISMIC_TARGET_LON", -66.9036)
    max_distance = getattr(config, "SEISMIC_MAX_DISTANCE_KM", 400)
    min_magnitude = getattr(config, "SEISMIC_MIN_MAGNITUDE", 3.5)

    earthquakes = []
    new_alerts = []

    try:
        resp = requests.get(USGS_ALL_DAY_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[SEISMIC] USGS request failed: {e}")
        return {"earthquakes": [], "count": 0, "timestamp": datetime.now().isoformat()}

    now_ts = datetime.now().isoformat()

    for feature in data.get("features", []):
        event_id = feature.get("id", "")
        if not event_id or _is_event_processed(event_id):
            continue

        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])

        if len(coords) < 2:
            continue

        mag = props.get("mag", 0) or 0
        if mag < min_magnitude:
            _mark_event_processed(event_id, mag, props.get("place", "Unknown"), coords[1], coords[0])
            continue

        dist = _haversine_km(target_lat, target_lon, coords[1], coords[0])
        if dist > max_distance:
            _mark_event_processed(event_id, mag, props.get("place", "Unknown"), coords[1], coords[0])
            continue

        entry = {
            "id": event_id,
            "magnitude": round(mag, 1),
            "place": props.get("place", "Unknown"),
            "time": datetime.fromtimestamp(props.get("time", 0) / 1000).isoformat() if props.get("time") else now_ts,
            "depth": round(props.get("depth", 0), 1),
            "latitude": coords[1],
            "longitude": coords[0],
            "distance_km": round(dist, 1),
            "type": "earthquake",
            "alert": props.get("alert"),
            "tsunami": props.get("tsunami", 0),
            "felt": props.get("felt", 0),
            "url": props.get("url", USGS_ALL_DAY_URL),
            "source": "USGS",
            "published": now_ts,
        }
        earthquakes.append(entry)

        if props.get("alert") in ("red", "orange") or props.get("tsunami", 0) == 1 or mag >= 6.0:
            entry["_alert"] = True
            new_alerts.append(entry)

        _mark_event_processed(event_id, mag, entry["place"], coords[1], coords[0])

    if earthquakes:
        logger.info(f"[SEISMIC] {len(earthquakes)} new events within {max_distance}km of target")

    if len(_SEEN_CACHE or set()) > 5000:
        _cleanup_old_events()

    return {
        "earthquakes": earthquakes,
        "count": len(earthquakes),
        "timestamp": now_ts,
    }
