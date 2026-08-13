"""
doh_patch.py - Escudo DNS-over-HTTPS Anti-Censura
Resuelve el DNS mediante Cloudflare/Google antes de instalar el parche
para evitar el bug de recursión infinita en socket.getaddrinfo.
"""

import json
import logging
import socket
import ssl
import time
import urllib.request

logger = logging.getLogger(__name__)

_original_getaddrinfo = socket.getaddrinfo
_dns_cache = {}
_DNS_CACHE_TTL = 300  # 5 minutos

_DOH_TIMEOUT = 5

# Dominios que NUNCA pasan por DoH — usan DNS local directo
DOH_BYPASS_DOMAINS = {
    "api.groq.com",
    "groq.com",
    "api.openai.com",
    "openai.com",
    "generativelanguage.googleapis.com",
    "api.telegram.org",
    "zrok.io",
    "share.zrok.io",
    "127.0.0.1",
    "localhost",
    "::1",
    "ve.dolarapi.com",
    "bcv.org.ve",
}

DOH_ENDPOINTS = [
    ("1.1.1.1", "https://1.1.1.1/dns-query?name={host}&type=A", "application/dns-json"),
    ("1.0.0.1", "https://1.0.0.1/dns-query?name={host}&type=A", "application/dns-json"),
    ("8.8.8.8", "https://8.8.8.8/resolve?name={host}&type=A", "application/json"),
    ("8.8.4.4", "https://8.8.4.4/resolve?name={host}&type=A", "application/json"),
]

_ssl_ctx = ssl.create_default_context()


def _doh_resolve(host: str):
    for server_ip, url_tpl, accept in DOH_ENDPOINTS:
        url = url_tpl.format(host=host)
        try:
            req = urllib.request.Request(url, headers={"accept": accept, "User-Agent": "CobaltoHub-DoH/1.0"})
            with urllib.request.urlopen(req, timeout=_DOH_TIMEOUT, context=_ssl_ctx) as resp:
                content = resp.read()
                if content:
                    try:
                        data = json.loads(content.decode())
                        for answer in data.get("Answer", []):
                            if answer.get("type") == 1:
                                return answer["data"]
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"[DOH] Error resolviendo {host} via {server_ip}: {e}")
            continue
    return None


def _doh_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if isinstance(host, bytes):
        host = host.decode("utf-8")
    if host == "localhost" or host == "::1":
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    parts = str(host).split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    if any(host == d or host.endswith("." + d) for d in DOH_BYPASS_DOMAINS):
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    now = time.time()
    if host in _dns_cache:
        entry = _dns_cache[host]
        if now - entry["ts"] < _DNS_CACHE_TTL:
            ip = entry["ip"]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        else:
            del _dns_cache[host]

    ip = _doh_resolve(host)
    if ip:
        _dns_cache[host] = {"ip": ip, "ts": now}
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    return _original_getaddrinfo(host, port, family, type, proto, flags)


def enable_doh():
    socket.getaddrinfo = _doh_getaddrinfo
    logger.info("[ESCUDO ACTIVO] DNS-over-HTTPS (DoH) activado -> Cloudflare + Google.")
