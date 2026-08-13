import asyncio
import json
import logging
import os
import threading
from typing import Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL")
_REDIS_CLIENT = None
if _REDIS_URL:
    try:
        import redis
        _REDIS_CLIENT = redis.from_url(_REDIS_URL, decode_responses=True)
    except Exception:
        pass


class AsyncTaskQueue:
    def __init__(self, queue_name: str, max_retries: int = 3, max_queue: int = 100):
        self.queue_name = queue_name
        self._local_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)
        self._worker_task: Optional[asyncio.Task] = None
        self._processed: int = 0
        self._failed: int = 0
        self._lock = threading.Lock()
        self._max_retries = max_retries
        self._registry: Dict[str, Callable] = {}

    def register_handler(self, name: str, func: Callable):
        """Registra una función o corutina para manejar tareas desde Redis."""
        self._registry[name] = func

    def start(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def enqueue(self, name: str, payload: dict = None, coro: Coroutine = None, priority: bool = False) -> bool:
        """
        Encola una tarea. Si Redis está activo, serializa el 'payload'.
        Para fallback local, soporta pasar una 'coro' directamente.
        """
        payload = payload or {}
        task_data = {"name": name, "payload": payload, "retries": 0, "max_retries": self._max_retries}

        if _REDIS_CLIENT:
            try:
                # Capa A: Redis Queue (Distribuida)
                redis_key = f"cobalto:queue:{self.queue_name}"
                if priority:
                    _REDIS_CLIENT.lpush(redis_key, json.dumps(task_data))
                else:
                    _REDIS_CLIENT.rpush(redis_key, json.dumps(task_data))
                return True
            except Exception as e:
                logger.warning(f"[TASK QUEUE] Error encolando en Redis, usando fallback local. Error: {e}")

        # Fallback: Memoria local
        if coro:
            task_data["coro"] = coro

        try:
            await self._local_queue.put(task_data)
            return True
        except asyncio.QueueFull:
            logger.warning(f"[TASK QUEUE] Cola llena. Tarea '{name}' rechazada.")
            return False

    async def _worker_loop(self):
        while True:
            try:
                task_data = None

                # Intentar leer de Redis primero (si está activo)
                if _REDIS_CLIENT:
                    try:
                        redis_key = f"cobalto:queue:{self.queue_name}"
                        # Non-blocking pop para poder atender local queue también
                        item = _REDIS_CLIENT.lpop(redis_key)
                        if item:
                            task_data = json.loads(item)
                    except Exception:
                        pass

                # Si no hay en Redis, leer local sin bloquear eternamente
                if not task_data:
                    try:
                        task_data = await asyncio.wait_for(self._local_queue.get(), timeout=1.0)
                        is_local = True
                    except asyncio.TimeoutError:
                        continue # Volver a revisar Redis y Local
                else:
                    is_local = False

                name = task_data.get("name")
                try:
                    # Ejecutar: si es fallback tiene "coro", si es redis usa el registry
                    if "coro" in task_data and task_data["coro"]:
                        await task_data["coro"]
                    elif name in self._registry:
                        func = self._registry[name]
                        if asyncio.iscoroutinefunction(func):
                            await func(task_data.get("payload", {}))
                        else:
                            await asyncio.to_thread(func, task_data.get("payload", {}))
                    else:
                        logger.warning(f"[TASK QUEUE] Tarea '{name}' no tiene handler registrado.")

                    with self._lock:
                        self._processed += 1

                except Exception as e:
                    task_data["retries"] = task_data.get("retries", 0) + 1
                    if task_data["retries"] <= task_data.get("max_retries", self._max_retries):
                        backoff = 2 ** task_data["retries"]
                        logger.warning(
                            f"[TASK QUEUE] '{name}' falló (intento {task_data['retries']}). Reintentando en {backoff}s. Error: {e}"
                        )
                        asyncio.create_task(self._delayed_retry(task_data, backoff, is_local))
                    else:
                        with self._lock:
                            self._failed += 1
                        logger.error(f"[TASK QUEUE] '{name}' agotó reintentos.")

                finally:
                    if is_local:
                        self._local_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TASK QUEUE] Worker error: {e}")
                await asyncio.sleep(5)

    async def _delayed_retry(self, task_data: dict, delay: float, is_local: bool):
        await asyncio.sleep(delay)
        if not is_local and _REDIS_CLIENT:
            try:
                redis_key = f"cobalto:queue:{self.queue_name}"
                _REDIS_CLIENT.rpush(redis_key, json.dumps(task_data))
                return
            except Exception:
                pass

        try:
            await self._local_queue.put(task_data)
        except asyncio.QueueFull:
            logger.error(f"[TASK QUEUE] Rechazado reintento de '{task_data.get('name')}' (cola local llena).")

    async def join(self):
        await self._local_queue.join()

    def get_stats(self) -> dict:
        with self._lock:
            qsize = self._local_queue.qsize()
            if _REDIS_CLIENT:
                try:
                    redis_key = f"cobalto:queue:{self.queue_name}"
                    qsize += _REDIS_CLIENT.llen(redis_key)
                except Exception:
                    pass

            return {
                "queue_size": qsize,
                "processed": self._processed,
                "failed": self._failed,
                "max_retries": self._max_retries,
            }

    def stop(self):
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()


TASK_QUEUE_AI = AsyncTaskQueue(queue_name="ai_tasks", max_retries=3, max_queue=50)
TASK_QUEUE_OSINT = AsyncTaskQueue(queue_name="osint_tasks", max_retries=2, max_queue=200)
