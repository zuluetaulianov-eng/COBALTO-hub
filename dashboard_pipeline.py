import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from dashboard_state import state
from extractor import fetch_external_news_async, get_own_intel
from osint_registry import FALLBACKS, load_function, load_special_module

logger = logging.getLogger(__name__)

get_social_hub_data = load_function("social_hub", "get_social_hub_data") or FALLBACKS["sources"]
get_serp_data = load_function("osint_serp", "get_serp_data") or FALLBACKS["sources_dict"]
get_realtime_data = load_function("osint_realtime", "get_realtime_data") or FALLBACKS["sources_dict"]
get_pastebin_data = load_function("osint_pastebin", "get_pastebin_data") or FALLBACKS["sources_dict"]
get_satellite_data = load_function("osint_satellite", "get_satellite_data") or FALLBACKS["sources_dict"]
get_emergency_scanner_data = load_function("osint_scanner", "get_emergency_scanner_data") or FALLBACKS["sources_dict"]
get_tiktok_all = load_function("tiktok_extractor", "get_tiktok_all") or FALLBACKS["sources_list"]
get_instagram_all = load_function("instagram_extractor", "get_instagram_all") or FALLBACKS["sources_list"]
get_cyber_scanner_data = load_function("osint_cyber_scanner", "get_cyber_scanner_data") or FALLBACKS["sources_dict"]
get_ransomware_data = load_function("osint_ransomware", "get_ransomware_data") or FALLBACKS["sources_dict"]
get_vencert_data = load_function("osint_vencert", "get_vencert_data") or FALLBACKS["sources_dict"]
get_all_open_data = load_function("open_data_apis", "get_all_open_data") or FALLBACKS["sources_dict"]
get_all_flight_data = load_function("flight_tracker", "get_all_flight_data") or FALLBACKS["sources_dict"]
get_all_vessel_data = load_function("vessel_tracker", "get_all_vessel_data") or FALLBACKS["sources_dict"]
get_all_events_data = load_function("events_tracker", "get_all_events_data") or FALLBACKS["sources_dict"]

_osint_alerts = load_special_module("osint_alerts")
generate_alerts = _osint_alerts.get("generate_alerts", lambda x: ([], {}))
_osint_narrative = load_special_module("osint_narrative")
get_narrative_data = _osint_narrative.get(
    "get_narrative_data", lambda x: {"narratives": [], "total_entries": 0, "timestamp": ""}
)
_osint_socialgraph = load_special_module("osint_socialgraph")
get_social_graph = _osint_socialgraph.get(
    "get_social_graph", lambda x: {"graph": {"nodes": [], "edges": []}, "timestamp": "", "count": 0, "edges": 0}
)
_user_search = load_special_module("user_search")
search_multiple_users_for_dashboard = _user_search.get(
    "search_multiple_users_for_dashboard", lambda x: {"timestamp": "", "cards": []}
)

SOCIAL_SEMAPHORE = asyncio.Semaphore(5)


import re

STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "en", "para", "por", "con", "sin",
    "sobre", "entre", "tras", "hacia", "hasta", "contra", "y", "o", "que", "es", "son", "se", "su", "sus",
    "al", "lo", "como", "mas", "más", "pero", "este", "esta", "estos", "estas"
}

def extract_keywords(text: str) -> set:
    if not text:
        return set()
    words = re.findall(r'\b[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]{3,}\b', text.lower())
    return {w for w in words if w not in STOPWORDS}

