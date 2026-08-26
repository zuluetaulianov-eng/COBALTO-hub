"""
MASTODON SCRAPER (Módulo Autónomo Exportable)
=============================================
Extractor para la red social federada Mastodon.
Consulta múltiples instancias (mastodon.social, fosstodon.org, infosec.exchange)
mediante la API pública REST sin necesidad de autenticación.
"""

import asyncio
import html
import logging
import re
from typing import Any, Dict, List

import aiohttp

logger = logging.getLogger("MastodonScraper")

MASTODON_INSTANCES = [
    "https://mastodon.social",
    "https://fosstodon.org",
    "https://infosec.exchange",
]


def clean_mastodon_html(html_text: str) -> str:
    """Limpia etiquetas HTML, artefactos de listas y rastros de IA de las publicaciones de Mastodon."""
    if not html_text:
        return ""
    text = html.unescape(html_text)
    text = re.sub(r"<(br|p|div|/p|/div)[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?i)<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"(?i)here'?s\s+a\s+thinking\s+process:?", "", text)
    text = re.sub(r"(?i)thinking\s+process:?", "", text)
    text = re.sub(r"^\s*\[?\s*(?:['\"][^'\"]*['\"]\s*,\s*)*['\"][^'\"]*['\"]\s*\]\s*", "", text)
    text = re.sub(r"^\s*['\"][^'\"]*['\"]\s*,\s*['\"][^'\"]*['\"]\s*\]\s*", "", text)
    text = re.sub(r"^\s*['\"\]\)]+\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


async def fetch_mastodon_hashtag(hashtag: str, max_items: int = 6) -> List[Dict[str, Any]]:
    """Extrae publicaciones recientes por hashtag consultando instancias federadas."""
    results = []
    headers = {"User-Agent": "MastodonOSINTBot/1.0 (+https://github.com/cobalto)"}

    for instance in MASTODON_INSTANCES:
        try:
            url = f"{instance}/api/v1/timelines/tag/{hashtag}"
            params = {"limit": max_items}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        posts = await resp.json()
                        if isinstance(posts, list):
                            for post in posts[:max_items]:
                                raw_content = post.get("content", "")
                                text = clean_mastodon_html(raw_content)
                                if not text:
                                    continue

                                account = post.get("account", {})
                                acct = account.get("acct", "anónimo")
                                published = (post.get("created_at") or "Reciente")[:16].replace("T", " ")
                                media = post.get("media_attachments", [])
                                image_url = media[0].get("preview_url") if media else None

                                results.append({
                                    "title": text[:120] + ("..." if len(text) > 120 else ""),
                                    "content": text,
                                    "author": acct,
                                    "author_display_name": account.get("display_name", acct),
                                    "link": post.get("url") or f"{instance}/@{acct}",
                                    "published": published,
                                    "image": image_url,
                                    "instance": instance,
                                    "source": f"Mastodon #{hashtag}",
                                })
                            if results:
                                return results
        except Exception as e:
            logger.warning(f"[MASTODON] Error al consultar {instance}: {e}")

    return results


def fetch_mastodon_sync(hashtag: str = "infosec", limit: int = 5) -> List[Dict[str, Any]]:
    """Ejecutor síncrono."""
    return asyncio.run(fetch_mastodon_hashtag(hashtag, limit))
