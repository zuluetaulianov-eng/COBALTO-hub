# social_extras.py - Fuentes adicionales ESPECIALIZADAS
# Wikipedia, GitHub, OSINT, ciberseguridad y más

from datetime import datetime
from typing import Any, Dict, List

import feedparser
import requests

from social_public_extractor import safe_get  # Tor + fallback anti-censura

# ==========================================
# WIKIPEDIA - Cambios recientes en artículos de Venezuela
# ==========================================
WIKIPEDIA_WATCHLIST = [
    "Venezuela",
    "Nicolás_Maduro",
    "Historia_de_Venezuela",
    "Economía_de_Venezuela",
    "Política_de_Venezuela",
    "Crisis_política_en_Venezuela",
    "Sanciones_a_Venezuela",
    "Relaciones_internacionales_de_Venezuela",
    "Petróleos_de_Venezuela",
    "FARC",
]


def get_wikipedia_changes() -> List[Dict[str, Any]]:
    """Extrae cambios recientes de Wikipedia Venezuela"""
    results = []
    try:
        # API de cambios recientes de Wikipedia
        url = "https://en.wikipedia.org/w/api.php"
        {
            "action": "query",
            "list": "recentchanges",
            "rcnamespace": 0,
            "rclimit": 20,
            "rcprop": "title|timestamp|user|comment",
            "format": "json",
            "rcstart": datetime.now().isoformat(),
        }
        resp = safe_get(url)
        if resp.status_code == 200:
            data = resp.json()
            for change in data.get("query", {}).get("recentchanges", []):
                title = change.get("title", "")
                if "venezuela" in title.lower() or "maduro" in title.lower():
                    results.append(
                        {
                            "title": f"Wiki: {title}",
                            "summary": change.get("comment", "Sin descripción")[:200],
                            "link": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                            "published": change.get("timestamp", ""),
                            "source": "Wikipedia Changes",
                            "type": "wikipedia",
                        }
                    )
    except Exception as e:
        print(f"[WARN] Wikipedia: {e}")
    return results


