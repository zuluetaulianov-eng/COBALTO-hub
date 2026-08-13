"""
humanization.py - Módulo de humanización anti-bloqueo v9.1
Refactorizado en submódulos especializados para mantenibilidad.

Re-exporta todas las funciones/objetos públicos desde los submódulos
para mantener compatibilidad con importaciones existentes.
"""

from humanization_combined import humanized_request, safe_humanized_get  # noqa: F401
from humanization_delays import (  # noqa: F401
    human_delay,
    human_delay_async,
    human_delay_between_requests,
    human_delay_between_requests_async,
    simulate_human_browsing,
    simulate_human_browsing_async,
)
from humanization_proxy import get_proxies  # noqa: F401
from humanization_queue import TASK_QUEUE_AI, TASK_QUEUE_OSINT, AsyncTaskQueue  # noqa: F401
from humanization_ratelimit import (  # noqa: F401
    RATE_LIMITERS,
    RateLimiter,
    get_dynamic_max_requests,
    wait_for_rate_limit,
    wait_for_rate_limit_async,
)
from humanization_session import SESSION_MANAGER, SessionManager  # noqa: F401
from humanization_stats import (  # noqa: F401
    HUMANIZATION_STATS,
    HumanizationStats,
    get_humanization_stats,
    record_humanized_request,
)
from humanization_stress import STRESS_MONITOR, SystemStressMonitor  # noqa: F401
from humanization_ua import USER_AGENTS, get_headers_with_random_ua, get_random_user_agent  # noqa: F401
