"""
dashboard.py v9.1 - Refactorizado en submódulos especializados

Submódulos:
  - dashboard_state.py: Estado global AppState
  - dashboard_geocontext.py: Categorización geográfica y semáforos
  - dashboard_heavy.py: Análisis pesado (onion, dorks, IA, briefing)
  - dashboard_pipeline.py: Pipeline de extracción y construcción de datos
  - dashboard_sensors.py: Sensores bajo demanda (realtime, social)
"""

import asyncio
import concurrent.futures
import logging
import time as time_mod
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import config as config_mod
import metrics
from dashboard_geocontext import categorize_source
from dashboard_pipeline import _build_geo_points, _build_pipeline_async, _build_rt_items
from dashboard_state import state
from event_radar import radar
from extractor import get_circuit_breaker_count
from osint_registry import FALLBACKS, load_function, load_special_module
from security_utils import sanitize_for_json
from utils import parse_datetime

logger = logging.getLogger(__name__)

# ── Cache de verificación Tor ──
_tor_active_cache = None
_tor_active_cache_time = 0.0


async def is_tor_active() -> bool:
    global _tor_active_cache, _tor_active_cache_time
    now = time_mod.time()
    if now - _tor_active_cache_time > 60:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", config_mod.TOR_SOCKS_PORT), timeout=1.5)
            writer.close()
            await writer.wait_closed()
            _tor_active_cache = True
        except Exception:
            _tor_active_cache = False
        _tor_active_cache_time = now
    return _tor_active_cache or False


# ── Módulos especiales (multi-función) ──
_osint_fakenews = load_special_module("osint_fakenews")
analyze_batch_news = _osint_fakenews.get("analyze_batch_news", lambda x: [])
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
get_realtime_metrics = _osint_socialgraph.get("get_realtime_metrics", lambda x: {"total_nodes": 0, "total_edges": 0})
get_geographic_locations = _osint_socialgraph.get("get_geographic_locations", lambda x: [])
calculate_activity_heatmap = _osint_socialgraph.get("calculate_activity_heatmap", lambda x: {})
detect_bridge_nodes = _osint_socialgraph.get("detect_bridge_nodes", lambda x: [])
_user_search = load_special_module("user_search")
search_multiple_users_for_dashboard = _user_search.get(
    "search_multiple_users_for_dashboard", lambda x: {"timestamp": "", "cards": []}
)
get_influential_users = _user_search.get(
    "get_influential_users", lambda force_refresh=False: {"profile_changes": []}
)

# ── Módulos sociales estándar ──
get_social_hub_data = load_function("social_hub", "get_social_hub_data") or FALLBACKS["sources"]
get_serp_data = load_function("osint_serp", "get_serp_data") or FALLBACKS["sources_dict"]
get_realtime_data = load_function("osint_realtime", "get_realtime_data") or FALLBACKS["sources_dict"]
get_pastebin_data = load_function("osint_pastebin", "get_pastebin_data") or FALLBACKS["sources_dict"]
get_satellite_data = load_function("osint_satellite", "get_satellite_data") or FALLBACKS["sources_dict"]
get_emergency_scanner_data = load_function("osint_scanner", "get_emergency_scanner_data") or FALLBACKS["sources_dict"]
get_tiktok_all = load_function("tiktok_extractor", "get_tiktok_all") or FALLBACKS["sources_list"]
get_instagram_all = load_function("instagram_extractor", "get_instagram_all") or FALLBACKS["sources_list"]
get_onion_data = load_function("osint_onion", "get_onion_data") or FALLBACKS["sources_dict"]
get_social_dorks_sync = load_function("osint_social_dorks", "get_social_dorks_sync") or FALLBACKS["sources_dict"]
get_cyber_scanner_data = load_function("osint_cyber_scanner", "get_cyber_scanner_data") or FALLBACKS["sources_dict"]
get_ransomware_data = load_function("osint_ransomware", "get_ransomware_data") or FALLBACKS["sources_dict"]
get_vencert_data = load_function("osint_vencert", "get_vencert_data") or FALLBACKS["sources_dict"]
get_all_open_data = load_function("open_data_apis", "get_all_open_data") or FALLBACKS["sources_dict"]
get_all_flight_data = load_function("flight_tracker", "get_all_flight_data") or FALLBACKS["sources_dict"]
get_all_vessel_data = load_function("vessel_tracker", "get_all_vessel_data") or FALLBACKS["sources_dict"]
get_all_events_data = load_function("events_tracker", "get_all_events_data") or FALLBACKS["sources_dict"]
from asn_monitor import get_network_outages
from correlation_engine import correlate as correlate_events
from gdacs_monitor import get_gdacs_data
from seismic_monitor import get_seismic_data

