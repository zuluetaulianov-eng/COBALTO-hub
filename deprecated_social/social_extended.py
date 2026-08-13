# social_extended.py - Fuentes públicas ADICIONALES
# APIs gratuitas, scraping, Nitter, y más canales

import re
from datetime import datetime
from typing import Any, Dict, List

import feedparser
import requests

from social_public_extractor import safe_get  # Tor + fallback anti-censura

# ==========================================
# NEWSAPI - API gratuita (límite 100req/día)
# obtener clave gratis en: https://newsapi.org
# ==========================================
NEWSAPI_KEY = None  # Optional: pone tu clave en .env si tienes

NEWSAPI_ENDPOINTS = {
    "top_headlines": "https://newsapi.org/v2/top-headlines",
    "everything": "https://newsapi.org/v2/everything",
}


def search_newsapi(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Busca en NewsAPI (requiere API key opcional)"""
    if not NEWSAPI_KEY:
        return []
    results = []
    try:
        params = {
            "q": f"{query} Venezuela",
            "language": "es",
            "sortBy": "publishedAt",
            "pageSize": limit,
            "apiKey": NEWSAPI_KEY,
        }
        resp = safe_get(f"{NEWSAPI_ENDPOINTS['everything']}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        if resp.status_code == 200:
            data = resp.json()
            for article in data.get("articles", []):
                results.append(
                    {
                        "title": article.get("title", "")[:140],
                        "summary": article.get("description", "")[:280],
                        "link": article.get("url", "#"),
                        "published": article.get("publishedAt", ""),
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "type": "newsapi",
                    }
                )
    except Exception as e:
        print(f"[WARN] NewsAPI: {e}")
    return results


# ==========================================
# NITTER - Alternativa a Twitter sin login
# ==========================================
NITTER_INSTANCES = [
    "nitter.poast.org",
    "nitter.privacydev.net",
    "nitter.tiekoetter.com",
]

NITTER_USERS = [
    "EfectoCocuyo",
    "elnacionalweb",
    "DiarioTalCual",
    "VVperiodista",
    "notivenezuela",
]


def scrape_nitter(user: str, instance: str = "nitter.poast.org") -> List[Dict[str, Any]]:
    """Scraping de Twitter vía Nitter sin login"""
    results = []
    try:
        url = f"https://{instance}/{user}"
        resp = safe_get(url)
        if resp.status_code == 200:
            tweets = re.findall(r'class="tweet-content[^"]*"[^>]*>([^<]+)', resp.text)[:5]
            for tweet in tweets:
                if tweet.strip():
                    results.append(
                        {
                            "title": tweet.strip()[:140],
                            "summary": tweet.strip()[:280],
                            "link": url,
                            "published": datetime.now().isoformat(),
                            "source": f"Nitter @{user}",
                            "type": "nitter",
                        }
                    )
    except Exception as e:
        print(f"[WARN] Nitter {user}: {e}")
    return results


def get_nitter_all() -> List[Dict[str, Any]]:
    """Scrapea múltiples usuarios de Nitter"""
    results = []
    for user in NITTER_USERS:
        items = scrape_nitter(user)
        results.extend(items)
    return results


# ==========================================
# CANALES ADICIONALES DE TELEGRAM
# ==========================================
TELEGRAM_EXTRA_CHANNELS = {
    # Noticias generales Venezuela
    "noticias2": "https://t.me/s/noticias2",
    "A Toda Noticia": "https://t.me/s/ATodaNoticia",
    "Venezuela Hoy": "https://t.me/s/VenezuelaHoy",
    "Noticiero de Venezuela": "https://t.me/s/NoticieroVen",
    # Economía
    "Economía al Día": "https://t.me/s/economiaaldia",
    "DolarToday Venezuela": "https://t.me/s/dolartoday",
    # Política
    "Política Venezuela": "https://t.me/s/politicavzla",
    "360°": "https://t.me/s/venezuela360",
    # Tecnología
    "TecnoVenezuela": "https://t.me/s/tecnovenezuela",
    "CiberVenezuela": "https://t.me/s/cibervenezuela",
}


def get_telegram_extra() -> List[Dict[str, Any]]:
    """Extrae de canales adicionales de Telegram"""
    results = []
    for name, url in TELEGRAM_EXTRA_CHANNELS.items():
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
                        "source": f"Telegram: @{name}",
                        "type": "telegram_extra",
                    }
                )
        except Exception as e:
            print(f"[WARN] TG {name}: {e}")
    return results


# ==========================================
# FOROS Y COMUNIDADES ESPECIALIZADAS
# ==========================================
FORUMS = {
    "SecuritybyDefault (Espana)": "https://www.securitybydefault.com/feed/",
}


def get_forums() -> List[Dict[str, Any]]:
    """Extrae de foros especializados"""
    results = []
    for name, url in FORUMS.items():
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
                        "type": "forum",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# FUENTES ALTERNATIVAS DE VENEZUELA
# ==========================================
ALT_VENEZUELA = {
    "Mision Verdad": "https://misionverdad.com/feed",
    "La Iguana TV": "https://laiguana.tv/feed/",
}


def get_alt_venezuela() -> List[Dict[str, Any]]:
    """Extrae de fuentes alternativas de Venezuela"""
    results = []
    for name, url in ALT_VENEZUELA.items():
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
                        "type": "alt_venezuela",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# FEEDS DE PODCASTS
# ==========================================
PODCASTS = {
    "El Pitazo Audio": "https://www.spreaker.com/show/4403643/feed",
    "Venezuela Crisis": "https://feeds.soundcloud.com/users/soundcloud:users:322158009/sounds.rss",
}


def get_podcasts() -> List[Dict[str, Any]]:
    """Extrae de podcasts de Venezuela"""
    results = []
    for name, url in PODCASTS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": f"Podcast: {name}",
                        "type": "podcast",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# BÚSQUEDA EN TIEMPO REAL (DuckDuckGo)
# ==========================================
def search_duckduckgo(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Búsqueda en DuckDuckGo sin API"""
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}+Venezuela"
        resp = safe_get(url)
        if resp.status_code == 200:
            links = re.findall(r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', resp.text)
            for link, title in links[:limit]:
                results.append(
                    {
                        "title": title.strip()[:140],
                        "summary": f"Búsqueda: {query}",
                        "link": link,
                        "published": datetime.now().isoformat(),
                        "source": "DuckDuckGo",
                        "type": "search",
                    }
                )
    except Exception as e:
        print(f"[WARN] DuckDuckGo: {e}")
    return results


# ==========================================
# REDES SOCIALES CHINAS (sin restricciones)
# ==========================================
CHINESE_PLATFORMS = {
    "Weibo Search Venezuela": "https://s.weibo.com/weibo?q=Venezuela",
    "Toutiao (今日头条)": "https://www.toutiao.com/search/?keyword=Venezuela",
}


def get_chinese_social() -> List[Dict[str, Any]]:
    """Extrae de redes sociales chinas (alternativo)"""
    results = []
    for name, url in CHINESE_PLATFORMS.items():
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                titles = re.findall(r'"content_title[^>]*>([^<]+)', resp.text)[:5]
                for title in titles:
                    results.append(
                        {
                            "title": title.strip()[:140],
                            "summary": f"Contenido de {name}",
                            "link": url,
                            "published": datetime.now().isoformat(),
                            "source": name,
                            "type": "chinese",
                        }
                    )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# UNIFICAR TODAS LAS FUENTES
# ==========================================
def get_extended_sources() -> Dict[str, Any]:
    """Recolecta todas las fuentes adicionales"""
    import concurrent.futures

    now = datetime.now().isoformat()
    data = {"timestamp": now, "sources": {}, "count": 0}

    sources_funcs = [
        ("Telegram Extra", get_telegram_extra),
        ("Nitter (Twitter)", get_nitter_all),
        ("Foros Especializados", get_forums),
        ("Venezuela Alternativa", get_alt_venezuela),
        ("DuckDuckGo Búsqueda", lambda: search_duckduckgo("venezuela")),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(func): name for name, func in sources_funcs}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results = future.result()
                if results:
                    data["sources"][name] = results
                    data["count"] += len(results)
            except Exception as e:
                print(f"[ERROR] {name}: {e}")

    return data


if __name__ == "__main__":
    print("=== Fuentes extendidas SIN credenciales ===")
    data = get_extended_sources()
    print(f"Total: {data['count']} items")
    for source, items in data["sources"].items():
        print(f"  {source}: {len(items)} items")
