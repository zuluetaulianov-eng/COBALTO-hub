"""
DARK WEB & PASTE SITES SCRAPER (Módulo Autónomo Exportable)
=========================================================
Monitoreo de sitios de filtrados (Pastebin / leaks) y páginas .onion en la Dark Web.
Soporta proxy Tor SOCKS5, detección de billeteras cripto (BTC, ETH, TRON, SOL, XMR)
y análisis sintáctico de credenciales filtradas y sanciones (OFAC).
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("DarkWebScraper")

# Patrones Regex para Criptomonedas
CRYPTO_PATTERNS = {
    "btc": re.compile(r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b"),
    "eth": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "tron": re.compile(r"\bT[A-Za-z1-9]{33}\b"),
    "solana": re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"),
    "monero": re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b"),
}

PASTE_SOURCES = [
    {
        "name": "PasteDump Public API",
        "url": "https://psbdmp.ws/api/search/{query}",
        "enabled": True,
    }
]


def extract_crypto_wallets(text: str) -> Dict[str, List[str]]:
    """Extrae direcciones de criptomonedas encontradas en el texto."""
    found = {}
    for coin, pattern in CRYPTO_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            found[coin] = list(set(matches))
    return found


def analyze_leak_text(text: str) -> Dict[str, Any]:
    """Analiza texto crudo en busca de filtraciones de credenciales y palabras clave de sanciones."""
    patterns = []
    if re.search(r"\b(?:pass|pwd|password|login|email|@)\b[\s:]+\S+", text, re.IGNORECASE):
        patterns.append("credential_leak")
    if re.search(r"\b(?:dumps|cc|cvv|fullz|ssn|d\.o\.b)\b", text, re.IGNORECASE):
        patterns.append("financial_fraud")
    if re.search(r"\b(?:ransomware|malware|exploit|0day|backdoor)\b", text, re.IGNORECASE):
        patterns.append("cyber_threat")

    sanction_keywords = ["sanction", "ofac", "sdn", "embargo", "sancion", "sancionado", "lista negra"]
    lower = text.lower()
    found_sanctions = [kw for kw in sanction_keywords if kw in lower]

    return {
        "crypto_wallets": extract_crypto_wallets(text),
        "threat_indicators": patterns,
        "sanction_keywords": found_sanctions,
    }


async def search_paste_sites(query: str, limit: int = 10, tor_proxy: Optional[str] = None) -> List[Dict[str, Any]]:
    """Busca menciones de palabras clave, correos o dominios en sitios Paste/Leak."""
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Bot/1.0"}
    proxy = tor_proxy or os.environ.get("TOR_SOCKS_PROXY", None)

    for source in PASTE_SOURCES:
        if not source["enabled"]:
            continue
        try:
            url = source["url"].format(query=query)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, proxy=proxy, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data if isinstance(data, list) else data.get("data", [])
                        for item in items[:limit]:
                            raw_content = item.get("content", item.get("raw", ""))
                            results.append({
                                "source": source["name"],
                                "title": item.get("title", item.get("id", "Untitled Paste")),
                                "url": item.get("url", f"https://pastebin.com/{item.get('id', '')}"),
                                "snippet": raw_content[:300],
                                "finint_analysis": analyze_leak_text(raw_content),
                                "scraped_at": datetime.now().isoformat(),
                            })
        except Exception as e:
            logger.warning(f"[DARKWEB] Fallo en {source['name']}: {e}")

    return results


async def scrape_onion_url(onion_url: str, tor_socks_port: int = 9050) -> Dict[str, Any]:
    """Scrapea un sitio .onion de la Dark Web utilizando proxy SOCKS5 de Tor."""
    proxy = f"socks5://127.0.0.1:{tor_socks_port}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(onion_url, proxy=proxy, headers=headers, timeout=25) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
                    title = title_match.group(1).strip() if title_match else "Darkweb Page"
                    return {
                        "onion_url": onion_url,
                        "status": resp.status,
                        "title": title,
                        "finint_analysis": analyze_leak_text(text),
                        "content_length": len(text),
                        "scraped_at": datetime.now().isoformat(),
                    }
    except Exception as e:
        return {"onion_url": onion_url, "status": "ERROR", "error": str(e)}

    return {"onion_url": onion_url, "status": "FAILED"}
