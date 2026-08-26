"""
HACKER NEWS SCRAPER (Módulo Autónomo Exportable)
================================================
Scraper para Hacker News utilizando HNRSS y la API REST pública de Algolia.
Extrae historias populares, noticias recientes por palabra clave y discusiones de ciberseguridad.
SIN NECESIDAD DE CLAVES DE API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import feedparser

logger = logging.getLogger("HackerNewsScraper")

HNRSS_URL = "https://hnrss.org/frontpage"
ALGOLIA_HN_API = "https://hn.algolia.com/api/v1/search_by_date"


async def fetch_hn_top_rss(limit: int = 10) -> List[Dict[str, Any]]:
    """Extrae las historias principales del feed HNRSS."""
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HNRSS_URL, timeout=12) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    feed = feedparser.parse(content)
                    for entry in feed.entries[:limit]:
                        results.append({
                            "title": entry.get("title", "Sin título"),
                            "link": entry.get("link", "#"),
                            "comments_url": entry.get("comments", entry.get("link", "")),
                            "published": entry.get("published", datetime.now().isoformat()),
                            "source": "Hacker News RSS",
                            "type": "news",
                        })
    except Exception as e:
        logger.error(f"[HN] Error al consultar HNRSS: {e}")
    return results


async def search_hn_algolia(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Busca historias en Hacker News por palabra clave vía API de Algolia."""
    results = []
    try:
        params = {"query": query, "tags": "story", "hitsPerPage": limit}
        async with aiohttp.ClientSession() as session:
            async with session.get(ALGOLIA_HN_API, params=params, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for hit in data.get("hits", []):
                        story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                        results.append({
                            "title": hit.get("title", "Sin título"),
                            "link": story_url,
                            "points": hit.get("points", 0),
                            "author": hit.get("author", "Anónimo"),
                            "num_comments": hit.get("num_comments", 0),
                            "created_at": hit.get("created_at", ""),
                            "hn_item_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                            "source": f"Hacker News Search ({query})",
                        })
    except Exception as e:
        logger.error(f"[HN] Error al consultar Algolia HN API: {e}")
    return results


def search_hn_sync(query: str = "cybersecurity", limit: int = 5) -> List[Dict[str, Any]]:
    """Ejecutor síncrono para scripts estándar."""
    return asyncio.run(search_hn_algolia(query, limit))
