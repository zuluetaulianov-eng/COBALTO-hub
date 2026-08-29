# social_hub.py - Centro Unificado de Inteligencia Social (Cobalto Hub 2026)
# Consolidación de: social_extractor, social_extractor_v2, social_public_extractor, social_data
# Enfoque: Eficiencia, deduplicación y resiliencia ante censura.

import hashlib
import html
import json
import logging
import os
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import requests
from dotenv import load_dotenv
from lxml_html_clean import Cleaner

from config import RESIDENTIAL_PROXY_URL
from extractor import normalize_video_embed_url
from osint_deep_scraper import scraper
from osint_tls_backend import tls_manager
from tiktok_extractor import get_tiktok_all, get_tiktok_profiles

logger = logging.getLogger(__name__)

# ── Configuración y Carga de Entorno ──────────────────────────────
load_dotenv()

# ── Utilidades de Limpieza y Normalización ────────────────────────
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


def canonicalize_url(url: str) -> str:
    """Normaliza una URL a un formato canónico sin subdominios espejo ni query params tracking."""
    if not url or url == "#":
        return "#"
    try:
        parsed = urlparse(url.lower().strip())
        netloc = parsed.netloc
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        if "redlib" in netloc or "libreddit" in netloc or "reddit.com" in netloc:
            netloc = "reddit.com"
        elif netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}"
    except Exception:
        return url.lower().strip()


