# metrics.py - Monitoreo y Telemetría para Cobalto Hub

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# ── Métricas de Infraestructura (HTTP) ───────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "cobalto_http_requests_total", "Total de peticiones HTTP", ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION = Histogram(
    "cobalto_http_request_duration_seconds", "Latencia de peticiones HTTP", ["method", "endpoint"]
)

# ── Métricas de Inteligencia (OSINT) ─────────────────────────────
OSINT_NEWS_COUNT = Gauge("cobalto_osint_news_total", "Número total de noticias en el dashboard")

OSINT_ALERTS_COUNT = Gauge("cobalto_osint_alerts_total", "Número de alertas activas por severidad", ["severity"])

OSINT_UPDATE_DURATION = Histogram(
    "cobalto_osint_update_duration_seconds", "Tiempo de ejecución del pipeline de actualización", ["priority_mode"]
)

OSINT_SOURCES_ACTIVE = Gauge("cobalto_osint_sources_active", "Número de fuentes de información activas")

# ── Métricas de Usuario y Red ────────────────────────────────────
ACTIVE_WEBSOCKETS = Gauge("cobalto_active_connections", "Conexiones WebSocket activas actualmente")

RATE_LIMIT_HITS = Counter(
    "cobalto_rate_limit_hits_total", "Número de veces que se ha activado el rate limiting", ["module"]
)


# ── Funciones de Utilidad ────────────────────────────────────────
def get_metrics_report():
    """Genera el reporte en formato Prometheus."""
    return generate_latest(), CONTENT_TYPE_LATEST
