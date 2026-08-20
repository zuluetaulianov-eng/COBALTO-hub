import asyncio
import concurrent.futures
import logging
from datetime import datetime

from ai_core import clear_briefing_step, generate_global_briefing, geolocate_text, set_briefing_step
from dashboard_state import state
from osint_registry import FALLBACKS, load_function, load_special_module

logger = logging.getLogger(__name__)

_HEAVY_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=8)

_heavy_track_lock = asyncio.Lock()

_osint_alerts = load_special_module("osint_alerts")
generate_alerts = _osint_alerts.get("generate_alerts", lambda x: ([], {}))
_osint_fakenews = load_special_module("osint_fakenews")
analyze_batch_news = _osint_fakenews.get("analyze_batch_news", lambda x: [])

get_onion_data = load_function("osint_onion", "get_onion_data") or FALLBACKS["sources_dict"]
get_social_dorks_sync = load_function("osint_social_dorks", "get_social_dorks_sync") or FALLBACKS["sources_dict"]


async def update_heavy_track(mode="full"):
    if _heavy_track_lock.locked():
        logger.info("[HEAVY TRACK] Análisis en curso. Saltando ciclo.")
        return
    async with _heavy_track_lock:
        logger.info("[HEAVY TRACK] Iniciando análisis profundo...")
        heavy_tasks = [(get_onion_data, "Onion"), (get_social_dorks_sync, "Dorks Social")]
        res_data = {"sources": {}, "count": 0, "timestamp": datetime.now().strftime("%H:%M:%S")}

        def _fetch_heavy(fn, name):
            try:
                return name, fn()
            except Exception as e:
                logger.warning(f"Fallo en Heavy Task {name}: {e}")
                return name, {}

        loop = asyncio.get_running_loop()
        futures = [loop.run_in_executor(_HEAVY_EXECUTOR, _fetch_heavy, fn, nm) for fn, nm in heavy_tasks]
        results = await asyncio.gather(*futures)

        for name, res in results:
            if res and "sources" in res:
                for s, items in res["sources"].items():
                    if items:
                        key = f"{name}: {s}"
                        res_data["sources"][key] = items
                        res_data["count"] += len(items)

        state.heavy_track_cache["onion_and_dorks"] = res_data

        if not state.last_entries_cache:
            logger.info("[HEAVY TRACK] Sin datos de noticias. Análisis IA diferido.")
            state.heavy_track_cache["global_briefing"] = {
                "agents": [],
                "consensus": "⏳ Cargando datos de inteligencia. Análisis en cola...",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            logger.info("[HEAVY TRACK] Análisis profundo completado (parcial).")
            return

        try:
            import config
            nlp_active = getattr(config, "MODULE_NLP_ACTIVE", True)

            alerts = []
            ai_points = []
            fakenews = []
            loop = asyncio.get_running_loop()

            if nlp_active:
                alerts_tuple, fakenews = await asyncio.gather(
                    loop.run_in_executor(_HEAVY_EXECUTOR, generate_alerts, state.last_entries_cache),
                    loop.run_in_executor(_HEAVY_EXECUTOR, analyze_batch_news, state.last_entries_cache[:30]),
                )
                alerts, _ = alerts_tuple
            else:
                logger.info("[HEAVY TRACK] Módulo NLP desactivado. Saltando análisis de fakenews y alertas IA.")

            avg_score = 100
            if fakenews:
                scores = [f.get("reliability_score", 0) for f in fakenews if isinstance(f, dict)]
                if scores:
                    raw_avg = sum(scores) / len(scores)
                    # Convert raw average penalty (0-10) to a reliability percentage (100%-0%)
                    avg_score = max(0, min(100, 100 - int(raw_avg * 10)))

            color_conf = "#ff4444" if avg_score < 50 else "#44aaee" if avg_score < 80 else "#00ffaa"

            if nlp_active:
                set_briefing_step("ARES", "procesando")
                briefing_data = await generate_global_briefing(state.last_entries_cache, alerts, fakenews, mode=mode)
                clear_briefing_step()
            else:
                briefing_data = {
                    "agents": [],
                    "consensus": "⚠️ Módulo NLP/IA desactivado por el administrador. Sistema en modo de bajo consumo.",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }

            state.heavy_track_cache["global_briefing"] = briefing_data
            state.heavy_track_cache["reliability_score"] = int(avg_score)
            state.heavy_track_cache["reliability_color"] = color_conf

            if isinstance(briefing_data, dict) and "consensus" in briefing_data:
                if "briefing_history" not in state.heavy_track_cache:
                    state.heavy_track_cache["briefing_history"] = []
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state.heavy_track_cache["briefing_history"].insert(0, {"time": now_str, "content": briefing_data})
                state.heavy_track_cache["briefing_history"] = state.heavy_track_cache["briefing_history"][:10]

            async def _geo_worker(alert):
                from dashboard_geocontext import GEO_SEMAPHORE

                async with GEO_SEMAPHORE:
                    try:
                        coords = await geolocate_text(f"{alert['title']} - {alert['summary']}")
                        if coords and coords.get("lat"):
                            return {
                                "lat": coords["lat"],
                                "lon": coords["lon"],
                                "title": alert["title"],
                                "source": "🤖 Geo-IA",
                                "type": "ai_geo",
                                "summary": alert["summary"],
                            }
                    except Exception:
                        pass
                    return None

            geo_tasks = [
                _geo_worker(alert)
                for alert in alerts[:5]
                if any(lvl in alert["level"] for lvl in ["CRÍTICO", "URGENTE"])
            ]
            if geo_tasks:
                geo_results = await asyncio.gather(*geo_tasks)
                ai_points = [r for r in geo_results if r]
            state.heavy_track_cache["ai_geopoints"] = ai_points

        except Exception as e:
            logger.error(f"IA/Alertas: {e}")

        # FASE 2: Run agent investigation cycle
        try:
            from agent_orchestrator import orchestrator
            agent_ctx = {
                "alerts": alerts or [],
                "composite_events": state.heavy_track_cache.get("composite_events", []),
                "all_entries": state.last_entries_cache or [],
                "asn_data": state.heavy_track_cache.get("asn_data", {}),
            }
            await orchestrator.run_investigation_cycle(agent_ctx)
        except Exception as agent_err:
            logger.warning(f"[AGENT] Investigation cycle error: {agent_err}")

        # FASE 3: Predictive scoring cycle
        try:
            from early_warning import early_warning
            from entity_registry import list_all as list_entities
            from event_bus import bus
            from predictive_scorer import compute_entity_threat

            all_entries = state.last_entries_cache or []
            composite_events = state.heavy_track_cache.get("composite_events", [])
            agent_tasks = []
            try:
                from agent_orchestrator import orchestrator as orch
                agent_tasks = orch.list_tasks(status="completed")
            except Exception:
                pass

            entities = await asyncio.to_thread(list_entities, limit=200)
            now = datetime.now()
            scores = []
            for ent in entities:
                try:
                    sc = compute_entity_threat(ent, agent_tasks, composite_events, all_entries, now)
                    scores.append(sc)
                except Exception:
                    continue

            scores.sort(key=lambda x: x["threat_score"], reverse=True)
            new_warnings = early_warning.evaluate(scores, context=state.heavy_track_cache)
            for w in new_warnings:
                bus.emit("predictive", source="predictive_scorer", data={
                    "warning": w,
                    "summary": f"{w['level']}: {w['entity_name']} (score={w['threat_score']})",
                })

            state.heavy_track_cache["predictive_scores"] = scores[:50]
            state.heavy_track_cache["predictive_active"] = len(early_warning.get_active())
        except Exception as pred_err:
            logger.warning(f"[PREDICTIVE] Cycle error: {pred_err}")

        logger.info("[HEAVY TRACK] Análisis profundo completado.")
