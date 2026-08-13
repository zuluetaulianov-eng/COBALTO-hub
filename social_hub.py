# social_hub.py - Centro Unificado de Inteligencia Social (Cobalto Hub 2026)
# Consolidación de: social_extractor, social_extractor_v2, social_public_extractor, social_data
# Enfoque: Eficiencia, deduplicación y resiliencia ante censura.

import hashlib
import json
import logging
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from lxml_html_clean import Cleaner

from osint_deep_scraper import scraper
from tiktok_extractor import get_tiktok_all, get_tiktok_profiles

logger = logging.getLogger(__name__)

# ── Configuración y Carga de Entorno ──────────────────────────────
load_dotenv()

# ── Utilidades de Limpieza ────────────────────────────────────────
cleaner = Cleaner(
    allow_tags=["p", "br", "strong", "em", "a", "b", "i"],
    safe_attrs=["href", "title"],
    scripts=False,
    javascript=False,
    comments=False,
    frames=False,
    forms=False,
    annoying_tags=True,
)


def clean_html(html_content: str) -> str:
    """Limpia HTML y devuelve texto plano o formateado seguro."""
    if not html_content:
        return ""
    try:
        cleaned = cleaner.clean(html_content)
        return BeautifulSoup(cleaned, "html.parser").get_text()[:300]
    except Exception:
        return html_content[:300]


# ── Gestión de Conexión (Tor + Fallback) ──────────────────────────
TOR_BLOCKS = ["t.me", "telegram.org", "reddit.com", "facebook.com", "instagram.com", "tiktok.com"]

_session = requests.Session()
_session.headers.update(scraper.get_headers())


def safe_get(url: str, timeout: int = 12) -> Optional[requests.Response]:
    """Conexión inteligente usando sesión reutilizable y Tor."""
    domain = url.split("/")[2] if "://" in url else url

    if any(b in domain for b in TOR_BLOCKS):
        try:
            return _session.get(url, timeout=timeout)
        except Exception:
            return None

    tor_port = None
    for port in [9150, 9050]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    tor_port = port
            finally:
                sock.close()
            if tor_port:
                break
        except Exception:
            continue

    if tor_port:
        proxies = {"http": f"socks5h://127.0.0.1:{tor_port}", "https": f"socks5h://127.0.0.1:{tor_port}"}
        try:
            return _session.get(url, proxies=proxies, timeout=timeout + 5)
        except Exception:
            pass

    try:
        return _session.get(url, timeout=timeout)
    except Exception:
        return None


# ── Deduplicación Centralizada (thread-safe) ────────────────────
_SEEN_HASHES = set()
_SEEN_HASHES_LOCK = threading.Lock()


def is_duplicate(item: Dict) -> bool:
    """Verifica si el contenido ya fue procesado en la ejecución actual."""
    content = f"{item.get('title', '')}|{item.get('link', '')}".lower().strip()
    h = hashlib.md5(content.encode()).hexdigest()
    with _SEEN_HASHES_LOCK:
        if h in _SEEN_HASHES:
            return True
        _SEEN_HASHES.add(h)
        return False


# ── Extractores: Scrapers Públicos (v3) ──────────────────────────
NITTER_INSTANCES = ["https://nitter.net", "https://nitter.privacydev.net", "https://twitt.re"]


def fetch_rss(name: str, url: str, max_items: int = 5) -> List[Dict]:
    """Extrae feeds RSS estándar."""
    resp = safe_get(url)
    if not resp or not resp.content:
        return []
    feed = feedparser.parse(resp.content)
    results = []
    for entry in feed.entries[:max_items]:
        item = {
            "title": getattr(entry, "title", "Sin título")[:140],
            "summary": clean_html(getattr(entry, "summary", "") or getattr(entry, "description", "")),
            "link": getattr(entry, "link", "#"),
            "published": getattr(entry, "published", "Reciente"),
            "source": name,
            "image": entry.media_content[0].get("url")
            if hasattr(entry, "media_content") and entry.media_content
            else None,
        }
        if not is_duplicate(item):
            results.append(item)
    return results


