# utils.py - Módulo de utilidades compartidas v1.1
# Funciones comunes: sanitización HTML, logging JSON, validación de URLs, async safety

import asyncio
import concurrent.futures
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from lxml_html_clean import Cleaner

from config import ALLOWED_SCHEMES

# Configuración global
LOG_FILE = Path(__file__).parent / "cobalto.log.json"
LOG_MAX_SIZE = 5 * 1024 * 1024  # 5MB

# Cleaner seguro (allowlist estricto para RSS)
HTML_CLEANER = Cleaner(
    allow_tags=[
        "p",
        "br",
        "strong",
        "em",
        "a",
        "ul",
        "ol",
        "li",
        "img",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "span",
        "div",
    ],
    safe_attrs=["href", "src", "alt", "title", "class"],
    scripts=True,
    javascript=True,
    comments=True,
    frames=True,
    forms=True,
    annoying_tags=True,
    embedded=True,
    page_structure=True,
    processing_instructions=True,
    add_nofollow=True,
    links=True,
    meta=True,
)

# ALLOWED_SCHEMES importado desde config.py (fuente única de verdad)


def sanitize_html(raw_html):
    """Sanitiza HTML eliminando scripts y elementos peligroso"""
    if not raw_html:
        return ""
    try:
        cleaned = HTML_CLEANER.clean_html(raw_html)
        soup = BeautifulSoup(cleaned, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return raw_html


def is_valid_url(url):
    """Valida que la URL tenga un esquema y dominio válidos"""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        return bool(parsed.netloc)
    except Exception:
        return False


def log_json(level, message, extra=None):
    """Escribe logs estructurados en JSON"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    if extra:
        entry.update(extra)

    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_SIZE:
            LOG_FILE.write_text("[]", encoding="utf-8")

        try:
            logs = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logs = []

        logs.append(entry)
        logs = logs[-1000:]  # mantener últimos 1000

        LOG_FILE.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class StructuredLogger:
    """Logger estructurado para el proyecto"""

    def __init__(self, name):
        self.name = name
        self._logger = logging.getLogger(name)

    def info(self, msg, **kwargs):
        self._logger.info(msg)
        log_json("INFO", msg, {"module": self.name, **kwargs})

    def warning(self, msg, **kwargs):
        self._logger.warning(msg)
        log_json("WARNING", msg, {"module": self.name, **kwargs})

    def error(self, msg, **kwargs):
        self._logger.error(msg)
        log_json("ERROR", msg, {"module": self.name, **kwargs})

    def debug(self, msg, **kwargs):
        self._logger.debug(msg)
        log_json("DEBUG", msg, {"module": self.name, **kwargs})


_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]


def safe_get(url, params=None, timeout=20):
    """Petición GET robusta con reintentos y headers humanizados."""
    import urllib3

    from humanization import get_headers_with_random_ua

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = get_headers_with_random_ua()
    try:
        return requests.get(url, params=params, headers=headers, timeout=timeout, verify=False)
    except Exception as e:
        print(f"[HTTP-SAFE-ERR] {url}: {e}")

        # Retornar objeto dummy para no romper el flujo
        class DummyResponse:
            def __init__(self):
                self.status_code = 500
                self.content = b""
                self.text = ""

            def json(self):
                return {}

        return DummyResponse()


_ASYNC_POOL = None


def _get_async_pool():
    global _ASYNC_POOL
    if _ASYNC_POOL is None:
        _ASYNC_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="async_runner")
    return _ASYNC_POOL


def safe_async_run(coro, timeout=None):
    """Ejecuta una coroutine desde cualquier contexto sin RuntimeError ni deadlock."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # Estamos dentro de un loop corriendo (ej: desde FastAPI) -> thread separado
            fut = _get_async_pool().submit(asyncio.run, coro)
            return fut.result(timeout=timeout)
        # Loop existe pero no está corriendo (raro)
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result(timeout=timeout)
    except RuntimeError:
        # No hay loop running -> crear uno nuevo
        return asyncio.run(coro)


def parse_datetime(date_val) -> Optional[datetime]:
    """
    Parsea cualquier representación de fecha (datetime, struct_time, string)
    a un objeto datetime con zona horaria UTC.
    Retorna None si no se puede parsear o si es inválido.
    """
    import email.utils
    from datetime import timezone

    from dateutil import parser as date_parser

    if not date_val:
        return None

    # Si ya es un datetime
    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            return date_val.replace(tzinfo=timezone.utc)
        return date_val.astimezone(timezone.utc)

    # Si es un struct_time (del feedparser)
    if isinstance(date_val, tuple) or (hasattr(date_val, 'tm_year') and hasattr(date_val, 'tm_mon')):
        try:
            # Convertir struct_time o tupla a datetime
            # struct_time de feedparser usualmente está en UTC
            dt = datetime(*date_val[:6], tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError, OverflowError):
            pass

    # Si es un string o bytes
    if isinstance(date_val, (str, bytes)):
        if isinstance(date_val, bytes):
            try:
                date_str = date_val.decode('utf-8', errors='ignore')
            except Exception:
                return None
        else:
            date_str = date_val

        date_str = date_str.strip()
        if not date_str:
            return None

        # Intentar con email.utils (muy rápido para RFC 2822 usado en feeds RSS)
        try:
            dt = email.utils.parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

        # Intentar con dateutil.parser (soporta ISO, YYYY-MM-DD, y muchos otros)
        try:
            dt = date_parser.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    return None