def cluster_similar_entries(entries: List[Dict]) -> List[Dict]:
    clustered: List[Dict] = []
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        title_kw = extract_keywords(title)
        entry_kw = extract_keywords(title + " " + summary[:100])
        norm_title = re.sub(r'[^a-z0-9áéíóúñ]', '', title.lower())

        matched_cluster = None
        for existing in clustered:
            ex_title = existing.get("title", "")
            ex_norm_title = existing.get("_norm_title", "")
            ex_title_kw = existing.get("_title_kw", set())
            ex_kw = existing.get("_keywords", set())

            # 1. Coincidencia exacta de título normalizado
            if norm_title and ex_norm_title and norm_title == ex_norm_title:
                matched_cluster = existing
                break

            # 2. Coincidencia por intersección o Jaccard de palabras clave del título
            if title_kw and ex_title_kw:
                t_inter = title_kw.intersection(ex_title_kw)
                t_union = title_kw.union(ex_title_kw)
                t_jaccard = len(t_inter) / len(t_union) if t_union else 0.0
                if t_jaccard >= 0.45 or (len(t_inter) >= 3 and len(title_kw) >= 3):
                    matched_cluster = existing
                    break

            # 3. Coincidencia por Jaccard del cuerpo de texto (título + resumen)
            if ex_kw and entry_kw:
                intersection = entry_kw.intersection(ex_kw)
                union = entry_kw.union(ex_kw)
                jaccard = len(intersection) / len(union) if union else 0.0
                if jaccard >= 0.38:
                    matched_cluster = existing
                    break

        if matched_cluster:
            rel_sources = matched_cluster.setdefault("related_sources", [])
            src_info = {
                "source": entry.get("source", "OSINT"),
                "title": title,
                "link": entry.get("link", "#"),
                "published": entry.get("published", "")
            }
            if not any(s.get("link") == src_info["link"] or (s.get("source") == src_info["source"] and s.get("title") == src_info["title"]) for s in rel_sources):
                rel_sources.append(src_info)
            matched_cluster["sources_count"] = 1 + len(rel_sources)
        else:
            entry_copy = entry.copy()
            entry_copy["_keywords"] = entry_kw
            entry_copy["_title_kw"] = title_kw
            entry_copy["_norm_title"] = norm_title
            entry_copy["related_sources"] = []
            entry_copy["sources_count"] = 1
            clustered.append(entry_copy)

    for item in clustered:
        item.pop("_keywords", None)
        item.pop("_title_kw", None)
        item.pop("_norm_title", None)
    return clustered

