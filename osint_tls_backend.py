# osint_tls_backend.py - Motor de Peticiones con Firma TLS Rotativa (JA3 Evasion)
# Utiliza tls_client para simular fingerprints de navegadores reales.

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional

import requests as std_requests

# tls_client es opcional - si no está disponible, usamos requests normal
try:
    import tls_client

    HAS_TLS = True
except ImportError:
    HAS_TLS = False

logger = logging.getLogger("TLSBackend")

# Perfiles extendidos con Client Hints
CLIENT_PROFILES = ["chrome_112", "chrome_114", "firefox_112", "safari_16_0", "opera_95"]


def _fix_proxy_scheme(proxies: Optional[Dict]) -> Optional[Dict]:
    """Convierte socks5h:// a socks5:// para compatibilidad con tls_client."""
    if not proxies:
        return proxies
    fixed = {}
    for scheme, url in proxies.items():
        if isinstance(url, str) and url.startswith("socks5h://"):
            url = url.replace("socks5h://", "socks5://", 1)
        fixed[scheme] = url
    return fixed


class TLSSessionManager:
    """Gestiona sesiones con firmas TLS rotativas y headers aprendidos."""

    def __init__(self):
        self.sessions = {}

    def _get_learned_headers(self, platform: str) -> Dict:
        """Carga headers guardados por el Playwright Sniffer."""
        filename = Path(__file__).parent / f"learned_headers_{platform}.json"
        if filename.exists():
            try:
                with open(filename, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _request_via_requests(
        self,
        method: str,
        url: str,
        headers: Dict = None,
        params: Dict = None,
        data: Any = None,
        json: Any = None,
        proxies: Dict = None,
        timeout: int = 30,
    ) -> Optional[Any]:
        """Fallback a requests estándar cuando tls_client no puede usarse."""
        try:
            resp = std_requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                proxies=proxies,
                timeout=timeout,
            )
            return resp
        except Exception as e:
            logger.error(f"[REQUESTS ERROR] {url[:60]}: {e}")
            return None

    def request(
        self,
        method: str,
        url: str,
        platform: str = "default",
        headers: Dict = None,
        params: Dict = None,
        data: Any = None,
        json_data: Any = None,
        proxies: Dict = None,
        timeout: int = 30,
    ) -> Optional[Any]:
        """Realiza una petición con fallback automático si tls_client no soporta el proxy."""

        # Construir headers finales
        learned = self._get_learned_headers(platform)
        final_headers = {**learned}
        if headers:
            final_headers.update(headers)

        # Intentar con tls_client si está disponible
        if HAS_TLS:
            try:
                profile = random.choice(CLIENT_PROFILES)
                session = tls_client.Session(
                    client_identifier=profile, random_tls_extension_order=True, force_http1=False
                )
                if "chrome" in profile:
                    final_headers.update(
                        {
                            "sec-ch-ua": '"Google Chrome";v="112", "Not)A;Brand";v="8", "Chromium";v="112"',
                            "sec-ch-ua-mobile": "?0",
                            "sec-ch-ua-platform": '"Windows"',
                        }
                    )
                # Corregir esquema socks5h -> socks5
                safe_proxies = _fix_proxy_scheme(proxies)
                response = session.execute_request(
                    method=method,
                    url=url,
                    headers=final_headers,
                    params=params,
                    data=data,
                    json=json_data,
                    proxy=safe_proxies,
                    timeout_seconds=timeout,
                )
                return response
            except Exception as e:
                logger.warning(f"[TLS FALLBACK] {platform}: {e} -> usando requests")

        # Fallback a requests estándar
        return self._request_via_requests(
            method=method,
            url=url,
            headers=final_headers,
            params=params,
            data=data,
            json=json_data,
            proxies=proxies,
            timeout=timeout,
        )


# Instancia global
tls_manager = TLSSessionManager()
