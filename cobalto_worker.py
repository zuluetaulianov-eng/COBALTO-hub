"""
cobalto_worker.py — Worker independiente de extracción OSINT
=============================================================
Proceso separado del servidor web. Extrae datos, construye el
contexto completo y lo persiste en dashboard_persistent_cache.json.

El servidor (app.py) solo lee ese archivo; ya no extrae por su cuenta.

Uso:
    python cobalto_worker.py               # Corre indefinidamente (producción)
    python cobalto_worker.py --once        # Ejecuta un ciclo y sale (debug)
    python cobalto_worker.py --fast-only   # Solo fast-track (prueba rápida)

Variables de entorno relevantes (heredadas de .env):
    CYCLE_INTERVAL_MINUTES   Intervalo entre ciclos completos (default 30)
    WORKER_CACHE_FILE        Ruta al JSON de caché (default auto-detectado)
"""

import asyncio
import gc
import json
import logging
import multiprocessing
import os
import sys
import time

if sys.platform == 'win32':
    multiprocessing.freeze_support()
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import osint_elasticsearch

load_dotenv()

# -- Evitar UnicodeEncodeError en consola Windows --
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── Logging con rotación automática ──
import logging.handlers as _log_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        _log_handlers.RotatingFileHandler(
            "worker.log",
            maxBytes=5 * 1024 * 1024,  # 5 MB por archivo
            backupCount=3,             # Máximo 3 rotaciones (15 MB total)
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("cobalto.worker")

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
else:
    BASE_DIR = Path(__file__).parent

CACHE_FILE = Path(os.getenv("WORKER_CACHE_FILE", str(BASE_DIR / "dashboard_persistent_cache.json")))

# ── Redis connection pool ──
_redis_pool = None

def _get_redis_conn():
    global _redis_pool
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    import redis as _redis_mod
    if _redis_pool is None:
        _redis_pool = _redis_mod.ConnectionPool.from_url(redis_url, decode_responses=True)
    try:
        return _redis_mod.Redis(connection_pool=_redis_pool)
    except Exception as e:
        logger.warning(f"[REDIS] Error obteniendo conexión del pool: {e}")
        return None

# Activar escudo DoH anti-censura
try:
    import doh_patch
    doh_patch.enable_doh()
    logger.info("[DOH] Escudo DoH activo")
except Exception as e:
    logger.warning(f"[DOH] No se pudo activar: {e}")


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        try:
            import time
            if isinstance(obj, time.struct_time):
                return list(obj)
        except Exception:
            pass
        try:
            return str(obj)
        except Exception:
            return None


def _deep_sanitize(obj, depth: int = 0):
    """Elimina objetos no-JSON-serializables (Future, Lock, Task, etc.) recursivamente."""
    if depth > 12:
        return None
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if not isinstance(k, (str, int, float, bool, type(None))):
                k = str(k)
            clean[k] = _deep_sanitize(v, depth + 1)
        return clean
    if isinstance(obj, (list, tuple)):
        return [_deep_sanitize(i, depth + 1) for i in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Para cualquier otro tipo: intentar JSON primero, sino convertir a str
    try:
        import json as _json
        _json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        try:
            return str(obj)
        except Exception:
            return None


async def _save_cache(context: dict) -> bool:
    """Persiste el contexto en el archivo de caché compartido con el servidor."""
    try:
        # Reemplazar deepcopy que falla con locks (_thread.RLock)
        safe = {k: v for k, v in context.items() if k != "request"}

        # Limpiar objetos no serializables en all_entries
        if "all_entries" in safe:
            clean_entries = []
            for entry in safe["all_entries"]:
                if isinstance(entry, dict):
                    clean_entry = {k: v for k, v in entry.items() if k not in ["published_parsed", "published_dt", "request"]}
                    clean_entries.append(clean_entry)
                else:
                    clean_entries.append(entry)
            safe["all_entries"] = clean_entries

            # Fase 3 Políglota: Sincronizar en segundo plano con Elasticsearch
            # (El módulo ya tiene su propio try/except y fallback silencioso si ES no está activo)
            await asyncio.to_thread(osint_elasticsearch.index_entries, clean_entries)

        safe["_cached_at"] = datetime.now().isoformat()
        safe["_cache_source"] = "cobalto_worker"

        # Fase 0.2: Persistencia histórica en SQLite particionado
        try:
            import historical_store
            clean_for_storage = []
            for entry in safe.get("all_entries", []):
                if isinstance(entry, dict):
                    clean_for_storage.append(entry)
            if clean_for_storage:
                historical_store.store_entries(
                    clean_for_storage,
                    cycle_id=safe.get("cycle_id", 0),
                    cycle_type="full",
                )
        except Exception as hist_err:
            logger.debug(f"[HISTORICAL] Store error: {hist_err}")

        # Sanitización profunda para eliminar Future/Task/Lock antes de serializar
        safe = _deep_sanitize(safe)

        payload = json.dumps(safe, cls=SafeEncoder, ensure_ascii=False)

        r = _get_redis_conn()
        if r:
            try:
                r.set("dashboard_persistent_cache", payload)
                r.publish("cobalto_updates", "updated")
                logger.info("[CACHE] Guardado en Redis exitoso")
            except Exception as e:
                logger.warning(f"[CACHE] Falló guardado en Redis: {e}")

        # Escritura atómica: escribir en tmp y luego renombrar con reintentos para Windows
        tmp_file = CACHE_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(payload)

        for _attempt in range(5):
            try:
                tmp_file.replace(CACHE_FILE)
                break
            except PermissionError:
                time.sleep(0.05)
            except Exception as repl_err:
                logger.warning(f"[CACHE] Intento {_attempt+1} de reemplazo de caché falló: {repl_err}")
                time.sleep(0.05)

        entry_count = len(safe.get("all_entries", []))
        logger.info(f"[CACHE] Guardado: {entry_count} entradas -> {CACHE_FILE.name}")
        return True
    except Exception as e:
        logger.error(f"[CACHE] Error guardando: {e}")
        return False



async def _run_fast_cycle() -> bool:
    """Ciclo rápido: RSS prioritarios + sensores principales."""
    logger.info("[FAST] Iniciando ciclo rápido (RSS prioritario)...")
    try:
        from dashboard import get_dashboard_data, state
        from event_bus import bus

        bus.emit("cycle_start", "worker", {"type": "fast"})
        state.clear_cycle()
        ctx = await asyncio.wait_for(
            get_dashboard_data(priority_only=True), timeout=180
        )
        if ctx:
            await _save_cache(ctx)
            count = len(ctx.get('all_entries', []))
            logger.info(f"[FAST] Completado: {count} noticias")
            bus.emit("cycle_complete", "worker", {"type": "fast", "entry_count": count})
            return True
        logger.warning("[FAST] get_dashboard_data devolvió None")
        bus.emit("sensor_failure", "worker", {"type": "fast", "error": "get_dashboard_data returned None"})
        return False
    except asyncio.TimeoutError:
        logger.error("[FAST] Timeout (180s) en ciclo rápido")
        bus.emit("sensor_failure", "worker", {"type": "fast", "error": "timeout"})
        return False
    except Exception as e:
        logger.exception(f"[FAST] Error inesperado: {e}")
        bus.emit("sensor_failure", "worker", {"type": "fast", "error": str(e)})
        return False


async def _run_full_cycle() -> bool:
    """Ciclo completo: todos los extractores + heavy track."""
    logger.info("[FULL] Iniciando ciclo completo (todos los extractores)...")
    try:
        from dashboard import get_dashboard_data
        from event_bus import bus

        bus.emit("cycle_start", "worker", {"type": "full"})
        ctx = await asyncio.wait_for(
            get_dashboard_data(priority_only=False), timeout=1200
        )
        if ctx:
            await _save_cache(ctx)
            count = len(ctx.get('all_entries', []))
            sources = ctx.get('total_sources', 0)
            logger.info(f"[FULL] Completado: {count} noticias, {sources} fuentes")
            bus.emit("cycle_complete", "worker", {"type": "full", "entry_count": count, "sources": sources})
            return True
        logger.warning("[FULL] get_dashboard_data devolvió None")
        bus.emit("sensor_failure", "worker", {"type": "full", "error": "get_dashboard_data returned None"})
        return False
    except asyncio.TimeoutError:
        logger.error("[FULL] Timeout (1200s) en ciclo completo")
        bus.emit("sensor_failure", "worker", {"type": "full", "error": "timeout"})
        return False
    except Exception as e:
        logger.exception(f"[FULL] Error inesperado: {e}")
        bus.emit("sensor_failure", "worker", {"type": "full", "error": str(e)})
        return False


async def _run_heavy_cycle():
    """Heavy track: análisis IA profundo, onion, dorks, briefing táctico."""
    logger.info("[HEAVY] Iniciando análisis profundo (IA/Onion/Dorks)...")
    try:
        from dashboard import state
        from dashboard_heavy import update_heavy_track

        # Esperar a que haya entradas disponibles desde el ciclo anterior
        for _ in range(20):
            if state.last_entries_cache:
                break
            await asyncio.sleep(3)

        if not state.last_entries_cache:
            logger.warning("[HEAVY] Sin entradas en caché. Diferiendo análisis IA.")
            return

        await update_heavy_track()

        # ── Snapshot Collector: capturar frames de cámaras CCTV ──
        try:
            from cctv_snapshot_collector import snapshot_collector
            snapshots = await snapshot_collector.collect_known_sources()
            if snapshots:
                logger.info("[HEAVY] Captured %d CCTV snapshots", len(snapshots))
                # Emit event for dashboard
                try:
                    from event_bus import bus
                    bus.emit("cctv_snapshots", source="worker", data={"count": len(snapshots)})
                except Exception:
                    pass
                # Store in historical_store
                try:
                    from historical_store import store_entries
                    entries = []
                    for s in snapshots:
                        entries.append({
                            "title": f"Snapshot {s['camera_id']}",
                            "description": f"{s['source']} | {s['size_bytes']}B",
                            "category": "cctv_snapshot",
                            "source": s["source"],
                            "severity": "info",
                            "latitude": None,
                            "longitude": None,
                            "url": s.get("filepath", ""),
                            "timestamp": s["timestamp"],
                        })
                    await asyncio.to_thread(store_entries, entries)
                except Exception as e:
                    logger.debug("[HEAVY] historical_store error: %s", e)
        except Exception as e:
            logger.warning("[HEAVY] Snapshot collector error: %s", e)

        # Persistir heavy_track_cache junto con el contexto actual
        # Leemos el cache guardado y le añadimos los campos heavy
        try:
            existing = None
            r = _get_redis_conn()
            if r:
                try:
                    payload = r.get("dashboard_persistent_cache")
                    if payload:
                        existing = json.loads(payload)
                except Exception as e:
                    logger.warning(f"[HEAVY] No se pudo leer de Redis: {e}")

            if not existing and CACHE_FILE.exists():
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            if existing:
                existing["global_briefing"] = state.heavy_track_cache.get("global_briefing", {})
                existing["reliability_score"] = state.heavy_track_cache.get("reliability_score", 100)
                existing["reliability_color"] = state.heavy_track_cache.get("reliability_color", "#00ffaa")
                existing["briefing_history"] = state.heavy_track_cache.get("briefing_history", [])
                existing["ai_geopoints"] = state.heavy_track_cache.get("ai_geopoints", [])
                existing["_cached_at"] = datetime.now().isoformat()

                payload_new = json.dumps(existing, cls=SafeEncoder, ensure_ascii=False)

                if r:
                    try:
                        r.set("dashboard_persistent_cache", payload_new)
                        r.publish("cobalto_updates", "updated")
                    except Exception as e:
                        logger.warning(f"[HEAVY] No se pudo escribir en Redis: {e}")

                tmp_file = CACHE_FILE.with_suffix(".tmp")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    f.write(payload_new)
                tmp_file.replace(CACHE_FILE)
                logger.info("[HEAVY] Analisis profundo persistido en cache")
        except Exception as e:
            logger.error(f"[HEAVY] Error actualizando caché con heavy data: {e}")
    except Exception as e:
        logger.exception(f"[HEAVY] Error: {e}")

async def _heavy_cycle_handler(payload):
    await _run_heavy_cycle()
async def _run_full_extraction_cycle():
    """Ejecuta el ciclo de extracción completo: fast → full → despacha heavy."""
    # Recargar configuración dinámica para reflejar cambios del panel
    try:
        import config as _cfg
        _cfg.load_dynamic_config()
        logger.info("[CICLO] Configuración dinámica recargada")
    except Exception as e:
        logger.warning(f"[CICLO] No se pudo recargar config: {e}")

    cycle_start = time.time()
    logger.info("=" * 60)
    logger.info(f"[CICLO] Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Fase 1: Carga rápida
        await _run_fast_cycle()

        # Fase 2: Enriquecimiento completo
        await _run_full_cycle()

        # Fase 3: Heavy (IA, onion, briefing) — despachado a la cola distribuida
        try:
            from humanization import TASK_QUEUE_AI
            await TASK_QUEUE_AI.enqueue("heavy_cycle", priority=True)
            logger.info("[CICLO] Heavy track despachado a TASK_QUEUE_AI (Redis/Local)")
        except Exception as e:
            logger.error(f"[CICLO] Fallo al despachar Heavy track: {e}")

    finally:
        gc.collect()
        logger.debug("[WORKER-GC] Recolección de basura del Heap ejecutada")

    elapsed = time.time() - cycle_start
    logger.info(f"[CICLO] Completado en {elapsed:.1f}s")
    logger.info("=" * 60)


def _redis_config_listener():
    """Hilo daemon que escucha notificaciones de recarga de config por Redis."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return
    try:
        import redis as _r_mod
        _r = _r_mod.from_url(redis_url, decode_responses=True)
        _ps = _r.pubsub()
        _ps.subscribe("cobalto_config")
        logger.info("[WORKER] Listener Redis de configuración activo")
        for msg in _ps.listen():
            if msg["type"] == "message" and msg["data"] == "reloaded":
                import config as _cfg
                _cfg.load_dynamic_config()
                logger.info("[WORKER] Config recargada por señal Redis")
    except Exception:
        pass


async def worker_loop(interval_minutes: int = None, once: bool = False, fast_only: bool = False):
    """Loop principal del worker."""
    from config import CYCLE_INTERVAL_MINUTES

    if interval_minutes is None:
        interval_minutes = CYCLE_INTERVAL_MINUTES

    logger.info("[WORKER] COBALTO Worker iniciado")
    logger.info(f"[WORKER] Cache -> {CACHE_FILE}")
    logger.info(f"[WORKER] Intervalo de ciclo: {interval_minutes} minutos")

    # Iniciar listener Redis para recarga de config en tiempo real
    import threading as _threading
    _t = _threading.Thread(target=_redis_config_listener, daemon=True)
    _t.start()

    # Mantenimiento SQLite inicial
    try:
        from database import clean_old_sent_news
        await asyncio.to_thread(clean_old_sent_news, max_days=3)
        logger.info("[WORKER] Limpieza SQLite completada")
    except Exception as e:
        logger.warning(f"[WORKER] Limpieza SQLite falló (no crítico): {e}")

    # Arrancar colas globales de tareas distribuidas
    from humanization import TASK_QUEUE_AI, TASK_QUEUE_OSINT
    TASK_QUEUE_AI.register_handler("heavy_cycle", _heavy_cycle_handler)
    TASK_QUEUE_AI.start()
    TASK_QUEUE_OSINT.start()

    try:
        if fast_only:
            logger.info("[WORKER] Modo --fast-only: ejecutando solo ciclo rápido")
            await _run_fast_cycle()
            return

        if once:
            logger.info("[WORKER] Modo --once: ejecutando un ciclo completo y saliendo")
            await _run_full_extraction_cycle()
            # Esperar a que las colas terminen antes de salir
            await TASK_QUEUE_AI.join()
            await TASK_QUEUE_OSINT.join()
            return

        # Loop continuo
        while True:
            try:
                await _run_full_extraction_cycle()
            except Exception as e:
                logger.exception(f"[WORKER] Error inesperado en ciclo: {e}")

            logger.info(f"[WORKER] Próximo ciclo en {interval_minutes} minutos...")
            await asyncio.sleep(interval_minutes * 60)

    finally:
        logger.info("[WORKER] Deteniendo colas distribuidas...")
        TASK_QUEUE_AI.stop()
        TASK_QUEUE_OSINT.stop()


def main():
    once = "--once" in sys.argv
    fast_only = "--fast-only" in sys.argv

    interval = None
    for arg in sys.argv:
        if arg.startswith("--interval="):
            try:
                interval = int(arg.split("=")[1])
            except ValueError:
                pass

    try:
        asyncio.run(worker_loop(interval_minutes=interval, once=once, fast_only=fast_only))
    except KeyboardInterrupt:
        logger.info("[WORKER] Detenido por usuario (Ctrl+C)")
    except Exception as e:
        logger.exception(f"[WORKER] Error fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
