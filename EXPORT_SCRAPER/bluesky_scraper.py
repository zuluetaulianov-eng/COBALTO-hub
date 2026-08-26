"""
BLUESKY SCRAPER (Módulo Autónomo Exportable)
============================================
Extractor para la red social abierta Bluesky utilizando la API pública REST de AT Protocol.
No requiere credenciales ni inicio de sesión. Permite búsqueda por query/hashtag y perfiles.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

import aiohttp

logger = logging.getLogger("BlueskyScraper")

BSKY_PUBLIC_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
BSKY_PROFILE_API = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile"


async def fetch_bluesky_posts(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Busca publicaciones en Bluesky por término de búsqueda o hashtag."""
    results = []
    # Si no tiene # ni espacio, asumimos consulta normal o hashtag
    search_query = f"#{query}" if not query.startswith("#") and " " not in query else query
    params = {"q": search_query, "limit": limit, "sort": "latest"}
    headers = {"User-Agent": "BlueskyOSINTBot/1.0 (+https://github.com/cobalto)"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BSKY_PUBLIC_API, params=params, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for post in data.get("posts", [])[:limit]:
                        record = post.get("record", {})
                        author = post.get("author", {})
                        text = record.get("text", "").strip()
                        if not text:
                            continue

                        handle = author.get("handle", "bsky.app")
                        uri = post.get("uri", "")
                        post_id = uri.split("/")[-1] if uri else ""
                        post_url = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else f"https://bsky.app/profile/{handle}"
                        created_at = record.get("createdAt", datetime.now().isoformat())[:16].replace("T", " ")

                        results.append({
                            "title": text[:120] + ("..." if len(text) > 120 else ""),
                            "text": text,
                            "author_handle": handle,
                            "author_display_name": author.get("displayName", handle),
                            "avatar": author.get("avatar", ""),
                            "link": post_url,
                            "created_at": created_at,
                            "likes": post.get("likeCount", 0),
                            "reposts": post.get("repostCount", 0),
                            "source": f"Bluesky ({query})",
                        })
    except Exception as e:
        logger.error(f"[BLUESKY] Error al consultar API de Bluesky: {e}")

    return results


async def get_bluesky_profile(handle: str) -> Dict[str, Any]:
    """Obtiene información pública de perfil en Bluesky por su handle (ej: 'nytimes.com')."""
    params = {"actor": handle}
    headers = {"User-Agent": "BlueskyOSINTBot/1.0"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BSKY_PROFILE_API, params=params, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "handle": data.get("handle", handle),
                        "displayName": data.get("displayName", ""),
                        "description": data.get("description", ""),
                        "followersCount": data.get("followersCount", 0),
                        "followsCount": data.get("followsCount", 0),
                        "postsCount": data.get("postsCount", 0),
                        "avatar": data.get("avatar", ""),
                        "profile_url": f"https://bsky.app/profile/{handle}",
                    }
    except Exception as e:
        logger.error(f"[BLUESKY] Error al obtener perfil de {handle}: {e}")

    return {"handle": handle, "status": "ERROR"}


def fetch_bluesky_sync(query: str = "ciberseguridad", limit: int = 5) -> List[Dict[str, Any]]:
    """Ejecutor síncrono."""
    return asyncio.run(fetch_bluesky_posts(query, limit))