get_network_resilience_data = load_function("osint_network_resilience", "get_network_resilience_data") or FALLBACKS["sources_dict"]
get_sigint_alerts_data = load_function("osint_sigint_alerts", "get_sigint_alerts_data") or FALLBACKS["sources_dict"]
get_botnet_detector_data = load_function("osint_botnet_detector", "get_botnet_detector_data") or FALLBACKS["sources_dict"]
get_finint_data = load_function("osint_finint", "get_finint_data") or FALLBACKS["sources_dict"]

# ── Thread pool dedicado (evita saturar el pool por defecto de asyncio) ──
_DASHBOARD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=16)

# ── Semáforos de concurrencia ──
SOCIAL_SEMAPHORE = asyncio.Semaphore(8)


def get_empty_context() -> Dict[str, Any]:
    import config
    return {
        "PAGE_TITLE": config.PAGE_TITLE,
        "SITE_URL": config.SITE_URL,
        "PAGE_DESCRIPTION": config.PAGE_DESCRIPTION,
        "LOGO_PATH": config.LOGO_PATH,
        "LOGO_FALLBACK": config.LOGO_FALLBACK,
        "ENTRY_MAX_AGE_HOURS": config.ENTRY_MAX_AGE_HOURS,
        "TELEGRAM_CHANNEL": config.TELEGRAM_CHANNEL,
        "ABOUT_US_CONTENT": config.ABOUT_US_CONTENT,
        "NOTES_INFORMATIVAS": config.NOTES_INFORMATIVAS,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "all_entries": [],
        "ai_geopoints": [],
        "geo_points": [],
        "social_data": {"sources": {}, "count": 0, "timestamp": ""},
        "category_groups": {},
        "alerts": [],
        "alert_counts": {"total": 0, "critico": 0, "urgente": 0, "atencion": 0},
        "global_briefing": "",
        "reliability": {"total": 0},
        "reliability_score": 100,
        "reliability_color": "#00ffaa",
        "total_sources": 0,
        "tor_active": False,
        "rt_items": [],
        "own_posts": [],
        "narrative_analysis": {"narratives": [], "total_entries": 0, "timestamp": ""},
        "social_graph": {"graph": {"nodes": [], "edges": []}},
        "cb_count": 0,
        "composite_events": [],
        "cycle_id": 0,
        "cycle_start_ts": "",
        "entity_explorer_data": {"entities": [], "stats": {"total_entities": 0, "ofac_matches": 0, "wikidata_linked": 0}},
    }


