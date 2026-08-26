"""
LINKEDIN SCRAPER (Módulo Autónomo Exportable)
==============================================
Extractor OSINT para perfiles de usuario, empresas e inteligencia corporativa en LinkedIn.
Utiliza dorking inteligente mediante DuckDuckGo Lite HTML sin requerir credenciales de sesión.
"""

import asyncio
import logging
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("LinkedInScraper")


def extract_linkedin_profile_metadata(text: str, link: str) -> Dict[str, Any]:
    """Extrae nombre, cargo e institución a partir del snippet de LinkedIn."""
    username_match = re.search(r"linkedin\.com/in/([a-zA-Z0-9_-]+)", link)
    company_match = re.search(r"linkedin\.com/company/([a-zA-Z0-9_-]+)", link)

    target_type = "profile" if username_match else "company" if company_match else "general"
    identifier = username_match.group(1) if username_match else company_match.group(1) if company_match else "unknown"

    return {
        "identifier": identifier,
        "target_type": target_type,
        "url": link,
        "raw_snippet": text,
    }


async def search_linkedin_dork(query: str, search_type: str = "profile", limit: int = 8) -> List[Dict[str, Any]]:
    """Ejecuta una búsqueda dork en LinkedIn (site:linkedin.com/in u site:linkedin.com/company)."""
    site_prefix = "site:linkedin.com/in/" if search_type == "profile" else "site:linkedin.com/company/"
    full_query = f"{site_prefix} {query}"
    encoded_query = urllib.parse.quote(full_query)
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }

    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ddg_url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    html_text = await resp.text()
                    soup = BeautifulSoup(html_text, "html.parser")
                    blocks = soup.select(".result__body")

                    for block in blocks[:limit]:
                        title_el = block.select_one(".result__a")
                        snippet_el = block.select_one(".result__snippet")

                        title = title_el.get_text(strip=True) if title_el else ""
                        link = title_el.get("href") if title_el else ""
                        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                        if "linkedin.com" in link:
                            # Limpieza de URL redirigida por DDG si aplica
                            if "uddg=" in link:
                                match = re.search(r"uddg=([^&]+)", link)
                                if match:
                                    link = urllib.parse.unquote(match.group(1))

                            meta = extract_linkedin_profile_metadata(snippet, link)
                            results.append({
                                "title": title.replace(" | LinkedIn", "").replace(" - LinkedIn", ""),
                                "link": link,
                                "snippet": snippet,
                                "metadata": meta,
                                "scraped_at": datetime.now().isoformat(),
                                "source": f"LinkedIn OSINT ({search_type})",
                            })
    except Exception as e:
        logger.error(f"[LINKEDIN] Error al ejecutar dork: {e}")

    return results


def search_linkedin_sync(query: str, search_type: str = "profile", limit: int = 5) -> List[Dict[str, Any]]:
    """Ejecutor síncrono."""
    return asyncio.run(search_linkedin_dork(query, search_type, limit))
