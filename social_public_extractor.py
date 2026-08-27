# social_public_extractor.py - Extrae de fuentes públicas SIN credenciales
# Versión 1.1 - Más fuentes públicas añadidas

import html
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import requests
import urllib3

from config import REDLIB_INSTANCES, RESIDENTIAL_PROXY_URL
from osint_tls_backend import tls_manager

urllib3.disable_warnings()


def clean_text_summary(text: str, max_length: int = 280) -> str:
    """Limpia etiquetas HTML, unescape entidades, rastros de IA y artefactos de listas en resúmenes RSS/OSINT."""
    if not text:
        return ""
    try:
        text = html.unescape(str(text))
        text = re.sub(r'<(br|p|div|/p|/div)[^>]*>', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)

        # 1. Rastros de pensamiento de IA
        text = re.sub(r"(?i)<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"(?i)here'?s\s+a\s+thinking\s+process:?", "", text)
        text = re.sub(r"(?i)thinking\s+process:?", "", text)

        # 2. Artefactos de listas Python
        text = re.sub(r"^\s*\[?\s*(?:['\"][^'\"]*['\"]\s*,\s*)*['\"][^'\"]*['\"]\s*\]\s*", "", text)
        text = re.sub(r"^\s*['\"][^'\"]*['\"]\s*,\s*['\"][^'\"]*['\"]\s*\]\s*", "", text)
        text = re.sub(r"^\s*['\"\]\)]+\s*", "", text)

        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_length]
    except Exception:
        return str(text)[:max_length]


# Proxies de TOR (socks5h = DNS tambien resuelto via Tor)
TOR_PROXIES = {"http": "socks5h://127.0.0.1:9150", "https": "socks5h://127.0.0.1:9150"}

# Fallback a puerto 9050 (Tor como servicio)
TOR_PROXIES_ALT = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}

# Dominios que bloquean activamente conexiones desde nodos Tor
TOR_BLOCKED_DOMAINS = ["t.me", "telegram.org", "reddit.com", "facebook.com", "instagram.com", "tiktok.com"]

# Pool de instancias alternativas de Reddit (Redlib / Libreddit)
REDDIT_FRONTEND_INSTANCES = REDLIB_INSTANCES if REDLIB_INSTANCES else [
    "https://redlib.catsarch.com",
    "https://redlib.vlink.dev",
    "https://libreddit.privacydev.net",
    "https://redlib.freedit.eu",
    "https://libreddit.oxhead.nl",
]

logger = logging.getLogger("social_public_extractor")

_cached_tor_port = None
_last_tor_check_time = 0.0


def get_tor_port() -> Optional[int]:
    """Detecta el puerto de Tor disponible con caché de 60 segundos."""
    global _cached_tor_port, _last_tor_check_time
    import socket
    now = time.time()
    if now - _last_tor_check_time > 60.0:
        _cached_tor_port = None
        for port in [9150, 9050, 9151]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                try:
                    if sock.connect_ex(("127.0.0.1", port)) == 0:
                        _cached_tor_port = port
                        break
                finally:
                    sock.close()
            except Exception:
                continue
        _last_tor_check_time = now
    return _cached_tor_port


def check_tor_available() -> bool:
    """Verifica si Tor está disponible en alguno de los puertos"""
    return get_tor_port() is not None


# ── Circuit Breaker Tracker para endpoints externos con Exponential Backoff & Jitter ──
_circuit_breaker_state: Dict[str, Dict[str, Any]] = {}
MAX_FAILURES_BEFORE_BREAKER = 3
BASE_BREAKER_COOLDOWN = 300  # 5 minutos base
MAX_BREAKER_COOLDOWN = 1800  # 30 minutos máximo


def is_circuit_open(target_key: str) -> bool:
    """Retorna True si el circuito está abierto (desactivado por fallas consecutivas)."""
    now = time.time()
    state = _circuit_breaker_state.get(target_key)
    if not state:
        return False
    if state.get("failures", 0) >= MAX_FAILURES_BEFORE_BREAKER:
        if now < state.get("cooldown_until", 0.0):
            return True
        # Cooldown cumplido: permitir un intento de recuperación
        return False
    return False