async def get_dashboard_data(priority_only: bool = False) -> Dict[str, Any]:
    try:
        state.progress_state.update({"step": "Desplegando Sensores", "percentage": 20})

        import config
        osint_active = getattr(config, "MODULE_OSINT_ACTIVE", True)
        social_active = getattr(config, "MODULE_SOCIAL_ACTIVE", True)

        social_tasks = []
        if osint_active:
            social_tasks.append((get_social_hub_data, "COBALTO HUB"))

        if not priority_only:
            if osint_active:
                social_tasks += [
                    (get_serp_data, "SERP"),
                    (get_pastebin_data, "Pastebin"),
                    (get_satellite_data, "Satélite"),
                    (get_emergency_scanner_data, "Scanner"),
                    (get_cyber_scanner_data, "Cyber Scanner"),
                    (get_ransomware_data, "Ransomware"),
                    (get_vencert_data, "VenCERT"),
                    (get_network_resilience_data, "Resiliencia de Red"),
                    (get_sigint_alerts_data, "Anomalías SIGINT"),
                    (get_botnet_detector_data, "Detector de Botnets"),
                    (get_finint_data, "Radar FININT"),
                ]
            if social_active:
                social_tasks += [
                    (get_realtime_data, "Realtime"),
                    (get_tiktok_all, "TikTok"),
                    (get_instagram_all, "Instagram"),
                    (radar.scan_flash_events, "EVENT RADAR"),
                ]
        else:
            if social_active:
                social_tasks.append((radar.scan_flash_events, "EVENT RADAR"))

        loop = asyncio.get_running_loop()

        async def _fetch_social_async(fn, name):
            async with SOCIAL_SEMAPHORE:
                try:
                    if asyncio.iscoroutinefunction(fn):
                        return name, await asyncio.wait_for(fn(), timeout=120)
                    return name, await asyncio.wait_for(loop.run_in_executor(_DASHBOARD_EXECUTOR, fn), timeout=120)
                except asyncio.TimeoutError:
                    logger.warning(f"Sensor {name} excedió timeout de 120s")
                    return name, {}
                except Exception as e:
                    metrics.RATE_LIMIT_HITS.labels(module=f"sensor_{name}").inc()
                    logger.warning(f"Fallo en sensor {name}: {e}")
                    return name, {}

        pipeline_task = _build_pipeline_async(priority_only=priority_only)
        social_tasks_async = [_fetch_social_async(fn, nm) for fn, nm in social_tasks]
        results = await asyncio.gather(pipeline_task, *social_tasks_async, return_exceptions=True)

        pipeline = (
            results[0]
            if not isinstance(results[0], Exception)
            else {
                "all_entries": [],
                "own": [],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sorted_sources": [],
            }
        )
        if isinstance(results[0], Exception):
            logger.error(f"[PIPELINE] Error crítico en pipeline: {results[0]}")
        social_results = [r for r in results[1:] if not isinstance(r, Exception)]

        now_utc = datetime.now(timezone.utc)
        cutoff_time = now_utc - timedelta(hours=config_mod.ENTRY_MAX_AGE_HOURS)


        social_data = {"sources": {}, "count": 0, "timestamp": datetime.now().strftime("%H:%M:%S")}
        for name, res in social_results:
            if not res:
                continue
            sources_to_add = res.get("sources", {}) if isinstance(res, dict) else {name: res}
            for s, items in sources_to_add.items():
                if items:
                    key = f"{name}: {s}" if s and s != name else name
                    # Filter items by ENTRY_MAX_AGE_HOURS to keep OSINT data fresh and coherent
                    filtered_items = []
                    for item in items:
                        if not isinstance(item, dict):
                            filtered_items.append(item)
                            continue
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
                        social_data["sources"][key.strip(": ")] = filtered_items
                        social_data["count"] += len(filtered_items)

        heavy_data = state.heavy_track_cache["onion_and_dorks"]
        for s, items in heavy_data.get("sources", {}).items():
            if items:
                key = f"HEAVY: {s}"
                filtered_items = []
                for item in items:
                    if not isinstance(item, dict):
                        filtered_items.append(item)
                        continue
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
                    social_data["sources"][key] = filtered_items
                    social_data["count"] += len(filtered_items)

        category_groups = defaultdict(list)
        for source, items in social_data["sources"].items():
            category_groups[categorize_source(source)].append((source, items))

        state.progress_state.update({"step": "Análisis de Inteligencia", "percentage": 80})

        all_entries = pipeline["all_entries"]
        alert_candidates = list(all_entries)
        seen_alert_ids = set()
        for items in social_data["sources"].values():
            for item in items:
                if isinstance(item, dict):
                    item_key = (item.get("link", ""), item.get("title", ""))
                    if item_key not in seen_alert_ids:
                        seen_alert_ids.add(item_key)
                        alert_candidates.append(item)

        loop = asyncio.get_running_loop()
        alerts_res, narrative_res = await asyncio.gather(
            loop.run_in_executor(_DASHBOARD_EXECUTOR, generate_alerts, alert_candidates),
            loop.run_in_executor(_DASHBOARD_EXECUTOR, get_narrative_data, all_entries),
        )
        alerts, alert_counts = alerts_res

        social_graph = {}
        open_data, flight_data, vessel_data, events_data, user_search_data, seismic_data, gdacs_data, asn_data = {}, {}, {}, {}, {}, {}, {}, {}
        composite_events = []
        influential_result = {}

        if not priority_only:
            state.progress_state.update({"step": "Análisis de Redes", "percentage": 90})
            results_ext = await asyncio.gather(
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_social_graph, all_entries),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_all_open_data),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_all_flight_data),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_all_vessel_data),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_all_events_data),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, search_multiple_users_for_dashboard, config.TARGET_USERS),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_seismic_data),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_gdacs_data),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_network_outages),
                loop.run_in_executor(_DASHBOARD_EXECUTOR, get_influential_users),
                return_exceptions=True
            )
            social_graph = results_ext[0] if not isinstance(results_ext[0], Exception) else {}
            if isinstance(results_ext[0], Exception):
                logger.error(f"Error in social_graph task: {results_ext[0]}")
                social_graph = {}
            influential_result = results_ext[9] if not isinstance(results_ext[9], Exception) else {}

            # FASE 1.4: Entity linker — enriquecer nodos del grafo con entity_registry_id
            try:
                graph_data = social_graph.get("graph", {})
                if graph_data.get("nodes") and len(graph_data["nodes"]) > 1:
                    from entity_linker import run_full_link_cycle
                    from graph_database import save_graph_snapshot
                    from osiris_intel import ensure_sanctions_index
                    snapshot_id = save_graph_snapshot(graph_data, extraction_method="regex")
                    sanctions_index = await ensure_sanctions_index()
                    if sanctions_index:
                        await loop.run_in_executor(
                            _DASHBOARD_EXECUTOR,
                            run_full_link_cycle,
                            graph_data,
                            sanctions_index,
                            snapshot_id,
                        )
            except Exception as linker_err:
                logger.warning(f"[ENTITY LINKER] Error in cycle: {linker_err}")

            # SAFE MODE FALLBACK: If graph is empty or has 0/1 node, provide mock data
            nodes_count = len(social_graph.get("graph", {}).get("nodes", []))
            if nodes_count < 2:
                mock_graph = {
                    "nodes": [
                        {"id": "persons::Sujeto_Control", "label": "Sujeto de Control", "group": "persons", "sentiment": "neutral", "pagerank": 0.08, "community": 1, "is_botnet": False},
                        {"id": "organizations::Estructura_X", "label": "Estructura X", "group": "organizations", "sentiment": "negative", "pagerank": 0.06, "community": 1, "is_botnet": False},
                        {"id": "locations::Operaciones", "label": "Operaciones", "group": "locations", "sentiment": "neutral", "pagerank": 0.04, "community": 2, "is_botnet": False},
                        {"id": "persons::Agente_01", "label": "Agente 01", "group": "persons", "sentiment": "negative", "pagerank": 0.05, "community": 1, "is_botnet": True},
                        {"id": "persons::Agente_02", "label": "Agente 02", "group": "persons", "sentiment": "positive", "pagerank": 0.03, "community": 2, "is_botnet": False},
                    ],
                    "edges": [
                        {"from": "persons::Sujeto_Control", "to": "organizations::Estructura_X", "value": 5, "type": "co-occurrence"},
                        {"from": "persons::Sujeto_Control", "to": "persons::Agente_01", "value": 3, "type": "co-occurrence"},
                        {"from": "organizations::Estructura_X", "to": "locations::Operaciones", "value": 4, "type": "co-occurrence"},
                        {"from": "persons::Agente_02", "to": "locations::Operaciones", "value": 2, "type": "co-occurrence"},
                    ]
                }
                social_graph = {
                    "graph": mock_graph,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "count": 5,
                    "edges": 4,
                    "is_mock": True
                }

            open_data = results_ext[1] if not isinstance(results_ext[1], Exception) else {}
            flight_data = results_ext[2] if not isinstance(results_ext[2], Exception) else {}
            vessel_data = results_ext[3] if not isinstance(results_ext[3], Exception) else {}
            events_data = results_ext[4] if not isinstance(results_ext[4], Exception) else {}
            user_search_data = results_ext[5] if not isinstance(results_ext[5], Exception) else {}
            seismic_data = results_ext[6] if len(results_ext) > 6 and not isinstance(results_ext[6], Exception) else {}
            gdacs_data = results_ext[7] if len(results_ext) > 7 and not isinstance(results_ext[7], Exception) else {}
            asn_data = results_ext[8] if len(results_ext) > 8 and not isinstance(results_ext[8], Exception) else {}

            if seismic_data and seismic_data.get("earthquakes"):
                eqs = events_data.setdefault("earthquakes", [])
                seen_ids = {e.get("id") for e in eqs if e.get("id")}
                for eq in seismic_data["earthquakes"]:
                    if eq.get("id") not in seen_ids:
                        eqs.append(eq)

            if gdacs_data and gdacs_data.get("weather_alerts"):
                was = events_data.setdefault("weather_alerts", [])
                seen_ids = {a.get("id") for a in was if a.get("id")}
                for alert in gdacs_data["weather_alerts"]:
                    if alert.get("id") not in seen_ids:
                        was.append(alert)

            if asn_data and asn_data.get("network_outages"):
                no = events_data.setdefault("network_outages", [])
                seen_ids = {o.get("id") for o in no if o.get("id")}
                for outage in asn_data["network_outages"]:
                    if outage.get("id") not in seen_ids:
                        no.append(outage)

        # Merge profile change alerts from target monitor
        profile_changes = influential_result.get("profile_changes", []) if isinstance(influential_result, dict) else []
        if profile_changes:
            alerts.extend(profile_changes)
            alert_counts["total"] = alert_counts.get("total", 0) + len(profile_changes)

        # Correlacion geoespacial
        composite_events = correlate_events(seismic_data, gdacs_data, asn_data, events_data)
        if composite_events:
            alerts.extend(composite_events)
            alert_counts["total"] = alert_counts.get("total", 0) + len(composite_events)

        rt_items = _build_rt_items(flight_data, vessel_data, events_data, open_data)

        dashboard_result = {
            **get_empty_context(),
            "now": pipeline["timestamp"],
            "all_entries": sanitize_for_json(all_entries),
            "total_sources": social_data.get("count", 0),
            "tor_active": await is_tor_active(),
            "rt_items": rt_items,
            "ai_geopoints": state.heavy_track_cache.get("ai_geopoints", []),
            "social_data": sanitize_for_json(social_data),
            "category_groups": dict(category_groups),
            "own_posts": pipeline["own"],
            "global_briefing": sanitize_for_json(state.heavy_track_cache.get("global_briefing", {})),
            "reliability_score": state.heavy_track_cache.get("reliability_score", 100),
            "reliability_color": state.heavy_track_cache.get("reliability_color", "#00ffaa"),
            "briefing_history": sanitize_for_json(state.heavy_track_cache.get("briefing_history", [])),
            "alerts": sanitize_for_json(alerts),
            "alert_counts": alert_counts,
            "narrative_analysis": sanitize_for_json(narrative_res),
            "social_graph": sanitize_for_json(social_graph),
            "open_data": sanitize_for_json(open_data),
            "flight_data": sanitize_for_json(flight_data),
            "vessel_data": sanitize_for_json(vessel_data),
            "events_data": sanitize_for_json(events_data),
            "seismic_data": sanitize_for_json(seismic_data),
            "gdacs_data": sanitize_for_json(gdacs_data),
            "asn_data": sanitize_for_json(asn_data),
            "user_search_data": sanitize_for_json(user_search_data),
            "composite_events": sanitize_for_json(composite_events) if composite_events else [],
            "cb_count": get_circuit_breaker_count(),
            "entity_explorer_data": _get_entity_explorer_data(),
        }

        dashboard_result["geo_points"] = _build_geo_points(social_data, rt_items, state.heavy_track_cache)
        dashboard_result["cycle_id"] = state.cycle_id
        dashboard_result["cycle_start_ts"] = state.cycle_start_ts
        return dashboard_result

    except Exception as e:
        logger.critical(f"Dashboard error crítico: {e}", exc_info=True)
        return None
    finally:
        state.progress_state.update({"step": "Finalizado", "percentage": 100})


def _get_entity_explorer_data() -> dict:
    """Load entity registry data for the frontend explorer."""
    try:
        from entity_registry import get_stats, search
        stats = get_stats()
        # Load last 50 entities for initial render
        recent = search(query="", limit=50)
        return {"entities": sanitize_for_json(recent), "stats": stats}
    except Exception:
        return {"entities": [], "stats": {"total_entities": 0, "ofac_matches": 0, "wikidata_linked": 0}}