def clean_html(html_content: str) -> str:
    """Limpia HTML, rastros de IA (thinking process) y artefactos de listas en publicaciones OSINT/sociales."""
    if not html_content:
        return ""
    try:
        text = html.unescape(str(html_content))
        text = re.sub(r'<(br|p|div|/p|/div)[^>]*>', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)

        # 1. Eliminar rastros de cadenas de pensamiento de IA (DeepSeek, Llama, Ollama, etc.)
        text = re.sub(r"(?i)<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"(?i)here'?s\s+a\s+thinking\s+process:?", "", text)
        text = re.sub(r"(?i)thinking\s+process:?", "", text)

        # 2. Eliminar artefactos de listas de Python str tipo "['🌍', '🌎']" o "'🌍', '🌎']"
        text = re.sub(r"^\s*\[?\s*(?:['\"][^'\"]*['\"]\s*,\s*)*['\"][^'\"]*['\"]\s*\]\s*", "", text)
        text = re.sub(r"^\s*['\"][^'\"]*['\"]\s*,\s*['\"][^'\"]*['\"]\s*\]\s*", "", text)

        # 3. Eliminar caracteres sueltos de cierre/apertura sobrantes al inicio
        text = re.sub(r"^\s*['\"\]\)]+\s*", "", text)

        text = re.sub(r'\s+', ' ', text).strip()
        return text[:300]
    except Exception:
        return str(html_content)[:300]


# ── Gestión de Conexión (Tor + Fallback + TLS Evasion + Proxies) ──
TOR_BLOCKS = ["t.me", "telegram.org", "reddit.com", "facebook.com", "instagram.com", "tiktok.com"]

_session = requests.Session()
_session.headers.update(scraper.get_headers())


def safe_get(url: str, timeout: int = 12) -> Optional[requests.Response]:
    """Conexión inteligente usando TLS manager rotativo, proxies residenciales y Tor."""
    domain = url.split("/")[2] if "://" in url else url

    if "reddit.com" in domain:
        headers = {"User-Agent": "cobalto-hub:v9.0 (by /u/cobaltouser)"}
        try:
            resp = _session.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                return resp
        except Exception:
            pass

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

    # 1. Si el dominio bloquea Tor (Reddit, Telegram, etc.)
    if any(b in domain for b in TOR_BLOCKS):
        proxies = None
        proxy_url = RESIDENTIAL_PROXY_URL or os.getenv("RESIDENTIAL_PROXY_URL")
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        # Usar tls_manager para evitar TLS fingerprinting
        resp = tls_manager.request("GET", url, platform="social_hub", headers=headers, proxies=proxies, timeout=timeout)
        if resp is not None and getattr(resp, "status_code", 0) == 200:
            return resp
        # Fallback a session directa
        try:
            return _session.get(url, headers=headers, proxies=proxies, timeout=timeout)
        except Exception:
            return None

    # 2. Si no bloquea Tor, intentar vía Tor SOCKS
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
            resp = tls_manager.request("GET", url, platform="social_hub", headers=headers, proxies=proxies, timeout=timeout + 5)
            if resp is not None and getattr(resp, "status_code", 0) == 200:
                return resp
        except Exception:
            pass

    # 3. Fallback final usando TLS manager o sesión directa
    resp = tls_manager.request("GET", url, platform="social_hub", headers=headers, timeout=timeout)
    if resp is not None and getattr(resp, "status_code", 0) == 200:
        return resp
    try:
        return _session.get(url, headers=headers, timeout=timeout)
    except Exception:
        return None


# ── Deduplicación Centralizada Canónica (thread-safe) ────────────
_SEEN_HASHES = set()
_SEEN_HASHES_LOCK = threading.Lock()


def is_duplicate(item: Dict) -> bool:
    """Verifica si el contenido ya fue procesado en la ejecución actual usando URL canónica."""
    title = (item.get("title", "") or "").lower().strip()
    canon_link = canonicalize_url(item.get("link", ""))
    content = f"{title}|{canon_link}"
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    with _SEEN_HASHES_LOCK:
        if h in _SEEN_HASHES:
            return True
        _SEEN_HASHES.add(h)
        return False


# ── Extractores: Redes Sociales Abiertas (Bluesky + Mastodon) ────
BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
MASTODON_INSTANCES = [
    "https://mastodon.social",
    "https://fosstodon.org",
    "https://infosec.exchange",
]


def fetch_bluesky(hashtag: str, max_items: int = 6) -> List[Dict]:
    """Extrae posts de Bluesky via AT Protocol public API (sin autenticación)."""
    try:
        params = {"q": f"#{hashtag}", "limit": max_items, "sort": "latest"}
        headers = {"User-Agent": "CobaltoHub/9.0 OSINT (+https://github.com/cobalto)"}
        resp = _session.get(BLUESKY_API, params=params, headers=headers, timeout=10)
        if not resp or resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for post in data.get("posts", [])[:max_items]:
            record = post.get("record", {})
            author = post.get("author", {})
            text = record.get("text", "").strip()
            if not text:
                continue
            handle = author.get("handle", "bsky")
            uri = post.get("uri", "")
            post_id = uri.split("/")[-1] if uri else ""
            link = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else "https://bsky.app"
            item = {
                "title": text[:140],
                "summary": text,
                "link": link,
                "published": record.get("createdAt", "Reciente")[:16].replace("T", " "),
                "source": f"Bluesky #{hashtag}",
                "image": None,
            }
            if not is_duplicate(item):
                results.append(item)
        return results
    except Exception:
        return []


def fetch_mastodon(hashtag: str, max_items: int = 6) -> List[Dict]:
    """Extrae posts de Mastodon via API pública REST (sin autenticación)."""
    for instance in MASTODON_INSTANCES:
        try:
            url = f"{instance}/api/v1/timelines/tag/{hashtag}"
            params = {"limit": max_items}
            headers = {"User-Agent": "CobaltoHub/9.0 OSINT"}
            resp = _session.get(url, params=params, headers=headers, timeout=10)
            if not resp or resp.status_code != 200:
                continue
            posts = resp.json()
            if not isinstance(posts, list) or not posts:
                continue
            results = []
            for post in posts[:max_items]:
                content_html = post.get("content", "")
                text = clean_html(content_html)
                if not text:
                    continue
                account = post.get("account", {})
                acct = account.get("acct", "mastodon")
                link = post.get("url") or f"{instance}/@{acct}"
                published = (post.get("created_at") or "Reciente")[:16].replace("T", " ")
                media = post.get("media_attachments", [])
                image = None
                video = None
                if media:
                    for att in media:
                        att_type = att.get("type")
                        if att_type in ("video", "gifv"):
                            video = att.get("url")
                            image = att.get("preview_url")
                            break
                        elif att_type == "image" and not image:
                            image = att.get("preview_url") or att.get("url")

                item = {
                    "title": text[:140],
                    "summary": text,
                    "link": link,
                    "published": published,
                    "source": f"Mastodon #{hashtag} ({instance.split('//')[1]})",
                    "image": image,
                    "video": video,
                }
                if not is_duplicate(item):
                    results.append(item)
            if results:
                return results
        except Exception:
            continue
    return []


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



# ── Extractor: twitterwebviewer.com (X/Twitter sin API key) ──────
TWITTER_WEB_VIEWER_BASE = "https://twitterwebviewer.com"


def fetch_twitterwebviewer(query: str, max_items: int = 6) -> List[Dict]:
    """Extrae posts de X/Twitter via twitterwebviewer.com (sin credenciales)."""
    try:
        from bs4 import BeautifulSoup
        url = f"{TWITTER_WEB_VIEWER_BASE}/search"
        params = {"q": query, "f": "live"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "es-419,es;q=0.9",
            "Referer": TWITTER_WEB_VIEWER_BASE,
        }
        resp = _session.get(url, params=params, headers=headers, timeout=15)
        if not resp or resp.status_code != 200:
            logger.warning(f"[TWV] twitterwebviewer retornó {getattr(resp, 'status_code', 'N/A')} para '{query}'")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        tweet_divs = (
            soup.select("div.tweet") or
            soup.select("article") or
            soup.select("div[data-tweet-id]") or
            soup.select(".tweet-body, .timeline-Tweet")
        )
        for div in tweet_divs[:max_items]:
            text_el = div.select_one(".tweet-text, p, .timeline-Tweet-text")
            text = text_el.get_text(" ", strip=True) if text_el else ""
            if not text or len(text) < 10:
                continue
            link_el = div.select_one("a[href*='twitter.com'], a[href*='x.com']")
            link = link_el["href"] if link_el and link_el.get("href") else f"https://x.com/search?q={query}"
            if not link.startswith("http"):
                link = TWITTER_WEB_VIEWER_BASE + link
            time_el = div.select_one("time, .tweet-timestamp, .js-short-timestamp")
            published = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else "Reciente"
            item = {
                "title": text[:140],
                "summary": text,
                "link": link,
                "published": published[:16] if len(published) > 16 else published,
                "source": f"X/Twitter #{query}",
            }
            if not is_duplicate(item):
                results.append(item)
        if not results:
            logger.warning(f"[TWV] Sin tweets parseados para '{query}' (HTML puede haber cambiado)")
        return results
    except Exception as e:
        logger.warning(f"[TWV] twitterwebviewer error para '{query}': {e}")
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
        ("Reddit Vzla", lambda: fetch_rss("Reddit Vzla", "https://www.reddit.com/r/vzla/new/.rss")),
        ("Reddit Colombia", lambda: fetch_rss("Reddit Colombia", "https://www.reddit.com/r/Colombia/new/.rss")),
        (
            "Telegram",
            lambda: fetch_rss("Telegram @notivenezuelaarma", "https://rsshub.app/telegram/channel/notivenezuelaarma"),
        ),
        ("Hacker News", lambda: fetch_rss("Hacker News", "https://hnrss.org/frontpage")),
        ("Bluesky Venezuela", lambda: fetch_bluesky("venezuela")),
        ("Bluesky Colombia", lambda: fetch_bluesky("colombia")),
        ("Bluesky CiberSeg", lambda: fetch_bluesky("ciberseguridad")),
        ("Mastodon Venezuela", lambda: fetch_mastodon("venezuela")),
        ("Mastodon Colombia", lambda: fetch_mastodon("colombia")),
        ("Mastodon InfoSec", lambda: fetch_mastodon("infosec")),
        ("X Venezuela", lambda: fetch_twitterwebviewer("venezuela")),
        ("X Colombia", lambda: fetch_twitterwebviewer("colombia")),
        ("X CiberSeg", lambda: fetch_twitterwebviewer("ciberseguridad")),
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
                    for item in items:
                        if not item.get("video"):
                            lnk = item.get("link", "")
                            if lnk and lnk != "#":
                                norm_vid = normalize_video_embed_url(lnk)
                                if norm_vid and (
                                    "youtube" in norm_vid
                                    or "vimeo" in norm_vid
                                    or "tiktok" in norm_vid
                                    or "dailymotion" in norm_vid
                                    or "rumble" in norm_vid
                                    or norm_vid.endswith((".mp4", ".webm", ".m3u8", ".mov"))
                                ):
                                    item["video"] = norm_vid

                        if "country_tags" not in item:
                            txt = f"{item.get('title', '')} {item.get('summary', '')}"
                            dom = item.get("link", "")
                            src = item.get("source", name)
                            try:
                                import theaters_config
                                item["country_tags"] = theaters_config.detect_country_tags(text=txt, domain=dom, source=src)
                            except Exception:
                                item["country_tags"] = ["GLOBAL"]
                    social_data["sources"][name] = items
                    social_data["count"] += len(items)
            except Exception as e:
                logger.warning(f"{name}: sin datos ({type(e).__name__})")

    logger.info(f"Completado en {time.time() - start_time:.2f}s. Total: {social_data['count']} items.")
    return social_data


if __name__ == "__main__":
    data = get_social_hub_data()
    print(json.dumps(data, indent=2))
