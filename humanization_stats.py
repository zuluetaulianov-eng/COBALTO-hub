import threading
from datetime import datetime
from typing import Any, Dict


class HumanizationStats:
    def __init__(self):
        self.total_requests = 0
        self.total_delay_time = 0.0
        self.rate_limit_waits = 0
        self.platform_counts = {}
        self.lock = threading.Lock()

    def record_request(self, platform: str, delay_time: float, rate_limit_wait: float = 0.0):
        with self.lock:
            self.total_requests += 1
            self.total_delay_time += delay_time
            if rate_limit_wait > 0:
                self.rate_limit_waits += 1
            self.platform_counts[platform] = self.platform_counts.get(platform, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            avg_delay = self.total_delay_time / self.total_requests if self.total_requests > 0 else 0
            return {
                "total_requests": self.total_requests,
                "total_delay_time": round(self.total_delay_time, 2),
                "average_delay": round(avg_delay, 2),
                "rate_limit_waits": self.rate_limit_waits,
                "platform_counts": self.platform_counts.copy(),
                "timestamp": datetime.now().isoformat(),
            }


HUMANIZATION_STATS = HumanizationStats()


def record_humanized_request(platform: str, delay_time: float, rate_limit_wait: float = 0.0):
    HUMANIZATION_STATS.record_request(platform, delay_time, rate_limit_wait)


def get_humanization_stats() -> Dict[str, Any]:
    return HUMANIZATION_STATS.get_stats()
