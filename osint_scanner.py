from datetime import datetime, timezone
from typing import Any, Dict, List

import feedparser
import requests
import urllib3
from dotenv import load_dotenv

from config import REGIONAL_BBOX

load_dotenv()
urllib3.disable_warnings()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CobaltoHub/9.0"

# Bounding box regional
BBOX = REGIONAL_BBOX

USGS_URL = (
    f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=3"
    f"&minlatitude={BBOX['lat_min']}&maxlatitude={BBOX['lat_max']}"
    f"&minlongitude={BBOX['lon_min']}&maxlongitude={BBOX['lon_max']}"
    f"&orderby=time&limit=10"
)

GDACS_RSS = "https://www.gdacs.org/xml/rss_7.xml"


def _in_region(lat: float, lon: float) -> bool:
    return BBOX["lat_min"] <= lat <= BBOX["lat_max"] and BBOX["lon_min"] <= lon <= BBOX["lon_max"]


def get_usgs_events() -> List[Dict[str, Any]]:
    results = []
    try:
        resp = requests.get(USGS_URL, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for feat in data.get("features", [])[:5]:
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [0, 0, 0])
                lat, lon = coords[1], coords[0]
                mag = props.get("mag", 0)
                place = props.get("place", "Venezuela")
                time_ms = props.get("time", 0)
                ts = (
                    datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc).isoformat()
                    if time_ms
                    else datetime.now().isoformat()
                )
                severity = "ALTA" if mag >= 5 else "MEDIA" if mag >= 4 else "BAJA"
                results.append(
                    {
                        "title": f"[{severity}] 🌊 Sismo M{mag} — {place}",
                        "summary": f"Magnitud: {mag} | Profundidad: {coords[2]}km | {place}",
                        "link": props.get("url", "https://earthquake.usgs.gov/earthquakes/"),
                        "published": ts,
                        "source": "🌊 USGS Earthquake",
                        "type": "emergency",
                        "latitude": lat,
                        "longitude": lon,
                        "severity": severity,
                    }
                )
    except Exception as e:
        print(f"[SCANNER-WARN] USGS: {e}")
    return results


def get_gdacs_alerts() -> List[Dict[str, Any]]:
    results = []
    try:
        feed = feedparser.parse(GDACS_RSS)
        for entry in feed.entries[:8]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            published = entry.get("published", datetime.now().isoformat())
            raw_geo = entry.get("georss_point", "")
            lat = lon = None
            if raw_geo:
                parts = raw_geo.split()
                if len(parts) == 2:
                    try:
                        lat, lon = float(parts[0]), float(parts[1])
                    except Exception:
                        pass
            has_ve = any(
                kw in (title + summary).lower() for kw in ["venezuela", "caracas", "sudamerica", "south america"]
            )
            if has_ve or (lat is not None and _in_region(lat, lon)):
                results.append(
                    {
                        "title": title[:120],
                        "summary": summary[:200],
                        "link": link,
                        "published": published,
                        "source": "🆘 GDACS Emergency",
                        "type": "emergency",
                        "latitude": lat,
                        "longitude": lon,
                    }
                )
    except Exception as e:
        print(f"[SCANNER-WARN] GDACS: {e}")
    return results


def get_emergency_scanner_data() -> Dict[str, Any]:
    items = get_usgs_events() + get_gdacs_alerts()
    if not items:
        items.append(
            {
                "title": "📡 Scanner: Sin emergencias activas en Venezuela",
                "summary": "Monitoreo continuo: USGS Earthquakes + GDACS. No se detectan eventos en este ciclo.",
                "link": "https://www.gdacs.org",
                "published": datetime.now().isoformat(),
                "source": "📡 Emergency Scanner",
                "type": "emergency_ok",
            }
        )
    return {"timestamp": datetime.now().isoformat(), "sources": {"📡 Emergency Scanner": items}, "count": len(items)}


if __name__ == "__main__":
    print("=== TEST EMERGENCY SCANNER ===")
    d = get_emergency_scanner_data()
    print(f"Total: {d['count']} items")
    for src, items in d["sources"].items():
        for i in items[:3]:
            print(f"  {i['title'][:70]}...")