# ==========================================
# GITHUB - Proyectos trending de Venezuela/desarrolladores
# ==========================================
def get_github_venezuela() -> List[Dict[str, Any]]:
    """Busca repositorios relacionados con Venezuela o de desarrolladores venezolanos"""
    results = []
    try:
        # Buscar repositorios con "venezuela" en descripción
        url = "https://api.github.com/search/repositories"
        params = {"q": "venezuela created:>2023-01-01", "sort": "stars", "per_page": 10}
        headers = {"Accept": "application/vnd.github.v3+json"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for repo in data.get("items", [])[:8]:
                results.append(
                    {
                        "title": f"GitHub: {repo.get('full_name', '')}",
                        "summary": repo.get("description", "")[:200],
                        "link": repo.get("html_url", "#"),
                        "published": repo.get("created_at", ""),
                        "source": f"GitHub ({repo.get('language', 'N/A')})",
                        "type": "github",
                    }
                )
    except Exception as e:
        print(f"[WARN] GitHub: {e}")
    return results


def get_github_trending() -> List[Dict[str, Any]]:
    """GitHub trending en español/inglés"""
    results = []
    try:
        url = "https://api.github.com/search/repositories"
        params = {"q": "language:python OR language:javascript OR language:go", "sort": "stars", "per_page": 10}
        headers = {"Accept": "application/vnd.github.v3+json"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for repo in data.get("items", [])[:5]:
                results.append(
                    {
                        "title": f"Trending: {repo.get('full_name', '')}",
                        "summary": repo.get("description", "")[:200],
                        "link": repo.get("html_url", "#"),
                        "published": repo.get("updated_at", ""),
                        "source": f"GitHub Trending ({repo.get('language', 'N/A')})",
                        "type": "github_trending",
                    }
                )
    except Exception as e:
        print(f"[WARN] GitHub Trending: {e}")
    return results


# ==========================================
# REDDIT - Más subreddits
# ==========================================
REDDIT_EXTRA_SUBREDDITS = [
    "vzla",
    "venezuela",
    "LatinAmerica",
    "southamerica",
    "caracas",
    "worldnews",
    "news",
    "technology",
    "cybersecurity",
    "hacking",
    "opensource",
    "programming",
    "python",
    "javascript",
    "LibertadYA",
    "TheRighteous",
    "es点左右",
]


def get_reddit_extra() -> List[Dict[str, Any]]:
    """Extrae de más subreddits"""
    results = []
    for sub in REDDIT_EXTRA_SUBREDDITS[:10]:
        try:
            url = f"https://redlib.catsarch.com/r/{sub}/rss"
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for post in feed.entries[:3]:
                results.append(
                    {
                        "title": post.get("title", "")[:140],
                        "summary": post.get("summary", "")[:200] or f"r/{sub}",
                        "link": post.get("link", "#").replace("redlib.catsarch.com", "reddit.com"),
                        "published": post.get("published", ""),
                        "source": f"Reddit r/{sub}",
                        "type": "reddit_extra",
                    }
                )
        except Exception as e:
            print(f"[WARN] Reddit r/{sub}: {e}")
    return results


# ==========================================
# FUENTES DE OSINT Y CIBERSEGURIDAD
# ==========================================
OSINT_SOURCES = {
    "SANS Internet Storm Center": "https://isc.sans.edu/rssfeed.xml",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "Bleeping Computer": "https://www.bleepingcomputer.com/feed/",
    "Dark Reading": "https://www.darkreading.com/rss.xml",
    "Schneier on Security": "https://www.schneier.com/feed/",
}


def get_osint_sources() -> List[Dict[str, Any]]:
    """Extrae de fuentes de ciberseguridad y OSINT"""
    results = []
    for name, url in OSINT_SOURCES.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "osint",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# HACKERONE Y BUGBOUNTY
# ==========================================
def get_bugbounty_reports() -> List[Dict[str, Any]]:
    """Busca reportes de bug bounty públicos"""
    results = []
    try:
        # HackerOne hacktivity (público)
        url = "https://api.hackerone.com/v1/hacktivity"
        requests.get(url, timeout=10)
        # No funciona sin auth, usamos alternativa
        results.append(
            {
                "title": "Bug Bounty - Buscar en HackerOne manualmente",
                "summary": "Explora programas de bug bounty en hackerone.com",
                "link": "https://hackerone.com/bug-bounty-programs",
                "published": datetime.now().isoformat(),
                "source": "HackerOne",
                "type": "bugbounty",
            }
        )
    except Exception as e:
        print(f"[WARN] BugBounty: {e}")
    return results


# ==========================================
# STACKOVERFLOW Y COMUNIDADES DE DESARROLLADORES
# ==========================================
STACKOVERFLOW_TAGS = ["venezuela", "caracas", "python", "javascript", "sql"]


def get_stackoverflow() -> List[Dict[str, Any]]:
    """Busca preguntas en StackOverflow"""
    results = []
    for tag in STACKOVERFLOW_TAGS[:3]:
        try:
            url = "https://api.stackexchange.com/2.3/questions"
            params = {"order": "desc", "sort": "activity", "tagged": tag, "site": "stackoverflow", "pagesize": 5}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for q in data.get("items", []):
                    results.append(
                        {
                            "title": f"SO: {q.get('title', '')[:140]}",
                            "summary": f"Tags: {', '.join(q.get('tags', []))[:200]}",
                            "link": q.get("link", "#"),
                            "published": datetime.fromtimestamp(q.get("creation_date", 0)).isoformat(),
                            "source": "StackOverflow",
                            "type": "stackoverflow",
                        }
                    )
        except Exception as e:
            print(f"[WARN] StackOverflow {tag}: {e}")
    return results


# ==========================================
# DARK WEB Y MONITOREO (onion links públicos)
# ==========================================
DARK_WEB_SOURCES = {
    "Dark.fail (Directorio onion)": "https://dark.fail/api/onions",
}


def get_dark_web() -> List[Dict[str, Any]]:
    """Enlaces a recursos onion públicos (no contenido ilegal)"""
    results = []
    # Solo devolvemos info, no scrapeamos dark web
    results.append(
        {
            "title": "Recursos Dark Web - Lista pública",
            "summary": "Nota: No scraping de contenido ilegal. Solo monitoreo de fuentes legales.",
            "link": "#",
            "published": datetime.now().isoformat(),
            "source": "Info - Dark Web",
            "type": "darkweb_info",
        }
    )
    return results


# ==========================================
# HACKERNOON, MEDIUM Y BLOGS TÉCNICOS
# ==========================================
TECH_BLOGS = {
    "Hacker Noon": "https://hackernoon.com/feed",
    "Dev.to Venezuela": "https://dev.to/feed",
    "Medium Venezuela": "https://medium.com/feed/tagged/Venezuela",
    "Codementor": "https://www.codementor.io/blog/feed",
}


def get_tech_blogs() -> List[Dict[str, Any]]:
    """Extrae de blogs técnicos"""
    results = []
    for name, url in TECH_BLOGS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "tech_blog",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# EVENTOS Y CONFERENCIAS
# ==========================================
EVENT_SOURCES = {
    "LACNIC": "https://www.lacnic.net/rss.xml",
    "ICANN": "https://www.icann.org/news/rss-feed.xml",
    "IETF": "https://www.ietf.org/rss/ietf-announce.xml",
}


def get_events() -> List[Dict[str, Any]]:
    """Extrae de fuentes de eventos tecnológicos"""
    results = []
    for name, url in EVENT_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "event",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# UNIFICAR TODAS LAS FUENTES ESPECIALES
# ==========================================
def get_special_sources() -> Dict[str, Any]:
    """Recolecta todas las fuentes especiales"""
    import concurrent.futures

    now = datetime.now().isoformat()
    data = {"timestamp": now, "sources": {}, "count": 0}

    sources_funcs = [
        ("Wikipedia Cambios", get_wikipedia_changes),
        ("GitHub Venezuela", get_github_venezuela),
        ("GitHub Trending", get_github_trending),
        ("Reddit Extra", get_reddit_extra),
        ("OSINT & Ciberseguridad", get_osint_sources),
        ("Tech Blogs", get_tech_blogs),
        ("StackOverflow", get_stackoverflow),
        ("Eventos Tech", get_events),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
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
    print("=== Fuentes especiales SIN credenciales ===")
    data = get_special_sources()
    print(f"Total: {data['count']} items")
    for source, items in data["sources"].items():
        print(f"  {source}: {len(items)} items")