def record_circuit_failure(target_key: str):
    """Registra un fallo e incrementa el tiempo de enfriamiento con Exponential Backoff & Jitter."""
    import random
    now = time.time()
    state = _circuit_breaker_state.setdefault(target_key, {"failures": 0, "cooldown_until": 0.0})
    state["failures"] += 1
    if state["failures"] >= MAX_FAILURES_BEFORE_BREAKER:
        exponent = min(state["failures"] - MAX_FAILURES_BEFORE_BREAKER, 4)
        backoff = min(MAX_BREAKER_COOLDOWN, BASE_BREAKER_COOLDOWN * (2 ** exponent))
        jitter = random.uniform(0.0, 30.0)
        cooldown_total = backoff + jitter
        state["cooldown_until"] = now + cooldown_total
        logger.warning(
            f"[CIRCUIT BREAKER] Circuito ABIERTO para {target_key} por {int(cooldown_total)}s (Exponential Backoff + Jitter, fallo #{state['failures']})."
        )


def record_circuit_success(target_key: str):
    """Registra una respuesta exitosa y resetea el contador de fallos."""
    if target_key in _circuit_breaker_state:
        _circuit_breaker_state[target_key] = {"failures": 0, "cooldown_until": 0.0}


def safe_get(url: str, timeout: int = 12, *args, **kwargs):
    """
    Estrategia de conexión en capas con TLS Fingerprint Evasion, Proxies y Circuit Breaker:
    1. Revisa si el circuito está abierto por fallas consecutivas previas.
    2. Si el dominio bloquea Tor -> usa TLS manager + Proxy Residencial (si está configurado).
    3. Si Tor está disponible -> lo intenta vía SOCKS con TLS manager.
    4. Fallback directo con firma TLS de navegador.
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

    domain = url.split("/")[2] if "://" in url else url

    if is_circuit_open(domain):
        logger.debug(f"[CIRCUIT BREAKER] Omitiendo {domain} por circuito abierto (fallback pasivo).")
        return None

    try:
        resp = _execute_safe_get(url, domain, headers, timeout)
        if resp is not None and getattr(resp, "status_code", 0) == 200:
            record_circuit_success(domain)
            return resp
        else:
            record_circuit_failure(domain)
            return resp
    except Exception as e:
        record_circuit_failure(domain)
        logger.warning(f"[SAFE_GET] Error consultando {domain}: {e}")
        return None


def _execute_safe_get(url: str, domain: str, headers: Dict[str, str], timeout: int):
    """Ejecuta la cadena de intentos de conexión HTTP/TLS."""
    # 1. Si el dominio bloquea Tor (Reddit, Telegram, Facebook, etc.)
    if any(blocked in domain for blocked in TOR_BLOCKED_DOMAINS):
        proxies = None
        proxy_url = RESIDENTIAL_PROXY_URL or os.getenv("RESIDENTIAL_PROXY_URL")
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        resp = tls_manager.request("GET", url, platform="social_public", proxies=proxies, timeout=timeout)
        if resp is not None and (getattr(resp, "status_code", 0) == 200 or getattr(resp, "content", None)):
            return resp

        try:
            return requests.get(url, headers=headers, proxies=proxies, timeout=timeout, verify=False)
        except Exception:
            return None

    # 2. Si Tor está disponible, intentar usarlo
    tor_port = get_tor_port()
    if tor_port:
        tor_proxies = {"http": f"socks5h://127.0.0.1:{tor_port}", "https": f"socks5h://127.0.0.1:{tor_port}"}
        try:
            resp = tls_manager.request("GET", url, platform="social_public", proxies=tor_proxies, timeout=timeout)
            if resp is not None and getattr(resp, "status_code", 0) == 200:
                return resp

            resp = requests.get(url, headers=headers, proxies=tor_proxies, timeout=timeout, verify=False)
            if resp.status_code == 200 and resp.content:
                return resp
        except Exception as e:
            logger.warning(f"[TOR] Error en puerto {tor_port} para {domain}: {e}. Fallback a TLS directo.")

    # 3. Fallback a conexión normal con TLS backend
    resp = tls_manager.request("GET", url, platform="social_public", timeout=timeout)
    if resp is not None:
        return resp

    return requests.get(url, headers=headers, timeout=timeout, verify=False)


# ==========================================
# TELEGRAM - Canales públicos (RSS)
# ==========================================
TELEGRAM_RSS_CHANNELS = {
    "notivenezuelaarma": "https://t.me/s/notivenezuelaarma",
    "venezuela_news": "https://t.me/s/venezuela_news",
    "elpetitvenezolano": "https://t.me/s/elpetitvenezolano",
    "vzlanoticias": "https://t.me/s/vzlanoticias",
    "infoVzla": "https://t.me/s/infoVzla",
    "noticiasvenezuela24": "https://t.me/s/noticiasvenezuela24",
    # Canales de noticias principales
    "lapatilla": "https://t.me/s/lapatilla",
    "efectococuyo": "https://t.me/s/efectococuyo",
    "runrunes": "https://t.me/s/runrunes",
    "elnacionalweb": "https://t.me/s/elnacionalweb",
    "ultimasnoticias": "https://t.me/s/ultimasnoticias",
    # Canales Colombia OSINT
    "NoticiasCaracol": "https://t.me/s/NoticiasCaracol",
    "ElTiempo_co": "https://t.me/s/eltiempo_co",
    "RevistaSemana": "https://t.me/s/RevistaSemana",
    # Canales de política y análisis
    "venezuelalive": "https://t.me/s/venezuelalive",
    "venezuelaalerta": "https://t.me/s/venezuelaalerta",
    "venezuelanews": "https://t.me/s/venezuelanews",
    "venezuelaactualidad": "https://t.me/s/venezuelaactualidad",
    # Canales de economía
    "dolartoday": "https://t.me/s/dolartoday",
    "monitorvenezuela": "https://t.me/s/monitorvenezuela",
    "economia_venezuela": "https://t.me/s/economia_venezuela",
    # Canales de seguridad y emergencias
    "venezuelaseguridad": "https://t.me/s/venezuelaseguridad",
    "alertas_venezuela": "https://t.me/s/alertas_venezuela",
    "emergencias_venezuela": "https://t.me/s/emergencias_venezuela",
    "noticierovenevision": "https://t.me/s/noticierovenevision",
}

# ==========================================
# YOUTUBE - Canales (RSS)
# ==========================================
YOUTUBE_CHANNELS = {
    "DVLVnoticias": "https://www.youtube.com/feeds/videos.xml?channel_id=UCW6_xiR4xL7LAaVRqMqKcRA",
    "VTvCanal8": "https://www.youtube.com/feeds/videos.xml?channel_id=UCc3cqcXjCDN5cU9I1Iqk9dQ",
}

# ==========================================
# MASTODON - Instancias alternativas (Anti-Censura)
# ==========================================
# Se evitan mastodon.social y mastodon.cloud porque suelen estar bloqueadas.
MASTODON_INSTANCES = {
    "mstdn.social": "https://mstdn.social/api/v1/timelines/public?limit=20",
    "mas.to": "https://mas.to/api/v1/timelines/public?limit=20",
    "infosec.exchange": "https://infosec.exchange/api/v1/timelines/public?limit=20",
}

# ==========================================
# REDDIT - Subreddits públicos
# ==========================================
REDDIT_PUBLIC_SUBREDDITS = ["vzla", "venezuela", "Colombia", "bogota", "medellin", "OSINT", "Geopolitics", "LatinAmerica", "worldnews"]


def get_telegram_rss() -> List[Dict[str, Any]]:
    """Extrae de canales de Telegram vía RSS (sin API)"""
    results = []
    for name, url in TELEGRAM_RSS_CHANNELS.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:5]:
                results.append(
                    {
                        "title": clean_text_summary(entry.get("title", "Sin título"), 140),
                        "summary": clean_text_summary(entry.get("summary", "") or entry.get("description", ""), 280),
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": f"Telegram: @{name}",
                        "type": "telegram",
                    }
                )
        except Exception as e:
            print(f"[WARN] Telegram RSS {name}: {e}")
    return results


def get_youtube_rss() -> List[Dict[str, Any]]:
    """Extrae de canales de YouTube vía RSS"""
    results = []
    for name, url in YOUTUBE_CHANNELS.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:3]:
                thumbnail = ""
                if hasattr(entry, "media_thumbnails") and entry.media_thumbnails:
                    thumbnail = entry.media_thumbnails[0].get("url", "")
                results.append(
                    {
                        "title": clean_text_summary(entry.get("title", "Sin título"), 140),
                        "summary": clean_text_summary(entry.get("summary", "") or entry.get("description", ""), 280),
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "image": thumbnail,
                        "source": f"YouTube: {name}",
                        "type": "youtube",
                    }
                )
        except Exception as e:
            print(f"[WARN] YouTube RSS {name}: {e}")
    return results


def get_mastodon_public() -> List[Dict[str, Any]]:
    """Extrae de instancias públicas de Mastodon (sin login)"""
    results = []
    for instance, url in MASTODON_INSTANCES.items():
        try:
            resp = safe_get(url)
            if resp.status_code == 200:
                data = resp.json()
                for post in data[:5]:
                    raw_content = post.get("content", "")
                    results.append(
                        {
                            "title": clean_text_summary(raw_content, 140),
                            "summary": clean_text_summary(raw_content, 280),
                            "link": post.get("url", "#"),
                            "published": post.get("created_at", ""),
                            "source": f"Mastodon: {instance}",
                            "type": "mastodon",
                        }
                    )
        except Exception as e:
            print(f"[WARN] Mastodon {instance}: {e}")
    return results


def get_reddit_public() -> List[Dict[str, Any]]:
    """Extrae de Reddit usando un pool de Frontends Alternativos (Redlib/Libreddit) con fallback dinámico"""
    results = []
    for sub in REDDIT_PUBLIC_SUBREDDITS:
        extracted = False
        for instance_base in REDDIT_FRONTEND_INSTANCES:
            try:
                url = f"{instance_base.rstrip('/')}/r/{sub}/rss"
                resp = safe_get(url, timeout=10)
                if not resp or getattr(resp, "status_code", 0) != 200 or not getattr(resp, "content", None):
                    continue
                feed = feedparser.parse(resp.content)
                if not feed.entries:
                    continue

                netloc = urlparse(instance_base).netloc
                for entry in feed.entries[:3]:
                    raw_link = entry.get("link", "#")
                    canonical_link = raw_link.replace(netloc, "reddit.com").replace("http://", "https://")
                    results.append(
                        {
                            "title": clean_text_summary(entry.get("title", "Sin título"), 140),
                            "summary": clean_text_summary(entry.get("summary", "") or entry.get("description", ""), 280),
                            "link": canonical_link,
                            "published": entry.get("published", ""),
                            "source": f"Reddit: r/{sub}",
                            "type": "reddit",
                        }
                    )
                extracted = True
                break  # Éxito con esta instancia
            except Exception as e:
                logger.warning(f"[WARN] Reddit Frontend {instance_base} r/{sub}: {e}")
                continue
        if not extracted:
            logger.warning(f"[WARN] No se pudo extraer r/{sub} desde ninguna instancia de Redlib.")
    return results


# ==========================================
# NOTICIAS INTERNACIONALES - Feeds RSS
# ==========================================
NEWS_INTERNATIONAL_FEEDS = {
    "BBC Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "DW Español": "https://www.dw.com/es/rss",
    "France24": "https://www.france24.com/es/rss",
    "Reuters Latinoamérica": "https://www.reutersagency.com/feed/?best-regions=latin-america",
    "VOA Español": "https://www.voanews.com/api/z-ipqsmg-_",
    "Al Jazeera Español": "https://www.aljazeera.com/xml/rss/all.xml",
    "EFE Latinoamérica": "https://efe.com/efe/america/rss",
    "Rusia Today Español": "https://actualidad.rt.com/rss.xml",
    "Sputnik Mundo": "https://mundo.sputniknews.com/export/rss2/all.xml",
}


def get_news_international() -> List[Dict[str, Any]]:
    """Extrae de feeds de noticias internacionales"""
    results = []
    for name, url in NEWS_INTERNATIONAL_FEEDS.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:3]:
                results.append(
                    {
                        "title": clean_text_summary(entry.get("title", "Sin título"), 140),
                        "summary": clean_text_summary(entry.get("summary", "") or entry.get("description", ""), 280),
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "news_intl",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# AGREGADORES DE NOTICIAS
# ==========================================
NEWS_AGGREGATORS = {
    "Google News (Venezuela)": "https://news.google.com/rss/search?q=venezuela&hl=es-CO&gl=CO&ceid=CO:es",
    "Google News (Colombia)": "https://news.google.com/rss/search?q=colombia&hl=es-CO&gl=CO&ceid=CO:es",
    "Google News (Conflicto Colombia)": "https://news.google.com/rss/search?q=eln+OR+emc+OR+clan+del+golfo+colombia&hl=es-CO&gl=CO&ceid=CO:es",
    "Yahoo News Venezuela": "https://news.yahoo.com/rss/tag/venezuela",
    "Microsoft News Venezuela": "https://www.bing.com/news/search?q=venezuela&format=rss",
    "Microsoft News Colombia": "https://www.bing.com/news/search?q=colombia&format=rss",
}


def get_news_aggregators() -> List[Dict[str, Any]]:
    """Extrae de agregadores de noticias"""
    results = []
    for name, url in NEWS_AGGREGATORS.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:4]:
                results.append(
                    {
                        "title": clean_text_summary(entry.get("title", "Sin título"), 140),
                        "summary": clean_text_summary(entry.get("summary", "") or entry.get("description", ""), 280),
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "aggregator",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# MEDIOS LATINOAMERICANOS
# ==========================================
LATAM_NEWS = {
    "El Tiempo (Colombia)": "https://www.eltiempo.com/rss/mundo.xml",
    "El Espectador (Colombia)": "https://www.elespectador.com/arc/outboundfeeds/rss/?outputType=xml",
    "Verdad Abierta (Colombia)": "https://verdadabierta.com/feed/",
    "InSight Crime ES": "https://es.insightcrime.org/feed/",
    "Indepaz": "https://indepaz.org.co/feed/",
    "La Jornada (México)": "https://www.jornada.com.mx/rss/mundo",
    "La Prensa (Panamá)": "https://www.prensa.com/rss/mundo.xml",
    "El Mercurio (Chile)": "https://www.elmercurio.com/rss/internacional.xml",
}


def get_latam_news() -> List[Dict[str, Any]]:
    """Extrae de medios latinoamericanos"""
    results = []
    for name, url in LATAM_NEWS.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:3]:
                results.append(
                    {
                        "title": clean_text_summary(entry.get("title", "Sin título"), 140),
                        "summary": clean_text_summary(entry.get("summary", "") or entry.get("description", ""), 280),
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "latam",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# PLATAFORMAS DE STREAMING/VIDEO
# ==========================================
VIDEO_PLATFORMS = {
    "Rumble (canales择)": "https://rumble.com/rss/Venezuela.xml",
    "Odysee (LBRY)": "https://odysee.com/@Venezuela:b/rss",
}


def get_video_platforms() -> List[Dict[str, Any]]:
    """Extrae de plataformas de video alternativas"""
    results = []
    for name, url in VIDEO_PLATFORMS.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:3]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "video",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# AGREGAR A LA FUNCIÓN PRINCIPAL
# ==========================================
def get_public_social_data() -> Dict[str, Any]:
    """Extrae datos de fuentes públicas sin credenciales"""
    now = datetime.now().isoformat()

    data = {"timestamp": now, "sources": {}, "count": 0, "auth_required": False}

    # Telegram RSS
    telegram_items = get_telegram_rss()
    if telegram_items:
        data["sources"]["Telegram (RSS)"] = telegram_items
        data["count"] += len(telegram_items)

    # YouTube RSS
    youtube_items = get_youtube_rss()
    if youtube_items:
        data["sources"]["YouTube (RSS)"] = youtube_items
        data["count"] += len(youtube_items)

    # Mastodon público
    mastodon_items = get_mastodon_public()
    if mastodon_items:
        data["sources"]["Mastodon"] = mastodon_items
        data["count"] += len(mastodon_items)

    # Reddit sin auth
    reddit_items = get_reddit_public()
    if reddit_items:
        data["sources"]["Reddit (público)"] = reddit_items
        data["count"] += len(reddit_items)

    # Noticias internacionales
    news_intl = get_news_international()
    if news_intl:
        data["sources"]["Noticias Internacionales"] = news_intl
        data["count"] += len(news_intl)

    # Agregadores de noticias
    aggregators = get_news_aggregators()
    if aggregators:
        data["sources"]["Agregadores"] = aggregators
        data["count"] += len(aggregators)

    # Medios latinoamericanos
    latam = get_latam_news()
    if latam:
        data["sources"]["Latinoamérica"] = latam
        data["count"] += len(latam)

    # Plataformas de video alternativas
    video = get_video_platforms()
    if video:
        data["sources"]["Video Alternativo"] = video
        data["count"] += len(video)

    if not data["sources"]:
        data["sources"]["info"] = [
            {
                "title": "Sin fuentes disponibles",
                "summary": "No se pudieron obtener datos de fuentes públicas",
                "link": "#",
                "published": now,
                "source": "Sistema",
            }
        ]

    return data


if __name__ == "__main__":
    print("=== Extracción pública SIN credenciales ===")
    data = get_public_social_data()
    print(f"Total: {data['count']} items")
    for source, items in data["sources"].items():
        print(f"  {source}: {len(items)} items")
