import logging
import threading
import time
from typing import List

logger = logging.getLogger(__name__)


class SystemStressMonitor:
    def __init__(self, cooldown: float = 120.0):
        self.cooldown = cooldown
        self._ai_failures: List[float] = []
        self._lock = threading.Lock()
        self._factor: float = 1.0
        self._last_scale_down: float = 0.0
        self._active = True

    @property
    def scaling_factor(self) -> float:
        now = time.time()
        with self._lock:
            self._ai_failures = [t for t in self._ai_failures if now - t < 300]
            if not self._ai_failures and self._factor > 1.0:
                self._factor = max(1.0, self._factor - 0.05)
            return self._factor

    def record_ai_failure(self):
        now = time.time()
        with self._lock:
            self._ai_failures.append(now)
            self._ai_failures = [t for t in self._ai_failures if now - t < 300]
            failure_rate = len(self._ai_failures) / 5.0
            if failure_rate > 3 and now - self._last_scale_down > 30:
                self._factor = min(4.0, self._factor * 1.5)
                self._last_scale_down = now
                logger.warning(f"[STRESS] Factor={self._factor:.1f} (AI fail rate={failure_rate:.1f}/min)")
            elif failure_rate < 0.5 and self._factor > 1.0:
                self._factor = max(1.0, self._factor * 0.9)

    def record_ai_success(self):
        with self._lock:
            if self._factor > 1.0 and self._ai_failures:
                self._factor = max(1.0, self._factor * 0.95)
            now = time.time()
            self._ai_failures = [t for t in self._ai_failures if now - t < 300]

    def scale_max_requests(self, base: int) -> int:
        scaled = int(base / self._factor)
        return max(1, scaled)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "factor": round(self._factor, 2),
                "ai_failures_5min": len(self._ai_failures),
                "active": self._active,
            }


STRESS_MONITOR = SystemStressMonitor()
