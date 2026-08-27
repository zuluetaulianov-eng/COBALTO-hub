"""
tls_evasion.py - Motor de Evasión TLS Ligera con JA3 & HTTP/2 Impersonation

Permite realizar peticiones HTTP/2 superando protecciones Cloudflare, Akamai e Imperva
mediante simulación exacta de la huella digital TLS (JA3 cipher suites, extensiones)
de navegadores reales (Chrome, Firefox, Safari) sin requerir un navegador Chromium completo.
"""

import asyncio
import logging
import random
from typing import Dict, Optional, Tuple

import tls_client

logger = logging.getLogger(__name__)

# Perfiles de navegadores soportados por tls-client
TLS_PROFILES = [
    "chrome_120",
    "chrome_119",
    "firefox_120",
    "firefox_117",
    "safari_16_0",
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def fetch_tls_sync(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 15,
    profile: Optional[str] = None,
) -> Tuple[int, str, Dict[str, str]]:
    """
    Realiza una petición GET síncrona evadiendo restricciones TLS/JA3.

    Returns:
        Tuple (status_code, text_content, response_headers)
    """
    selected_profile = profile or random.choice(TLS_PROFILES)
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)

    try:
        session = tls_client.Session(
            client_identifier=selected_profile,
            random_tls_extension_order=True,
        )
        resp = session.get(url, headers=req_headers, timeout_seconds=timeout_seconds)
        resp_headers = dict(resp.headers) if hasattr(resp, "headers") else {}
        return resp.status_code, resp.text, resp_headers
    except Exception as e:
        logger.debug(f"[TLS EVASION] Error en petición síncrona a {url}: {e}")
        return 0, "", {}


async def fetch_tls_async(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 15,
    profile: Optional[str] = None,
) -> Tuple[int, str, Dict[str, str]]:
    """
    Wrapper asíncrono para ejecutar fetch_tls_sync en el executor de asyncio.

    Returns:
        Tuple (status_code, text_content, response_headers)
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, fetch_tls_sync, url, headers, timeout_seconds, profile
    )
