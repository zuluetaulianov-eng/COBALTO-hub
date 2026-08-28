import asyncio
import logging
from datetime import datetime
from typing import Dict

import config
from osint_registry import FALLBACKS, load_function
from utils import parse_datetime

logger = logging.getLogger(__name__)

get_all_flight_data = load_function("flight_tracker", "get_all_flight_data") or FALLBACKS["sources_dict"]
get_all_vessel_data = load_function("vessel_tracker", "get_all_vessel_data") or FALLBACKS["sources_dict"]
get_all_events_data = load_function("events_tracker", "get_all_events_data") or FALLBACKS["sources_dict"]
get_all_open_data = load_function("open_data_apis", "get_all_open_data") or FALLBACKS["sources_dict"]
get_social_hub_data = load_function("social_hub", "get_social_hub_data") or FALLBACKS["sources"]
get_serp_data = load_function("osint_serp", "get_serp_data") or FALLBACKS["sources_dict"]
get_pastebin_data = load_function("osint_pastebin", "get_pastebin_data") or FALLBACKS["sources_dict"]
get_satellite_data = load_function("osint_satellite", "get_satellite_data") or FALLBACKS["sources_dict"]
get_emergency_scanner_data = load_function("osint_scanner", "get_emergency_scanner_data") or FALLBACKS["sources_dict"]
get_tiktok_all = load_function("tiktok_extractor", "get_tiktok_all") or FALLBACKS["sources_list"]
get_instagram_all = load_function("instagram_extractor", "get_instagram_all") or FALLBACKS["sources_list"]
get_cyber_scanner_data = load_function("osint_cyber_scanner", "get_cyber_scanner_data") or FALLBACKS["sources_dict"]
get_ransomware_data = load_function("osint_ransomware", "get_ransomware_data") or FALLBACKS["sources_dict"]
get_vencert_data = load_function("osint_vencert", "get_vencert_data") or FALLBACKS["sources_dict"]
get_ivss_data = load_function("osint_ivss", "get_ivss_data") or FALLBACKS["sources_dict"]

# --- Backend Caching System (Evita sobrecarga en accesos multi-usuario) ---
_realtime_cache = None
_realtime_cache_time = None
_realtime_lock = asyncio.Lock()

_social_cache = None
_social_cache_time = None
_social_lock = asyncio.Lock()


async def get_realtime_sensors_data() -> Dict:
    global _realtime_cache, _realtime_cache_time
    async with _realtime_lock:
        now = datetime.now()
        # Caché de 5 minutos (300 segundos)
        if _realtime_cache and _realtime_cache_time and (now - _realtime_cache_time).total_seconds() < 300:
            logger.info(
                "[CACHE] Sirviendo datos de sensores en tiempo real desde caché backend (Evitando sobrecarga en multi-usuario)."
            )
            return _realtime_cache

        logger.info("[SENSORS] Iniciando lectura física de sensores en tiempo real...")
        loop = asyncio.get_running_loop()
        sensor_funcs = [
            ("flight_data", get_all_flight_data),
            ("vessel_data", get_all_vessel_data),
            ("events_data", get_all_events_data),
            ("open_data", get_all_open_data),
        ]

        async def _run_sensor(fn):
            try:
                return await loop.run_in_executor(None, fn)
            except Exception as e:
                logger.warning(f"Sensor tiempo real {fn.__name__}: {e}")
                return {}

        results = await asyncio.gather(*[_run_sensor(fn) for _, fn in sensor_funcs])
        final_res = {name: results[i] for i, (name, _) in enumerate(sensor_funcs)}
        final_res["timestamp"] = now.isoformat()

        flight_data = final_res.get("flight_data", {})
        vessel_data = final_res.get("vessel_data", {})
        events_data = final_res.get("events_data", {})
        open_data = final_res.get("open_data", {})

        if not isinstance(flight_data, dict):
            flight_data = {"flights": []}
            final_res["flight_data"] = flight_data

        if not isinstance(vessel_data, dict):
            vessel_data = {"vessels": []}
            final_res["vessel_data"] = vessel_data

        if isinstance(flight_data, dict):
            for f in flight_data.get("flights", []):
                if isinstance(f, dict) and f.get("callsign"):
                    f.setdefault("title", f"Vuelo {f['callsign']}")
                    f.setdefault(
                        "summary",
                        f"País: {f.get('origin_country', '?')} | Altitud: {f.get('altitude', '?')}ft | Vel: {f.get('velocity', '?')}kt",
                    )
                    f.setdefault("link", f"https://globe.adsbexchange.com/?icao={f.get('icao24', '')}")
                    f.setdefault("published", flight_data.get("timestamp", ""))
                    f.setdefault("source", "OpenSky/ADS-B")
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
        if isinstance(events_data, dict):
            for eq in events_data.get("earthquakes", []):
                if isinstance(eq, dict):
                    eq.setdefault("title", f"Terremoto M{eq.get('magnitude', '?')} - {eq.get('place', '?')}")
                    eq.setdefault(
                        "summary", f"Magnitud: {eq.get('magnitude', '?')} | Profundidad: {eq.get('depth', '?')}km"
                    )
                    eq.setdefault("link", eq.get("url", "https://earthquake.usgs.gov/"))
                    eq.setdefault("published", eq.get("time", events_data.get("timestamp", "")))
                    eq.setdefault("source", "USGS")
            for wa in events_data.get("weather_alerts", []):
                if isinstance(wa, dict):
                    wa.setdefault("title", f"Alerta climática: {wa.get('city', '?')}")
                    wa.setdefault("summary", f"Condición: {wa.get('condition', '?')} | {wa.get('description', '')}")
                    wa.setdefault("link", f"https://openweathermap.org/city/{wa.get('city_id', '')}")
                    wa.setdefault("published", events_data.get("timestamp", ""))
                    wa.setdefault("source", "OpenWeatherMap")
            for si in events_data.get("security_incidents", []):
                if isinstance(si, dict):
                    si.setdefault("title", si.get("title", "Incidente de seguridad"))
                    si.setdefault("summary", si.get("summary", ""))
                    si.setdefault("source", "Eventos: Seguridad")
        if isinstance(open_data, dict):
            for eco in open_data.get("economic", []):
                if isinstance(eco, dict):
                    eco.setdefault("published", "")
                    eco.setdefault("source", "Datos Abiertos")
            for conflict in open_data.get("conflict", []):
                if isinstance(conflict, dict):
                    conflict.setdefault("published", "")
                    conflict.setdefault("source", "ACLED")
            for demo in open_data.get("demographic", []):
                if isinstance(demo, dict):
                    demo.setdefault("published", "")
                    demo.setdefault("source", "INE")

        _realtime_cache = final_res
        _realtime_cache_time = now
        return final_res