async def _build_pipeline_async(priority_only: bool = False) -> Dict[str, Any]:
    state.progress_state.update({"step": "Escaneando RSS", "percentage": 25})
    external_raw = await fetch_external_news_async(priority_only=priority_only)
    own = get_own_intel()

    from datetime import datetime, timedelta, timezone
    import hashlib
    import json
    import config
    import historical_store
    from utils import parse_datetime
    from social_hub import canonicalize_url

    def _normalize_dt(val: Any) -> Any:
        if not val:
            return None
        if isinstance(val, str):
            val = parse_datetime(val)
        if not isinstance(val, datetime):
            return None
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)

    max_age_hours = getattr(config, "ENTRY_MAX_AGE_HOURS", 48)
    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(hours=max_age_hours)

    def _entry_sig(item: dict) -> str:
        title = (item.get("title") or "").strip().lower()
        norm_title = re.sub(r'[^a-z0-9áéíóúñ]', '', title)
        if len(norm_title) >= 10:
            return f"title:{hashlib.md5(norm_title.encode('utf-8')).hexdigest()[:24]}"
        link = item.get("link") or item.get("url") or ""
        canon = canonicalize_url(link)
        if canon and canon != "#":
            return f"link:{canon}"
        src = (item.get("source") or "").strip().lower()
        h = hashlib.md5(f"{src}:{title}".encode("utf-8")).hexdigest()[:24]
        return f"raw:{h}"

    entries_map: Dict[str, Dict] = {}

    # 1. Cargar noticias persistentes en memoria (cache de estado)
    if hasattr(state, "last_entries_cache") and state.last_entries_cache:
        for item in state.last_entries_cache:
            if isinstance(item, dict):
                dt = _normalize_dt(item.get("published_dt") or item.get("published_iso") or item.get("published"))
                if dt and dt >= cutoff_dt:
                    sig = _entry_sig(item)
                    entries_map[sig] = item

    # 2. Cargar historial SQLite persistente (permite mantener noticias al reiniciar el sistema)
    try:
        hist_res = historical_store.query_range(from_dt=cutoff_dt, to_dt=now, limit=3000)
        for item in hist_res.get("entries", []):
            raw = item.get("raw_data")
            entry_dict = item
            if raw and isinstance(raw, str):
                try:
                    entry_dict = json.loads(raw)
                except Exception:
                    pass
            dt = _normalize_dt(entry_dict.get("published_dt") or entry_dict.get("published_iso") or entry_dict.get("published"))
            if dt and dt >= cutoff_dt:
                sig = _entry_sig(entry_dict)
                if sig not in entries_map:
                    entries_map[sig] = entry_dict
    except Exception as hist_err:
        logger.debug(f"[PIPELINE] Error consultando almacenamiento histórico: {hist_err}")

    # 3. Fusionar noticias recién extraídas (sin duplicar)
    new_incoming = []
    for source, items in sorted(external_raw.items()):
        if items:
            for item in items:
                item_copy = item.copy()
                item_copy["source"] = source
                sig = _entry_sig(item_copy)
                if sig not in entries_map:
                    entries_map[sig] = item_copy
                    new_incoming.append(item_copy)

    for item in own:
        item_copy = item.copy()
        item_copy.update({"type": "own", "source": "COBALTO INTEL"})
        if "title" not in item_copy:
            item_copy["title"] = item_copy.get("comment_short", "Reporte Táctico")
        sig = _entry_sig(item_copy)
        if sig not in entries_map:
            entries_map[sig] = item_copy
            new_incoming.append(item_copy)

    # 4. Guardar novedades en SQLite historical_store para persistencia post-reinicio
    if new_incoming:
        try:
            historical_store.store_entries(new_incoming, cycle_type="pipeline")
        except Exception as e:
            logger.debug(f"[HISTORICAL] Error guardando nuevas noticias: {e}")

    # 5. Normalizar timestamps, ordenar por fecha y purgar expiradas (older than max_age_hours)
    all_entries = []
    for sig, entry in entries_map.items():
        dt = _normalize_dt(entry.get("published_dt") or entry.get("published_iso") or entry.get("published"))
        if dt:
            if dt < cutoff_dt:
                continue
            entry["published_dt"] = dt
            entry["published_iso"] = dt.isoformat()
            if not entry.get("published") or "T" not in str(entry.get("published")):
                entry["published"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        all_entries.append(entry)

    def sort_key(x):
        dt = _normalize_dt(x.get("published_dt") or x.get("published_iso") or x.get("published") or x.get("timestamp") or x.get("created_at"))
        if dt is None:
            return 0.0
        try:
            return dt.timestamp()
        except (OSError, OverflowError):
            return 0.0

    all_entries.sort(key=sort_key, reverse=True)

    # 6. Reconstruir lista de fuentes activas con conteos reales acumulados
    active_sources_dict: Dict[str, List] = {}
    for entry in all_entries:
        src = entry.get("source", "OSINT")
        active_sources_dict.setdefault(src, []).append(entry)
    active_sources = [(src, items) for src, items in sorted(active_sources_dict.items())]

    all_entries = cluster_similar_entries(all_entries)
    state.last_entries_cache = all_entries[:2000]

    return {
        "external": external_raw,
        "own": own,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sorted_sources": active_sources,
        "all_entries": all_entries,
    }


def _build_rt_items(flight_data, vessel_data, events_data, open_data) -> List[Dict]:
    rt_items = []
    if isinstance(flight_data, dict):
        for f in flight_data.get("flights", []):
            if isinstance(f, dict) and f.get("callsign"):
                if f.get("is_emergency"):
                    label = f.get("emergency_label", "🚨 EMERGENCIA")
                    f["title"] = f"{label} — {f['callsign']}"
                    f["summary"] = (
                        f"Código Squawk: {f.get('squawk','?')} | "
                        f"Altitud: {f.get('altitude','?')}ft | Vel: {f.get('velocity','?')}kt"
                    )
                    f["_rt_source"] = "🚨 Emergencia Aérea"
                else:
                    f.setdefault("title", f"Vuelo {f['callsign']}")
                    f.setdefault(
                        "summary",
                        f"País: {f.get('origin_country', '?')} | Altitud: {f.get('altitude', '?')}ft | Vel: {f.get('velocity', '?')}kt",
                    )
                    f["_rt_source"] = "Vuelos"
                f.setdefault("link", f"https://globe.adsbexchange.com/?icao={f.get('icao24', '')}")
                f.setdefault("published", flight_data.get("timestamp", ""))
                f.setdefault("source", "OpenSky/ADS-B")
                rt_items.append(f)
    if isinstance(vessel_data, dict):
        for v in vessel_data.get("vessels", []):
            if isinstance(v, dict) and v.get("name"):
                v.setdefault("title", f"Buque {v['name']}")
                v.setdefault(
                    "summary",
                    f"Tipo: {v.get('ship_type', '?')} | Bandera: {v.get('flag', '?')} | Vel: {v.get('speed', '?')}kt",
                )
                v.setdefault("link", f"https://www.marinetraffic.com/es/ais/details/ships/{v.get('mmsi', '')}")
                v.setdefault("published", vessel_data.get("timestamp", ""))
                v.setdefault("source", "MarineTraffic")
                v["_rt_source"] = "Embarcaciones"
                rt_items.append(v)
    if isinstance(events_data, dict):
        for eq in events_data.get("earthquakes", []):
            if isinstance(eq, dict):
                mag = float(eq.get("magnitude", 0))
                eq.setdefault("title", f"Terremoto M{eq.get('magnitude', '?')} - {eq.get('place', '?')}")
                eq.setdefault(
                    "summary", f"Magnitud: {eq.get('magnitude', '?')} | Profundidad: {eq.get('depth', '?')}km"
                )
                eq.setdefault("link", eq.get("url", "https://earthquake.usgs.gov/"))
                eq.setdefault("published", eq.get("time", events_data.get("timestamp", "")))
                eq.setdefault("source", "USGS")
                eq.setdefault("severity", "critical" if mag >= 6 else "warning" if mag >= 4.5 else "info")
                eq["_rt_source"] = "Eventos: Terremotos"
                rt_items.append(eq)
        for wa in events_data.get("weather_alerts", []):
            if isinstance(wa, dict):
                alert_level = wa.get("alert_level", "")
                wa.setdefault("title", f"Alerta climática: {wa.get('city', '?')}")
                wa.setdefault("summary", f"Condición: {wa.get('condition', '?')} | {wa.get('description', '')}")
                wa.setdefault("published", events_data.get("timestamp", ""))
                wa.setdefault("source", "OpenWeatherMap")
                wa.setdefault("severity", "warning" if alert_level in ("Red", "Orange") else "info")
                wa["_rt_source"] = "Eventos: Clima"
                rt_items.append(wa)
        for no in events_data.get("network_outages", []):
            if isinstance(no, dict):
                severity_prefix = "🔴" if no.get("drop_percentage", 0) > 60 else "🟡"
                no.setdefault("title", no.get("title", ""))
                no.setdefault("summary", no.get("summary", ""))
                no.setdefault("published", events_data.get("timestamp", ""))
                no.setdefault("source", "IODA/GeorgiaTech")
                no.setdefault("severity", "critical" if no.get("drop_percentage", 0) > 60 else "warning")
                no["_rt_source"] = f"{severity_prefix} Apagón de Red"
                rt_items.append(no)
        for si in events_data.get("security_incidents", []):
            if isinstance(si, dict):
                si.setdefault("title", si.get("title", "Incidente de seguridad"))
                si["_rt_source"] = "Eventos: Seguridad"
                rt_items.append(si)
    if isinstance(open_data, dict):
        for eco in open_data.get("economic", []):
            if isinstance(eco, dict) and eco.get("title"):
                eco.setdefault("published", "")
                eco.setdefault("source", "Datos Abiertos")
                eco["_rt_source"] = "Open Data: Economía"
                rt_items.append(eco)
        for conflict in open_data.get("conflict", []):
            if isinstance(conflict, dict) and conflict.get("title"):
                conflict.setdefault("published", "")
                conflict.setdefault("source", "ACLED")
                conflict["_rt_source"] = "Open Data: Conflicto"
                rt_items.append(conflict)
        for demo in open_data.get("demographic", []):
            if isinstance(demo, dict) and demo.get("title"):
                demo.setdefault("published", "")
                demo.setdefault("source", "INE")
                demo["_rt_source"] = "Open Data: Demografía"
                rt_items.append(demo)
    if isinstance(flight_data, dict):
        for ap_key, ap in flight_data.get("airports", {}).items():
            if isinstance(ap, dict) and ap.get("lat") is not None and ap.get("lon") is not None:
                rt_items.append(
                    {
                        "title": ap.get("name", ap_key),
                        "latitude": ap["lat"],
                        "longitude": ap["lon"],
                        "source": "Aeropuertos Venezuela",
                        "type": "airport",
                        "published": flight_data.get("timestamp", ""),
                        "summary": f"Aeropuerto en {ap.get('city', '?')}",
                        "_rt_source": "Aeropuertos",
                    }
                )
    if isinstance(events_data, dict):
        for ci in events_data.get("critical_infrastructure", []):
            if isinstance(ci, dict) and ci.get("latitude") is not None and ci.get("longitude") is not None:
                ci.setdefault("title", ci.get("name", ""))
                ci.setdefault("source", "Infraestructura Crítica")
                ci.setdefault("published", "")
                ci["_rt_source"] = "Infraestructura"
                rt_items.append(ci)
        for rz in events_data.get("risk_zones", []):
            if isinstance(rz, dict) and rz.get("polygon"):
                lats = [p["lat"] for p in rz["polygon"] if isinstance(p, dict) and p.get("lat") is not None]
                lons = [p["lon"] for p in rz["polygon"] if isinstance(p, dict) and p.get("lon") is not None]
                if lats and lons:
                    rt_items.append(
                        {
                            "title": rz.get("name", ""),
                            "latitude": sum(lats) / len(lats),
                            "longitude": sum(lons) / len(lons),
                            "source": "Zonas de Riesgo",
                            "type": rz.get("type", "risk_zone"),
                            "published": "",
                            "summary": rz.get("description", ""),
                            "_rt_source": "Zonas de Riesgo",
                        }
                    )
    return rt_items


def _build_geo_points(social_data, rt_items, heavy_cache) -> List[Dict]:
    geo_points = []
    for items in social_data["sources"].values():
        for s in items:
            lat = s.get("lat") if s.get("lat") is not None else s.get("latitude")
            lon = s.get("lon") if s.get("lon") is not None else s.get("longitude")
            if lat is not None and lon is not None:
                geo_points.append(
                    {
                        "lat": float(lat),
                        "lon": float(lon),
                        "title": s.get("title", ""),
                        "source": s.get("source", ""),
                        "type": s.get("type", "default"),
                        "summary": s.get("summary", ""),
                        "date": s.get("published", ""),
                    }
                )
    for r in rt_items:
        lat = r.get("lat") if r.get("lat") is not None else r.get("latitude")
        lon = (
            r.get("lon")
            if r.get("lon") is not None
            else (r.get("longitude") if r.get("longitude") is not None else r.get("lng"))
        )
        if lat is not None and lon is not None:
            geo_points.append(
                {
                    "lat": float(lat),
                    "lon": float(lon),
                    "title": r.get("title", ""),
                    "source": r.get("source", ""),
                    "type": r.get("type", r.get("_rt_source", "realtime")),
                    "summary": r.get("summary", ""),
                    "date": r.get("published", ""),
                }
            )
    return geo_points
