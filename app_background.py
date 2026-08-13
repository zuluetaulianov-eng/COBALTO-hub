import asyncio
import logging
from pathlib import Path
from typing import Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    def __init__(self):
        self._tasks = []

    def start(self, coro: Callable[[], Coroutine], name: str, loop: bool = True):
        task = asyncio.create_task(self._wrapped(coro, name, loop))
        self._tasks.append(task)
        return task

    async def _wrapped(self, coro: Callable[[], Coroutine], name: str, loop: bool):
        if not loop:
            try:
                await coro()
            except asyncio.CancelledError:
                logger.info(f"[BG TASK CANCELLED] {name}")
            except Exception as e:
                logger.error(f"[BG TASK ERROR] {name}: {e}")
            return

        while True:
            try:
                await coro()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[BG TASK ERROR] {name}: {e}")
                await asyncio.sleep(60)

    def cleanup(self):
        for task in self._tasks:
            task.cancel()


class CacheFileWatcher:
    """
    Observa dashboard_persistent_cache.json en busca de cambios.
    Cuando el worker escribe datos nuevos, dispara on_change_callback
    para que el servidor actualice app_state y haga broadcast por WebSocket.
    """

    def __init__(
        self,
        cache_file: Path,
        on_change_callback: Callable,
        poll_interval: float = 15.0,
    ):
        self._cache_file = cache_file
        self._on_change = on_change_callback
        self._poll_interval = poll_interval
        self._last_mtime: float = 0.0
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Inicia el watcher como tarea asyncio."""
        self._task = asyncio.create_task(self._watch_loop(), name="cache_file_watcher")
        logger.info(f"[WATCHER] Observando {self._cache_file.name} cada {self._poll_interval}s")
        return self._task

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _watch_loop(self):
        while True:
            try:
                if self._cache_file.exists():
                    mtime = self._cache_file.stat().st_mtime
                    if mtime != self._last_mtime and self._last_mtime != 0:
                        logger.info(
                            f"[WATCHER] Cambio detectado en {self._cache_file.name} "
                            f"(mtime: {mtime:.0f})"
                        )
                        try:
                            await self._on_change()
                        except Exception as cb_err:
                            logger.error(f"[WATCHER] Error en callback: {cb_err}")
                    self._last_mtime = mtime
            except Exception as e:
                logger.warning(f"[WATCHER] Error monitoreando archivo: {e}")

            await asyncio.sleep(self._poll_interval)


class RedisCacheWatcher:
    """
    Observa el canal de PubSub en Redis en busca de actualizaciones.
    Cuando el worker escribe datos nuevos, dispara on_change_callback
    para que el servidor actualice app_state y haga broadcast por WebSocket.
    """

    def __init__(
        self,
        redis_url: str,
        on_change_callback: Callable,
    ):
        self._redis_url = redis_url
        self._on_change = on_change_callback
        self._task: Optional[asyncio.Task] = None
        self._pubsub = None
        self._client = None

    def start(self):
        """Inicia el watcher como tarea asyncio."""
        self._task = asyncio.create_task(self._watch_loop(), name="redis_pubsub_watcher")
        logger.info(f"[WATCHER] Conectado a Redis PubSub en {self._redis_url}")
        return self._task

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _watch_loop(self):
        import redis.asyncio as redis
        while True:
            try:
                self._client = redis.from_url(self._redis_url)
                self._pubsub = self._client.pubsub()
                await self._pubsub.subscribe("cobalto_updates")

                async for message in self._pubsub.listen():
                    if message["type"] == "message":
                        logger.info("[WATCHER] Notificación recibida desde Redis PubSub")
                        try:
                            await self._on_change()
                        except Exception as cb_err:
                            logger.error(f"[WATCHER] Error en callback: {cb_err}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WATCHER] Error conectando a Redis PubSub: {e}")
                await asyncio.sleep(5)
            finally:
                if self._pubsub:
                    try:
                        await self._pubsub.unsubscribe("cobalto_updates")
                    except Exception:
                        pass
                if self._client:
                    await self._client.aclose()

bg_manager = BackgroundTaskManager()
