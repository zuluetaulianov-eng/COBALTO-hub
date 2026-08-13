# osint_social_dorks.py - Búsquedas especializadas en redes sociales v2.0
# Parser ultra-liviano y resiliente sin Playwright para DuckDuckGo Lite.

import logging
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from social_public_extractor import safe_get

# ── Dorks Avanzados (Búsquedas especializadas en redes sociales) ──
DORK_QUERIES = {
    "Twitter/X - Alertas": "site:x.com venezuela (alerta OR urgente OR última)",
    "Facebook - Reportes": "site:facebook.com venezuela (apagón OR protesta OR denuncia)",
    "Instagram - Visuales": "site:instagram.com venezuela (protesta OR manifestación)",
    "TikTok - Tendencias": "site:tiktok.com venezuela (urgente OR noticia)",
}


def execute_google_dork(dork_name: str, query: str) -> List[Dict[str, Any]]:
    """Ejecuta una búsqueda en DuckDuckGo Lite (HTML) usando safe_get para evadir bloqueos y captchas."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    results = []
    try:
        logging.info(f"[DORKS] Extrayendo via DDG-Lite y safe_get: {dork_name}")
        resp = safe_get(url, timeout=15)

        if resp is None or resp.status_code != 200:
            logging.warning(f"[DORKS] HTTP {getattr(resp, 'status_code', 'N/A')} para {dork_name}")
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        search_blocks = soup.select(".result__body")

        if not search_blocks:
            logging.warning(
                f"[DORKS] No se hallaron resultados en DDG-Lite para {dork_name} (posible bloqueo o sin resultados)"
            )
            return []

        for block in search_blocks[:4]:
            title_el = block.select_one(".result__a")
            title = title_el.get_text(strip=True) if title_el else ""
            link = title_el.get("href") if title_el else ""

            snippet_el = block.select_one(".result__snippet")
            summary = snippet_el.get_text(strip=True) if snippet_el else "Sin descripción"

            if title and link:
                results.append(
                    {
                        "title": title,
                        "summary": summary.replace("\n", " ")[:280],
                        "link": link,
                        "published": datetime.now().isoformat(),
                        "source": f"🔍 Dork: {dork_name}",
                        "type": "social_dork",
                    }
                )

    except Exception as e:
        logging.warning(f"[DORKS] Falla en {dork_name}: {e}")

    return results


async def get_social_dorks_intel() -> List[Dict[str, Any]]:
    """Mantiene la interfaz asíncrona original pero usa el parser optimizado en hilos para evitar bloqueos."""
    import asyncio

    all_results = []
    for name, query in DORK_QUERIES.items():
        items = await asyncio.to_thread(execute_google_dork, name, query)
        all_results.extend(items)
        await asyncio.sleep(1.0)
    return all_results


def get_social_dorks_sync() -> Dict[str, Any]:
    """Función síncrona optimizada para el Dashboard (ejecutada en ThreadPoolExecutor)."""
    all_results = []
    for name, query in DORK_QUERIES.items():
        items = execute_google_dork(name, query)
        all_results.extend(items)
        import time

        time.sleep(1.0)
    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {"Búsquedas Sociales Avanzadas": all_results},
        "count": len(all_results),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Iniciando infiltracion Dorking en Redes Sociales (Parser optimizado)...")
    res = get_social_dorks_sync()
    for item in res["sources"].get("Búsquedas Sociales Avanzadas", []):
        try:
            print(f"[{item['source']}] {item['title'][:60]}...")
        except UnicodeEncodeError:
            clean_source = item["source"].encode("ascii", "ignore").decode("ascii")
            clean_title = item["title"][:60].encode("ascii", "ignore").decode("ascii")
            print(f"[{clean_source}] {clean_title}...")