def fetch_nitter(hashtag: str) -> List[Dict]:
    """Scrapea Twitter vía Nitter usando estrategia adaptativa."""
    for base in NITTER_INSTANCES:
        url = f"{base}/search?q=%23{hashtag}&f=recent"
        # Usar la lógica síncrona de smart_scrape si es posible, o una versión simplificada
        resp = safe_get(url)
        if resp and resp.status_code == 200:
            # ... lógica de BS4 ...
            soup = BeautifulSoup(resp.content, "html.parser")
            posts = soup.select(".timeline-item")[:5]
            results = []
            for p in posts:
                try:
                    txt = p.select_one(".tweet-content").get_text().strip()
                    item = {
                        "title": txt[:140],
                        "summary": txt,
                        "link": p.select_one(".tweet-link").get("href", "#"),
                        "published": "Reciente",
                        "source": f"X #{hashtag}",
                    }
                    if not is_duplicate(item):
                        results.append(item)
                except Exception:
                    continue
            if results:
                return results
    return []


# ── Extractores: APIs con Credenciales ───────────────────────────
def fetch_reddit_auth() -> List[Dict]:
    """Extrae de Reddit usando PRAW si hay credenciales."""
    try:
        import praw

        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
            user_agent="CobaltoHub/1.0",
        )
        results = []
        for sub in ["vzla", "ciberseguridad"]:
            for s in reddit.subreddit(sub).hot(limit=3):
                item = {
                    "title": s.title[:140],
                    "summary": s.selftext[:300],
                    "link": f"https://reddit.com{s.permalink}",
                    "published": datetime.fromtimestamp(s.created_utc).strftime("%Y-%m-%d"),
                    "source": f"r/{sub}",
                }
                if not is_duplicate(item):
                    results.append(item)
        return results
    except Exception:
        return []


# ── Extractores: Datos Públicos (Crypto, Clima) ──────────────────
def fetch_crypto() -> List[Dict]:
    """Precios de Criptomonedas."""
    resp = safe_get(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,tether&vs_currencies=usd&include_24hr_change=true"
    )
    if not resp:
        return []
    try:
        data = resp.json()
        results = []
        for coin, vals in data.items():
            item = {
                "title": f"{coin.upper()}: ${vals['usd']:,}",
                "summary": f"Cambio 24h: {vals['usd_24h_change']:.2f}%",
                "link": f"https://www.coingecko.com/en/coins/{coin}",
                "published": datetime.now().strftime("%H:%M"),
                "source": "Crypto",
            }
            results.append(item)
        return results
    except Exception:
        return []


# ── FUNCIÓN PRINCIPAL CONSOLIDADA ────────────────────────────────
def get_social_hub_data() -> Dict[str, Any]:
    """Recolecta todos los datos sociales y públicos de forma eficiente."""
    with _SEEN_HASHES_LOCK:
        _SEEN_HASHES.clear()
    start_time = time.time()

    tasks = [
        ("Reddit Public", lambda: fetch_rss("Reddit Vzla", "https://www.reddit.com/r/vzla/new/.rss")),
        (
            "Telegram",
            lambda: fetch_rss("Telegram @notivenezuelaarma", "https://rsshub.app/telegram/channel/notivenezuelaarma"),
        ),
        ("Hacker News", lambda: fetch_rss("Hacker News", "https://hnrss.org/frontpage")),
        ("Nitter Vzla", lambda: fetch_nitter("venezuela")),
        ("TikTok Hashtags", get_tiktok_all),
        ("TikTok Perfiles", get_tiktok_profiles),
        ("Crypto", fetch_crypto),
        ("Reddit Auth", fetch_reddit_auth),
    ]

    social_data = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sources": {}, "count": 0}

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_name = {executor.submit(func): name for name, func in tasks}
        for future in future_to_name:
            name = future_to_name[future]
            try:
                items = future.result(timeout=15)
                if items:
                    social_data["sources"][name] = items
                    social_data["count"] += len(items)
            except Exception as e:
                logger.error(f"{name}: {e}")

    logger.info(f"Completado en {time.time() - start_time:.2f}s. Total: {social_data['count']} items.")
    return social_data


if __name__ == "__main__":
    data = get_social_hub_data()
    print(json.dumps(data, indent=2))
