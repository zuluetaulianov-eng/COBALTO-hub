# search_social.py - Búsqueda multiplataforma SIN credenciales
# Busca noticias en fuentes públicas usando APIs y scraping básico

import os
from datetime import datetime
from typing import Any, Dict, List

import feedparser
import requests

from config import RESIDENTIAL_PROXY_URL
from osint_tls_backend import tls_manager

SEARCH_KEYWORDS = [
    "venezuela",
    "noticias",
    "politica",
    "economia",
    "chavismo",
    "oposicion",
    "maduro",
    "dolar",
    "sanciones",
    "eeuu",
    "rusia",
    "ciberseguridad",
    "tecnologia",
    "inteligencia artificial",
]


def search_google_news(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca en Google News vía RSS (sin API key)"""
    results = []
    try:
        url = f"https://news.google.com/rss/search?q={keyword}+venezuela&hl=es&gl=VE&ceid=VE:es"
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:150],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "Google News",
                    "type": "google",
                }
            )
    except Exception as e:
        print(f"[WARN] Google News: {e}")
    return results


def search_bing_news(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca en Bing News vía RSS"""
    results = []
    try:
        url = f"https://www.bing.com/news/search?q={keyword}+venezuela&format=rss"
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:150],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "Bing News",
                    "type": "bing",
                }
            )
    except Exception as e:
        print(f"[WARN] Bing News: {e}")
    return results


