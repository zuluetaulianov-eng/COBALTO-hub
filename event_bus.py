"""
event_bus.py — In-process pub/sub event bus for internal system events.
Optional Redis PubSub bridge for multi-process deployments.
Thread-safe for both sync and async handlers.
"""
import asyncio
import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_REDIS_ENABLED = False
_redis_client = None
_redis_pubsub = None
_redis_listener_task = None


def _init_redis():
    """Attempt to connect to Redis if URL is configured."""
    global _REDIS_ENABLED, _redis_client, _redis_pubsub
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        return
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        _redis_pubsub = _redis_client.pubsub()
        _REDIS_ENABLED = True
        logger.info("[EVENT BUS] Redis PubSub bridge enabled: %s", redis_url)
    except ImportError:
        logger.debug("[EVENT BUS] redis-py not installed. Skipping Redis bridge.")
    except Exception as e:
        logger.warning("[EVENT BUS] Redis connection failed: %s", e)


async def _redis_listener(bus: "EventBus"):
    """Continuously listen for Redis messages and re-emit them locally."""
    global _redis_pubsub, _REDIS_ENABLED
    if not _REDIS_ENABLED or _redis_pubsub is None:
        return
    try:
        await _redis_pubsub.subscribe("cobalto:events")
        logger.info("[EVENT BUS] Redis listener subscribed to cobalto:events")
        async for msg in _redis_pubsub.listen():
            if msg["type"] != "message":
                continue
            try:
                data = json.loads(msg["data"])
                bus.emit(
                    event_type=data.get("type", "external"),
                    source=data.get("source", "redis"),
                    data=data.get("data", {}),
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning("[EVENT BUS] Redis listener error: %s", e)
    finally:
        _REDIS_ENABLED = False


async def redis_publish(event_type: str, source: str, data: Optional[Dict] = None):
    """Publish an event to Redis channel (non-blocking)."""
    global _redis_client, _REDIS_ENABLED
    if not _REDIS_ENABLED or _redis_client is None:
        return
    try:
        payload = json.dumps({"type": event_type, "source": source, "data": data or {}, "timestamp": datetime.now().isoformat()})
        await _redis_client.publish("cobalto:events", payload)
    except Exception as e:
        logger.debug("[EVENT BUS] Redis publish error: %s", e)


class EventBus:
    """Lightweight in-process event bus.

    Events are simple dicts with at minimum:
      { "type": str, "source": str, "timestamp": str, "data": dict }

    Supports both sync and async handlers.
    Optionally bridges to Redis PubSub if REDIS_URL is configured.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._handlers: Dict[str, List[Dict]] = defaultdict(list)
        self._history: List[Dict] = []
        self._history_max = 500
        self._redis_enabled = False
        self._redis_client = None

    def enable_redis(self):
        """Activate Redis bridge using environment config."""
        global _REDIS_ENABLED, _redis_client, _redis_pubsub, _redis_listener_task
        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            return
        try:
            import redis.asyncio as aioredis
            self._redis_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            self._redis_enabled = True
            _REDIS_ENABLED = True
            _redis_client = self._redis_client
            _redis_pubsub = self._redis_client.pubsub()
            # Start listener in background
            _redis_listener_task = asyncio.ensure_future(_redis_listener(self))
            logger.info("[EVENT BUS] Redis PubSub bridge enabled: %s", redis_url)
        except ImportError:
            logger.debug("[EVENT BUS] redis-py not installed.")
        except Exception as e:
            logger.warning("[EVENT BUS] Redis init failed: %s", e)

    def on(self, event_type: str, handler: Callable, name: str = ""):
        """Register a handler for an event type. Handler can be sync or async."""
        with self._lock:
            self._handlers[event_type].append({
                "handler": handler,
                "name": name or getattr(handler, "__name__", str(id(handler))),
            })
        logger.debug(f"[EVENT BUS] Registered handler '{name}' for '{event_type}'")

    def off(self, event_type: str, handler: Optional[Callable] = None, name: str = ""):
        """Remove handler(s) for an event type."""
        with self._lock:
            if handler:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h["handler"] != handler
                ]
            elif name:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h["name"] != name
                ]
            else:
                self._handlers[event_type] = []

    def emit(self, event_type: str, source: str = "system", data: Optional[Dict] = None):
        """Emit an event synchronously. Handlers run in calling thread."""
        event = {
            "type": event_type,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }
        self._record(event)
        self._dispatch(event)
        # Fire-and-forget Redis publish
        if self._redis_enabled:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(redis_publish(event_type, source, data))
            except Exception:
                pass

    async def emit_async(self, event_type: str, source: str = "system", data: Optional[Dict] = None):
        """Emit an event asynchronously. Async handlers are awaited."""
        event = {
            "type": event_type,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }
        self._record(event)
        await self._dispatch_async(event)
        if self._redis_enabled:
            await redis_publish(event_type, source, data)

    def _record(self, event: Dict):
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_max:
                self._history = self._history[-self._history_max // 2:]

    def _dispatch(self, event: Dict):
        handlers = list(self._handlers.get(event["type"], []))
        global_handlers = list(self._handlers.get("*", []))
        for h in handlers + global_handlers:
            try:
                result = h["handler"](event)
                if result is not None and asyncio.iscoroutine(result):
                    logger.warning(
                        f"[EVENT BUS] Sync dispatch received coroutine from '{h['name']}'"
                    )
            except Exception as e:
                logger.error(f"[EVENT BUS] Handler '{h['name']}' error: {e}")

    async def _dispatch_async(self, event: Dict):
        handlers = list(self._handlers.get(event["type"], []))
        global_handlers = list(self._handlers.get("*", []))
        for h in handlers + global_handlers:
            try:
                result = h["handler"](event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[EVENT BUS] Async handler '{h['name']}' error: {e}")

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Return recent event history, optionally filtered by type."""
        with self._lock:
            if event_type:
                filtered = [e for e in self._history if e["type"] == event_type]
            else:
                filtered = list(self._history)
            return filtered[-limit:]

    def clear_history(self):
        with self._lock:
            self._history.clear()

    def handler_count(self) -> int:
        with self._lock:
            return sum(len(h) for h in self._handlers.values())


# Global singleton
bus = EventBus()


# ── Standard Event Types ──────────────────────────────────────────
# cycle_start    – A new OSINT cycle is starting
# cycle_complete – A cycle finished successfully
# sensor_failure – A sensor/module raised an error
# agent_finding  – An autonomous agent produced a finding
# anomaly        – System anomaly detected (e.g. rate limit spike)
# config_change  – Configuration was updated
# humint_report  – A HUMINT report was received
# predictive     – A predictive alert was generated
