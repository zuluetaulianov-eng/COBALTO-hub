import asyncio
import os
import random
import threading
import time
from typing import Dict

_REDIS_URL = os.getenv("REDIS_URL")
_REDIS_CLIENT = None
if _REDIS_URL:
    try:
        import redis
        _REDIS_CLIENT = redis.from_url(_REDIS_URL, decode_responses=True)
    except Exception:
        pass


class RateLimiter:
    def __init__(self, platform: str, max_requests: int = 10, time_window: int = 60):
        self.platform = platform
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
        self.base_delay = 1.0
        self.current_delay = 0.0
        self.max_delay = 120.0
        self.consecutive_errors = 0

    def wait_if_needed(self) -> float:
        now = time.time()

        # --- Capa A: Redis (Distribuido) ---
        if _REDIS_CLIENT:
            try:
                key = f"ratelimit:{self.platform}:requests"
                delay_key = f"ratelimit:{self.platform}:delay"

                # Obtener penalizaciones dinámicas de red
                current_delay_str = _REDIS_CLIENT.get(delay_key)
                if current_delay_str:
                    self.current_delay = float(current_delay_str)

                if self.current_delay > 0:
                    jitter = random.uniform(0.8, 1.2)
                    wait_time = self.current_delay * jitter
                    time.sleep(wait_time)
                    now = time.time()

                # Limpiar viejos (Sliding Window Log en Redis)
                _REDIS_CLIENT.zremrangebyscore(key, 0, now - self.time_window)
                count = _REDIS_CLIENT.zcard(key)

                if count >= self.max_requests:
                    oldest_items = _REDIS_CLIENT.zrange(key, 0, 0, withscores=True)
                    if oldest_items:
                        oldest_request = oldest_items[0][1]
                        hard_wait = self.time_window - (now - oldest_request) + 0.5
                        if hard_wait > 0:
                            time.sleep(hard_wait)
                            return hard_wait

                # Registrar nueva petición
                _REDIS_CLIENT.zadd(key, {str(now): now})
                _REDIS_CLIENT.expire(key, self.time_window * 2)
                return self.current_delay
            except Exception:
                pass # Fallback local

        # --- Fallback Local (Memoria) ---
        with self.lock:
            now = time.time()
            if self.current_delay > 0:
                jitter = random.uniform(0.8, 1.2)
                wait_time = self.current_delay * jitter
                time.sleep(wait_time)
            self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
            if len(self.requests) >= self.max_requests:
                oldest_request = min(self.requests)
                hard_wait = self.time_window - (now - oldest_request) + 0.5
                if hard_wait > 0:
                    time.sleep(hard_wait)
                    return hard_wait
            self.requests.append(time.time())
            return self.current_delay

    def report_status(self, status_code: int):
        with self.lock:
            if status_code == 429 or status_code >= 500:
                self.consecutive_errors += 1
                if self.current_delay == 0:
                    self.current_delay = self.base_delay
                else:
                    self.current_delay = min(self.max_delay, self.current_delay * 2)
            elif status_code < 400:
                self.consecutive_errors = 0
                if self.current_delay > 0:
                    self.current_delay = max(0, self.current_delay * 0.8)
                    if self.current_delay < 0.2:
                        self.current_delay = 0

            if _REDIS_CLIENT:
                try:
                    delay_key = f"ratelimit:{self.platform}:delay"
                    _REDIS_CLIENT.set(delay_key, str(self.current_delay), ex=600)
                except Exception:
                    pass


RATE_LIMITERS: Dict[str, RateLimiter] = {
    "twitter": RateLimiter("twitter", max_requests=5, time_window=60),
    "instagram": RateLimiter("instagram", max_requests=3, time_window=60),
    "telegram": RateLimiter("telegram", max_requests=10, time_window=60),
    "tiktok": RateLimiter("tiktok", max_requests=3, time_window=60),
    "youtube": RateLimiter("youtube", max_requests=5, time_window=60),
    "facebook": RateLimiter("facebook", max_requests=3, time_window=60),
    "linkedin": RateLimiter("linkedin", max_requests=3, time_window=60),
    "reddit": RateLimiter("reddit", max_requests=10, time_window=60),
    "ai_groq": RateLimiter("ai_groq", max_requests=30, time_window=60),
    "default": RateLimiter("default", max_requests=10, time_window=60),
}


def get_dynamic_max_requests(platform: str) -> int:
    from humanization_stress import STRESS_MONITOR

    base = RATE_LIMITERS.get(platform, RATE_LIMITERS["default"]).max_requests
    return STRESS_MONITOR.scale_max_requests(base)


async def wait_for_rate_limit_async(platform: str = "default") -> float:
    limiter = RATE_LIMITERS.get(platform, RATE_LIMITERS["default"])
    wait_time = await asyncio.to_thread(limiter.wait_if_needed)
    return wait_time


def wait_for_rate_limit(platform: str = "default") -> float:
    limiter = RATE_LIMITERS.get(platform, RATE_LIMITERS["default"])
    return limiter.wait_if_needed()