async def get_social_sensors_data() -> Dict:
    global _social_cache, _social_cache_time
    async with _social_lock:
        now = datetime.now()
        # Caché de 5 minutos (300 segundos)
        if _social_cache and _social_cache_time and (now - _social_cache_time).total_seconds() < 300:
            logger.info(
                "[CACHE] Sirviendo datos de sensores sociales desde caché backend (Evitando sobrecarga en multi-usuario)."
            )
            return _social_cache

        logger.info("[SENSORS] Iniciando lectura física de sensores de Radar Social...")
        social_sensors = [
            ("COBALTO HUB", get_social_hub_data),
            ("SERP", get_serp_data),
            ("Pastebin", get_pastebin_data),
            ("Satélite", get_satellite_data),
            ("Scanner", get_emergency_scanner_data),
            ("TikTok", get_tiktok_all),
            ("Instagram", get_instagram_all),
            ("Cyber Scanner", get_cyber_scanner_data),
            ("Ransomware", get_ransomware_data),
            ("VenCERT", get_vencert_data),
            ("IVSS Oficial", get_ivss_data),
        ]

        async def _call_sensor(name, fn):
            try:
                if asyncio.iscoroutinefunction(fn):
                    res = await fn()
                else:
                    res = await asyncio.to_thread(fn)
                return name, res
            except Exception as e:
                logger.warning(f"Lazy-sensor {name}: {e}")
                return name, None

        from datetime import timedelta, timezone
        cutoff_time = now.astimezone(timezone.utc) - timedelta(hours=config.ENTRY_MAX_AGE_HOURS)

        results = await asyncio.gather(*[_call_sensor(name, fn) for name, fn in social_sensors])
        sources = {}
        total = 0
        for name, res in results:
            if res is None:
                continue
            if isinstance(res, dict) and "sources" in res:
                for s, items in res["sources"].items():
                    if items:
                        key = f"{name}: {s}" if s != name else name
                        filtered_items = []
                        for item in items:
                            if isinstance(item, dict):
                                item.setdefault("title", "Sin título")
                                item.setdefault("link", "#")
                                item.setdefault("summary", "")
                                item.setdefault("published", "")
                                item.setdefault("source", key)

                                # Date filter
                                pub_val = (
                                    item.get("published") or
                                    item.get("published_iso") or
                                    item.get("date") or
                                    item.get("timestamp") or
                                    item.get("time")
                                )
                                if pub_val:
                                    dt = parse_datetime(pub_val)
                                    if dt and dt < cutoff_time:
                                        continue
                                filtered_items.append(item)
                        if filtered_items:
                            sources[key.strip(": ")] = filtered_items
                            total += len(filtered_items)
            elif isinstance(res, list):
                filtered_items = []
                for item in res:
                    if isinstance(item, dict):
                        item.setdefault("title", "Sin título")
                        item.setdefault("link", "#")
                        item.setdefault("summary", "")
                        item.setdefault("published", "")
                        item.setdefault("source", name)

                        # Date filter
                        pub_val = (
                            item.get("published") or
                            item.get("published_iso") or
                            item.get("date") or
                            item.get("timestamp") or
                            item.get("time")
                        )
                        if pub_val:
                            dt = parse_datetime(pub_val)
                            if dt and dt < cutoff_time:
                                continue
                        filtered_items.append(item)
                if filtered_items:
                    sources[name] = filtered_items
                    total += len(filtered_items)

        final_res = {"sources": sources, "count": total, "timestamp": now.isoformat()}
        _social_cache = final_res
        _social_cache_time = now
        return final_res