def search_youtube(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca videos en YouTube vía RSS de búsqueda"""
    results = []
    try:
        # YouTube no tiene RSS de búsqueda, usamos scraping básico
        url = f"https://www.youtube.com/results?search_query={keyword}+venezuela"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            # Extracción básica de títulos
            import re

            titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"', resp.text)[:limit]
            for title in titles:
                results.append(
                    {
                        "title": title[:150],
                        "summary": f"Video sobre {keyword}",
                        "link": f"https://youtube.com/results?search_query={keyword}",
                        "published": datetime.now().isoformat(),
                        "source": "YouTube",
                        "type": "youtube",
                    }
                )
    except Exception as e:
        print(f"[WARN] YouTube: {e}")
    return results


def search_telegram_channels(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca en canales públicos de Telegram vía web"""
    results = []
    # Canales públicos conocidos
    channels = ["notivenezuelaarma", "elpetitvenezolano", "vzlanoticias"]
    for channel in channels:
        try:
            url = f"https://t.me/s/{channel}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                import re

                posts = re.findall(r'message.html">(.*?)</div>', resp.text, re.DOTALL)[:limit]
                for post in posts:
                    clean = re.sub(r"<[^>]+>", "", post)[:280]
                    if keyword.lower() in clean.lower():
                        results.append(
                            {
                                "title": clean[:150],
                                "summary": clean[:280],
                                "link": f"https://t.me/{channel}",
                                "published": datetime.now().isoformat(),
                                "source": f"Telegram @{channel}",
                                "type": "telegram",
                            }
                        )
        except Exception as e:
            print(f"[WARN] Telegram {channel}: {e}")
    return results


def search_reddit(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca en Reddit usando TLS Fingerprint Evasion"""
    results = []
    subreddits = ["vzla", "venezuela", "latinamerica"]
    proxies = None
    proxy_url = RESIDENTIAL_PROXY_URL or os.getenv("RESIDENTIAL_PROXY_URL")
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/search.json?q={keyword}&sort=new&limit={limit}"
            resp = tls_manager.request("GET", url, platform="search_social", proxies=proxies, timeout=10)

            data = None
            if resp is not None:
                if hasattr(resp, "json"):
                    try:
                        data = resp.json()
                    except Exception:
                        pass
                elif hasattr(resp, "text"):
                    import json
                    try:
                        data = json.loads(resp.text)
                    except Exception:
                        pass

            if not data:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
                r = requests.get(url, headers=headers, proxies=proxies, timeout=10)
                if r.status_code == 200:
                    data = r.json()

            if data and "data" in data and "children" in data["data"]:
                for post in data["data"]["children"][:limit]:
                    p = post.get("data", {})
                    results.append(
                        {
                            "title": p.get("title", "")[:150],
                            "summary": p.get("selftext", "")[:280] or f"r/{sub}",
                            "link": f"https://reddit.com{p.get('permalink', '')}",
                            "published": datetime.fromtimestamp(p.get("created_utc", 0)).isoformat(),
                            "source": f"Reddit r/{sub}",
                            "type": "reddit",
                        }
                    )
        except Exception as e:
            print(f"[WARN] Reddit r/{sub}: {e}")
    return results


def search_news_sites(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca en sitios de noticias"""
    results = []

    # URLs de búsqueda de cada sitio
    sites = {
        "El Nacional": "https://www.elnacional.com/?s={}",
        "Efecto Cocuyo": "https://efectococuyo.com/?s={}",
        "Tal Cual": "https://talcualdigital.com/?s={}",
        "Runrunes": "https://runrun.es/?s={}",
    }

    for site, url_template in sites.items():
        try:
            url = url_template.format(keyword)
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                import re

                titles = re.findall(r"<h2[^>]*>([^<]+)</h2>", resp.text, re.I)[:limit]
                for title in titles:
                    if title.strip():
                        results.append(
                            {
                                "title": title.strip()[:150],
                                "summary": f"Noticia sobre {keyword} en {site}",
                                "link": url,
                                "published": datetime.now().isoformat(),
                                "source": site,
                                "type": "news_site",
                            }
                        )
        except Exception as e:
            print(f"[WARN] {site}: {e}")
    return results


def search_social_multiplatform(keyword: str = None, limit_per_source: int = 5) -> Dict[str, Any]:
    """
    Búsqueda multiplataforma SIN credenciales
    Busca en: Google News, Bing, YouTube, Telegram, Reddit, sitios de noticias
    """
    if not keyword:
        keyword = SEARCH_KEYWORDS[0]

    now = datetime.now().isoformat()
    data = {"timestamp": now, "keyword": keyword, "sources": {}, "count": 0}

    # Ejecutar búsquedas en paralelo
    import concurrent.futures

    search_functions = [
        ("Google News", lambda: search_google_news(keyword, limit_per_source)),
        ("Bing News", lambda: search_bing_news(keyword, limit_per_source)),
        ("YouTube", lambda: search_youtube(keyword, limit_per_source)),
        ("Telegram", lambda: search_telegram_channels(keyword, limit_per_source)),
        ("Reddit", lambda: search_reddit(keyword, limit_per_source)),
        ("Sitios de Noticias", lambda: search_news_sites(keyword, limit_per_source)),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(func): name for name, func in search_functions}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results = future.result()
                if results:
                    data["sources"][name] = results
                    data["count"] += len(results)
            except Exception as e:
                print(f"[ERROR] {name}: {e}")

    if not data["sources"]:
        data["sources"]["info"] = [
            {
                "title": "Sin resultados",
                "summary": f"No se encontraron resultados para '{keyword}'",
                "link": "#",
                "published": now,
                "source": "Sistema",
            }
        ]

    return data


def get_trending_topics() -> List[str]:
    """Obtiene temas trending relacionados con Venezuela"""
    topics = [
        "Venezuela",
        "Maduro",
        "Dólar Venezuela",
        "Sanciones Venezuela",
        "Trump Venezuela",
        "China Venezuela",
        "Rusia Venezuela",
        "Petroleo Venezuela",
        "Oposición Venezuela",
        "Elecciones Venezuela",
    ]
    return topics


if __name__ == "__main__":
    print("=== Búsqueda multiplataforma SIN credenciales ===")
    keyword = "venezuela"
    data = search_social_multiplatform(keyword)
    print(f"Keyword: {keyword}")
    print(f"Total resultados: {data['count']}")
    for source, items in data["sources"].items():
        print(f"  {source}: {len(items)} items")
