"""
finint_darkweb.py — Dark Web intelligence module.
Scrapes .onion sites, monitors paste sites and leak marketplaces.
Uses Tor SOCKS proxy if configured.
"""
import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Known paste/leak monitoring endpoints
LEAK_SOURCES = [
    {
        "name": "Pastebin",
        "url": "https://psbdmp.ws/api/search/{query}",
        "type": "paste",
        "enabled": True,
    },
    {
        "name": "LeakCheck",
        "url": "https://leakcheck.io/api/public?query={query}",
        "type": "leak",
        "enabled": False,  # requires API key
    },
]

# Known .onion markets/forums to monitor (example URLs)
ONION_TARGETS = [
    {"name": "Example Market", "url": "http://examplemarket.onion", "type": "marketplace", "enabled": False},
]

# Regex patterns for finding crypto addresses in text
CRYPTO_PATTERNS = {
    "btc": re.compile(r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b"),
    "eth": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "tron": re.compile(r"\bT[A-Za-z1-9]{33}\b"),
    "solana": re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"),
    "monero": re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b"),
}


def _tor_session() -> Dict:
    """Return proxy settings for Tor if configured."""
    tor_port = os.environ.get("TOR_SOCKS_PORT", "9050")
    use_tor = os.environ.get("USE_TOR_FALLBACK", "").lower() in ("true", "1", "yes")
    if use_tor:
        return {
            "proxy": f"socks5://127.0.0.1:{tor_port}",
            "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"},
        }
    return {}


async def monitor_paste_sites(query: str = "", limit: int = 20) -> List[Dict]:
    """Search paste sites for mentions of a query (domain, wallet, keyword)."""
    results = []
    if not query:
        return results

    for source in LEAK_SOURCES:
        if not source["enabled"]:
            continue
        try:
            url = source["url"].format(query=query)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=20, **_tor_session()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data if isinstance(data, list) else data.get("data", [])
                        for item in items[:limit]:
                            results.append({
                                "source": source["name"],
                                "type": source["type"],
                                "title": item.get("title", item.get("id", "Untitled")),
                                "content": item.get("content", item.get("raw", ""))[:500],
                                "url": item.get("url", ""),
                                "found_at": datetime.now().isoformat(),
                                "crypto_addresses": _extract_crypto(item.get("content", "")),
                            })
        except Exception as e:
            logger.debug(f"[DARKWEB] {source['name']} query failed: {e}")
        await asyncio.sleep(1)

    return results


async def scrape_onion_site(url: str, timeout: int = 30) -> Optional[Dict]:
    """Scrape a single .onion site via Tor proxy."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout, **_tor_session()) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return {
                        "url": url,
                        "status": resp.status,
                        "title": _extract_title(text),
                        "crypto_addresses": _extract_crypto(text),
                        "content_length": len(text),
                        "scraped_at": datetime.now().isoformat(),
                    }
    except Exception as e:
        logger.debug(f"[DARKWEB] Onion scrape failed {url}: {e}")
    return None


async def monitor_onion_targets() -> List[Dict]:
    """Scrape all configured .onion targets."""
    results = []
    for target in ONION_TARGETS:
        if not target["enabled"]:
            continue
        result = await scrape_onion_site(target["url"])
        if result:
            result["name"] = target["name"]
            result["type"] = target["type"]
            results.append(result)
        await asyncio.sleep(2)
    return results


def analyze_text_for_finint(text: str) -> Dict:
    """Scan raw text for financial intelligence indicators."""
    return {
        "crypto_addresses": _extract_crypto(text),
        "has_sanction_keywords": _check_sanction_keywords(text),
        "suspicious_patterns": _find_suspicious_patterns(text),
    }


def _extract_crypto(text: str) -> Dict[str, List[str]]:
    """Extract cryptocurrency addresses from text."""
    found = {}
    for currency, pattern in CRYPTO_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            found[currency] = list(set(matches))
    return found


def _extract_title(html: str) -> str:
    """Extract <title> from HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _check_sanction_keywords(text: str) -> List[str]:
    """Check text for sanction-related keywords."""
    keywords = ["sanction", "ofac", "sdn", "embargo", "blocked", "prohibited",
                "sanción", "sancionado", "lista negra", "congelado"]
    found = []
    lower = text.lower()
    for kw in keywords:
        if kw in lower:
            found.append(kw)
    return found


def _find_suspicious_patterns(text: str) -> List[str]:
    """Find suspicious patterns indicative of illicit activity."""
    patterns = []
    if re.search(r"\b(?:pass|pwd|password|login|email|@)\b[\s:]+\S+", text, re.IGNORECASE):
        patterns.append("credential_leak")
    if re.search(r"\b(?:dumps|cc|cvv|fullz|ssn|d.o.b)\b", text, re.IGNORECASE):
        patterns.append("financial_fraud")
    if re.search(r"\b(?:ransomware|malware|exploit|0day|backdoor)\b", text, re.IGNORECASE):
        patterns.append("cyber_threat")
    return patterns
