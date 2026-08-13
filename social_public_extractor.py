# social_public_extractor.py - Extrae de fuentes públicas SIN credenciales
# Versión 1.1 - Más fuentes públicas añadidas

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import feedparser
import requests
import urllib3

urllib3.disable_warnings()

# Proxies de TOR (socks5h = DNS tambien resuelto via Tor)
# Puerto 9150 = Tor Browser | Puerto 9050 = Tor como servicio de sistema
TOR_PROXIES = {"http": "socks5h://127.0.0.1:9150", "https": "socks5h://127.0.0.1:9150"}

# Fallback a puerto 9050 (Tor como servicio)
TOR_PROXIES_ALT = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}

# Dominios que bloquean activamente conexiones desde nodos Tor
TOR_BLOCKED_DOMAINS = ["t.me", "telegram.org", "reddit.com", "facebook.com", "instagram.com", "tiktok.com"]

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


def safe_get(url: str, timeout: int = 12, *args, **kwargs):
    """
    Estrategia de conexión en capas:
    1. Si el dominio bloquea Tor -> va directo (sin perder tiempo)
    2. Si Tor esta disponible -> lo intenta primero (detecta puerto automáticamente)
    3. Si falla -> fallback a internet normal
    """

    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

    # Detectar si el dominio bloquea Tor y saltar directo
    domain = url.split("/")[2] if "://" in url else url
    if any(blocked in domain for blocked in TOR_BLOCKED_DOMAINS):
        return requests.get(url, headers=headers, timeout=timeout, verify=False)

    # Detectar puerto de Tor disponible usando caché
    tor_port = get_tor_port()

    # Si Tor está disponible, intentar usarlo
    if tor_port:
        tor_proxies = {"http": f"socks5h://127.0.0.1:{tor_port}", "https": f"socks5h://127.0.0.1:{tor_port}"}
        try:
            resp = requests.get(url, headers=headers, proxies=tor_proxies, timeout=timeout, verify=False)
            # Si el código es 200 pero no hay contenido, probablemente es un bloqueo silencioso de Tor
            if resp.status_code == 200 and not resp.content:
                logger.warning(f"[TOR] Respuesta vacía de {domain} vía Tor. Intentando conexión directa...")
            else:
                return resp
        except Exception as e:
            err = str(e)
            if "timed out" in err.lower() or "ConnectTimeout" in err:
                logger.warning(f"[TOR] Timeout via Tor puerto {tor_port} para {domain}. Usando conexión directa.")
            elif "SOCKS" in err or "ProxyError" in err:
                logger.warning(f"[TOR] Error SOCKS en puerto {tor_port}. Usando conexión directa.")
            else:
                logger.warning(f"[TOR] Error en puerto {tor_port} para {domain}: {err}. Usando conexión directa.")

    # Fallback a conexion normal
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
    # Nuevos - Canales de noticias principales
    "lapatilla": "https://t.me/s/lapatilla",
    "efectococuyo": "https://t.me/s/efectococuyo",
    "runrunes": "https://t.me/s/runrunes",
    "elnacionalweb": "https://t.me/s/elnacionalweb",
    "ultimasnoticias": "https://t.me/s/ultimasnoticias",
    # Nuevos - Canales de política y análisis
    "venezuelalive": "https://t.me/s/venezuelalive",
    "venezuelaalerta": "https://t.me/s/venezuelaalerta",
    "venezuelanews": "https://t.me/s/venezuelanews",
    "venezuelaactualidad": "https://t.me/s/venezuelaactualidad",
    # Nuevos - Canales de economía
    "dolartoday": "https://t.me/s/dolartoday",
    "monitorvenezuela": "https://t.me/s/monitorvenezuela",
    "economia_venezuela": "https://t.me/s/economia_venezuela",
    # Nuevos - Canales de seguridad y emergencias
    "venezuelaseguridad": "https://t.me/s/venezuelaseguridad",
    "alertas_venezuela": "https://t.me/s/alertas_venezuela",
    "emergencias_venezuela": "https://t.me/s/emergencias_venezuela",
    "noticierovenevision": "https://t.me/s/noticierovenevision",
    "NoticiasCaracol": "https://t.me/s/NoticiasCaracol",
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
REDDIT_PUBLIC_SUBREDDITS = ["vzla", "venezuela", "LatinAmerica", "worldnews"]


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
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
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
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
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
                    results.append(
                        {
                            "title": (post.get("content", "")[:140]).replace("<p>", "").replace("</p>", ""),
                            "summary": post.get("content", "")[:280],
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
    """Extrae de Reddit usando Frontends Alternativos (Redlib) para evadir bloqueo"""
    results = []
    # Usamos redlib.catsarch.com u otra instancia de Redlib/Libreddit que no esté bloqueada
    for sub in REDDIT_PUBLIC_SUBREDDITS:
        try:
            url = f"https://redlib.catsarch.com/r/{sub}/rss"
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:3]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#").replace("redlib.catsarch.com", "reddit.com"),
                        "published": entry.get("published", ""),
                        "source": f"Reddit: r/{sub}",
                        "type": "reddit",
                    }
                )
        except Exception as e:
            print(f"[WARN] Reddit Frontend r/{sub}: {e}")
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
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
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
    "News.google (Venezuela)": "https://news.google.com/rss/search?q=venezuela&hl=es-CO&gl=CO&ceid=CO:es",
    "Yahoo News Venezuela": "https://news.yahoo.com/rss/tag/venezuela",
    "Microsoft News Venezuela": "https://www.bing.com/news/search?q=venezuela&format=rss",
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
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
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
    "El Espectador (Colombia)": "https://www.elespectador.com/rss/mundo/",
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
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
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
