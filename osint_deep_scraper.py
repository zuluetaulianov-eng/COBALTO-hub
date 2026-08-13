# osint_deep_scraper.py - Scraper Adaptativo y Extracción de APIs Ocultas
# Basado en el "Web Scraper Profesional" - Optimizado para Cobalto Hub 2026
# Soporta: requests + BS4, Playwright (fallback), Detección de APIs internas

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

import aiohttp
import fake_useragent
import tls_client
from bs4 import BeautifulSoup

from osint_playwright import fetch_rss_with_browser

# Configuración de logging
logger = logging.getLogger("DeepScraper")


class DeepScraper:
    """
    Scraper adaptativo que detecta APIs ocultas y extrae contenido limpio.
    Utiliza Playwright como fallback para sitios dinámicos.
    """

    def __init__(self):
        try:
            self.ua = fake_useragent.UserAgent()
        except Exception:
            self.ua = None

    def get_headers(self) -> Dict[str, str]:
        """Genera headers realistas."""
        user_agent = (
            self.ua.random
            if self.ua
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def detect_blocking(self, html: str) -> bool:
        """Detecta si el contenido indica un bloqueo (Cloudflare, Captcha, etc)."""
        indicators = ["captcha", "robot", "blocked", "cloudflare", "access denied", "403 forbidden", "429 too many"]
        return any(ind in html.lower() for ind in indicators)

    def extract_tables(self, html: str) -> List[List[Dict[str, str]]]:
        """Extrae todas las tablas de una página como lista de diccionarios."""
        soup = BeautifulSoup(html, "html.parser")
        all_tables = []
        for table in soup.find_all("table"):
            headers = [th.get_text().strip() for th in table.find_all("th")]
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text().strip() for td in tr.find_all("td")]
                if cells:
                    if headers and len(cells) == len(headers):
                        rows.append(dict(zip(headers, cells)))
                    else:
                        rows.append({"data": " | ".join(cells)})
            if rows:
                all_tables.append(rows)
        return all_tables

    async def extract_hidden_apis(self, url: str) -> Dict[str, List[str]]:
        """
        Analiza el contenido de una URL para encontrar endpoints de APIs,
        GraphQL o tokens de acceso ocultos en el código.
        """
        findings = {}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), timeout=15) as resp:
                    content = await resp.text()

            # Patrones inspirados en el Scraper Profesional
            patterns = {
                "api_endpoints": r'https?://[^"\']+(?:api|graphql|v\d+|rest)[^"\']*',
                "api_keys": r'["\']?(?:api[_-]key|access[_-]token|auth[_-]token)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                "js_endpoints": r'["\'](/[a-zA-Z0-9\-_/]*api/[^"\']*)["\']',
                "firebase_urls": r'https?://[^"\']+\.firebaseio\.com/[^"\']*',
                "s3_buckets": r'https?://[^"\']+\.s3\.amazonaws\.com/[^"\']*',
            }

            for key, pattern in patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    findings[key] = list(set(matches))[:20]  # Limitar a 20 por tipo

            return findings
        except Exception as e:
            logger.error(f"[DEEP SCAN] Error en {url}: {e}")
            return {}

    def extract_main_content(self, html: str) -> Dict[str, Any]:
        """
        Extrae el contenido principal eliminando basura (scripts, nav, footer).
        Inspirado en la técnica de 'AdaptiveScraper'.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Metadata
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name", tag.get("property", ""))
            if name:
                meta[name] = tag.get("content", "")

        # Limpieza agresiva de elementos no deseados
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]):
            element.decompose()

        # Extraer título y contenido
        title = soup.title.string if soup.title else ""
        content = soup.get_text(separator="\n", strip=True)

        # Extraer imágenes relevantes
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                images.append(src)

        return {
            "title": title,
            "content": content[:5000],  # Cap de 5000 chars
            "meta": meta,
            "images": list(set(images))[:10],
        }

    async def smart_scrape(self, url: str) -> Dict[str, Any]:
        """
        Estrategia adaptativa: Intenta aiohttp primero, si el contenido
        es escaso o bloqueado, usa Playwright.
        """
        logger.info(f"[SMART SCRAPE] Procesando: {url}")

        try:
            # 1. Intento estático
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), timeout=12) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        data = self.extract_main_content(html)

                        # Si tenemos contenido real, terminamos
                        if len(data["content"]) > 400:
                            data["method"] = "static"
                            return data

            # 2. Fallback ligero (tls_client) para evadir protecciones TLS sin Playwright
            logger.info(f"[SMART SCRAPE] Intentando tls_client para evadir bloqueos ligeros en {url}")
            try:
                def fetch_with_tls():
                    session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
                    return session.get(url, headers=self.get_headers(), timeout_seconds=12)

                tls_resp = await asyncio.to_thread(fetch_with_tls)
                if tls_resp.status_code == 200:
                    html = tls_resp.text
                    data = self.extract_main_content(html)
                    if len(data["content"]) > 400:
                        data["method"] = "tls_static"
                        return data
            except Exception as e:
                logger.debug(f"[SMART SCRAPE] tls_client falló: {e}")

            # 3. Fallback dinámico (Playwright) si lo anterior falló o fue bloqueado
            logger.info(f"[SMART SCRAPE] Contenido insuficiente. Usando Playwright para {url}")
            browser_data_bytes = await fetch_rss_with_browser(url)
            if browser_data_bytes:
                html = browser_data_bytes.decode("utf-8", errors="ignore")
                data = self.extract_main_content(html)
                data["method"] = "dynamic"
                return data

        except Exception as e:
            logger.error(f"[SMART SCRAPE] Error: {e}")

        return {"error": "No se pudo extraer contenido", "url": url}


# Instancia global para uso en otros módulos
scraper = DeepScraper()

if __name__ == "__main__":
    # Test rápido
    async def test():
        url = "https://www.elnacional.com"
        print(f"--- Escaneando APIs en {url} ---")
        apis = await scraper.extract_hidden_apis(url)
        print(json.dumps(apis, indent=2))

        print(f"\n--- Scraping Inteligente en {url} ---")
        res = await scraper.smart_scrape(url)
        print(f"Título: {res.get('title')}")
        print(f"Método: {res.get('method')}")
        print(f"Contenido (preview): {res.get('content', '')[:200]}...")

    asyncio.run(test())
