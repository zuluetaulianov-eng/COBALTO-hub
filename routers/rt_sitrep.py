"""
routers/rt_sitrep.py — Lectura profunda de noticias SITREP
Rutas: GET /api/sitrep/article
"""
import html as html_lib
import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query

from security_utils import sanitize_for_json

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sitrep"])

_CACHE: dict = {}
_CACHE_TTL = 600
_CACHE_MAX = 80

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
_ARTICLE_SELECTORS = [
    "article",
    "[itemprop='articleBody']",
    ".article-body",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".story-body",
    ".news-body",
    ".td-post-content",
    ".c-entry-content",
    ".noticia-cuerpo",
    ".cuerpo-noticia",
    ".content-body",
    "main article",
    "main",
]
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
_JUNK_TAGS = [
    "script", "style", "nav", "header", "footer", "aside", "form", "iframe",
    "noscript", "svg", "button", "input", "select", "textarea", "template",
    "video", "audio", "canvas", "link", "meta", "object", "embed",
]
_JUNK_SELECTORS = [
    ".share", ".social-share", ".sharing", ".related", ".related-posts",
    ".advert", ".ads", ".ad", ".adsbygoogle", ".cookie", ".comments",
    ".newsletter", ".subscribe", ".breadcrumb", ".tags", ".author-box",
    ".recommended", ".most-read", ".widget", ".sidebar", ".paywall",
    ".popup", ".modal", ".banner", "[role='navigation']", "[role='banner']",
    "[role='complementary']",
]
_JUNK_LINE = re.compile(
    r"(compartir|síguenos|suscr[ií]bete|newsletter|publicidad|cookie|"
    r"facebook|twitter|whatsapp|telegram|instagram|pinterest|"
    r"function\s*\(|window\.|document\.|var\s+\w+\s*=|"
    r"\{[\s\S]{0,80}\}|;\s*$|^\s*[.#][\w-]+\s*\{)",
    re.I,
)


def is_safe_article_url(url: str) -> bool:
    if not url or not isinstance(url, str) or len(url) > 2000:
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not host or host in _BLOCKED_HOSTS:
            return False
        if host.endswith(".local") or host.endswith(".internal") or host.endswith(".localhost"):
            return False
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def _meta(soup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return clean_plain_text(tag["content"].strip(), max_len=500, strip_urls=False)
    return ""


def clean_plain_text(raw: str, max_len: int = 12000, strip_urls: bool = True) -> str:
    if not raw:
        return ""
    text = html_lib.unescape(str(raw))
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    if strip_urls:
        text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if _JUNK_LINE.search(line) and len(line) < 180:
            continue
        if re.fullmatch(r"[\W_]+", line):
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:max_len]


def extract_article_from_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    title = _meta(soup, "og:title", "twitter:title")
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    description = _meta(soup, "og:description", "description", "twitter:description")
    image = _meta(soup, "og:image", "twitter:image")
    author = _meta(soup, "author", "article:author", "og:article:author")
    site_name = _meta(soup, "og:site_name")
    published = _meta(soup, "article:published_time", "og:published_time", "pubdate")
    section = _meta(soup, "article:section", "og:article:section")

    if image and image.startswith("//"):
        image = "https:" + image
    elif image and image.startswith("/"):
        image = urljoin(url, image)

    work = BeautifulSoup(html or "", "html.parser")
    for el in work(_JUNK_TAGS):
        el.decompose()
    for sel in _JUNK_SELECTORS:
        for el in work.select(sel):
            el.decompose()

    body_node = None
    body_text = ""
    for sel in _ARTICLE_SELECTORS:
        node = work.select_one(sel)
        if not node:
            continue
        text = clean_plain_text(node.get_text(separator="\n", strip=True))
        if len(text) > 220:
            body_node = node
            body_text = text
            break

    if not body_text:
        body_text = clean_plain_text(work.get_text(separator="\n", strip=True))

    images = []
    if image:
        images.append(image)
    src_root = body_node or work
    for img in src_root.find_all("img", src=True):
        src = img.get("src") or ""
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin(url, src)
        if not src.startswith("http"):
            continue
        if any(skip in src.lower() for skip in ("pixel", "spacer", "1x1", "icon", "logo", "avatar", "emoji", "sprite")):
            continue
        if src not in images:
            images.append(src)
        if len(images) >= 6:
            break

    words = len(re.findall(r"\w+", body_text))
    domain = urlparse(url).netloc.replace("www.", "")

    return {
        "ok": True,
        "url": url,
        "title": title,
        "description": description,
        "content": body_text,
        "author": author,
        "site_name": site_name or domain,
        "published": published,
        "section": section,
        "image": images[0] if images else "",
        "images": images,
        "word_count": words,
        "domain": domain,
    }


def _cache_get(url: str):
    item = _CACHE.get(url)
    if not item:
        return None
    if time.time() - item["ts"] > _CACHE_TTL:
        _CACHE.pop(url, None)
        return None
    return item["data"]


def _cache_set(url: str, data: dict):
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1]["ts"])[0]
        _CACHE.pop(oldest, None)
    _CACHE[url] = {"ts": time.time(), "data": data}


@router.get("/api/sitrep/article")
async def get_sitrep_article(url: str = Query(..., min_length=8, max_length=2000)):
    url = url.strip()
    if not is_safe_article_url(url):
        raise HTTPException(status_code=400, detail="URL no permitida")

    cached = _cache_get(url)
    if cached:
        return sanitize_for_json(cached)

    html = ""
    status_code = 200
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=_HEADERS, ssl=False, allow_redirects=True, max_redirects=5) as resp:
                status_code = resp.status
                html = await resp.text()
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("[SITREP ARTICLE] fetch failed %s: %s", url, e)
        raise HTTPException(status_code=502, detail="No se pudo extraer el artículo")

    data = extract_article_from_html(html, url)
    if not data.get("content") or len(data["content"]) < 80:
        if status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Fuente respondió {status_code}")
        raise HTTPException(status_code=502, detail="La fuente no entregó cuerpo usable")

    _cache_set(url, data)
    return sanitize_for_json(data, preserve_html_fields=[])
