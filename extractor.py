import asyncio
import logging
import random
import re
import textwrap
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
import feedparser
import tls_client
from bs4 import BeautifulSoup
from lxml_html_clean import Cleaner

import config
from config import (
    ALLOWED_SCHEMES,
    KEYWORDS,
    OWN_POSTS,
    PROBLEM_FEEDS,
    RSS_FEEDS,
    TELEGRAM_SOURCES,
)
from database import get_http_cache, update_http_cache
from feed_repair import load_patches, repair_feed
from osint_playwright import fetch_rss_with_browser
from utils import parse_datetime

try:
    from humanization import get_headers_with_random_ua

    HUMANIZATION_AVAILABLE = True
except ImportError:
    HUMANIZATION_AVAILABLE = False

# ── Circuit Breaker para Feeds ────────────────────────────────────
_feed_cb_lock = threading.Lock()
_feed_failures: dict = {}  # source -> consecutive failures
_FEED_CB_THRESHOLD = 3  # fallos consecutivos antes de saltar
_FEED_CB_RECOVERY = 600  # segundos hasta reintentar (10 min)


def is_feed_available(source: str) -> bool:
    """Retorna True si el feed no ha superado el umbral de fallos."""
    with _feed_cb_lock:
        failures, last_fail = _feed_failures.get(source, (0, 0))
        if failures >= _FEED_CB_THRESHOLD:
            if time.time() - last_fail > _FEED_CB_RECOVERY:
                del _feed_failures[source]
                return True
            return False
        return True


def report_feed_failure(source: str):
    with _feed_cb_lock:
        failures, last_fail = _feed_failures.get(source, (0, 0))
        _feed_failures[source] = (failures + 1, time.time())
        if failures + 1 >= _FEED_CB_THRESHOLD:
            logging.warning(
                f"[FEED CB] {source} ABIERTO ({failures + 1} fallos). Reintentando en {_FEED_CB_RECOVERY}s."
            )


def report_feed_success(source: str):
    with _feed_cb_lock:
        _feed_failures.pop(source, None)


def get_circuit_breaker_count() -> int:
    """Retorna cuántos feeds están actualmente en circuito abierto."""
    with _feed_cb_lock:
        now = time.time()
        return sum(1 for v in _feed_failures.values() if v[0] >= _FEED_CB_THRESHOLD and now - v[1] < _FEED_CB_RECOVERY)


def get_feeds_health() -> dict:
    """Retorna estado de salud detallado de todas las fuentes con circuit breaker."""
    with _feed_cb_lock:
        now = time.time()
        healthy = []
        degraded = []
        down = []
        for source, (failures, last_fail) in _feed_failures.items():
            remaining = max(0, _FEED_CB_RECOVERY - (now - last_fail))
            if failures >= _FEED_CB_THRESHOLD and now - last_fail < _FEED_CB_RECOVERY:
                down.append({"source": source, "failures": failures, "remaining_seconds": int(remaining)})
            else:
                degraded.append({"source": source, "failures": failures, "remaining_seconds": int(remaining)})
        return {
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "total_healthy": len(healthy),
            "total_degraded": len(degraded),
            "total_down": len(down),
            "threshold": _FEED_CB_THRESHOLD,
            "recovery_seconds": _FEED_CB_RECOVERY,
        }


# ── Configuraciones hardening ─────────────────────────────────────
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=25)
REQUEST_TIMEOUT_PROBLEM = aiohttp.ClientTimeout(total=35)
MAX_ENTRIES_PER_FEED = 12
MAX_RELEVANT_PER_FEED = 6
BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "extractor.log.json"
MAX_RETRIES = 0
BATCH_SIZE = 20

# Estado global de extracción (con límite para evitar memory leak)
MAX_SEEN_LINKS = 5000
seen_links = set()
_seen_links_lock = asyncio.Lock()


def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        return bool(parsed.netloc)
    except Exception:
        return False


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.0",
]

if not logging.getLogger().hasHandlers():
    import logging.handlers as _log_handlers
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(message)s",
        handlers=[
            _log_handlers.RotatingFileHandler(
                LOG_FILE.with_suffix(".txt"),
                maxBytes=5 * 1024 * 1024,  # 5 MB por archivo
                backupCount=2,             # Máximo 2 rotaciones (10 MB total)
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )
# Silenciar warnings de encoding de BeautifulSoup y charset_normalizer
logging.getLogger("bs4").setLevel(logging.ERROR)
logging.getLogger("charset_normalizer").setLevel(logging.ERROR)

cleaner = Cleaner(
    allow_tags=["p", "br", "strong", "em", "a", "ul", "ol", "li"],
    safe_attrs=["href", "title"],
    scripts=True,
    javascript=True,
    comments=True,
    frames=True,
    forms=True,
    annoying_tags=True,
    embedded=True,
    processing_instructions=True,
    add_nofollow=True,
    links=False,
    meta=True,  # links=False para no interferir con imágenes
)


def normalize_url(url):
    if not url or url == "#":
        return url
    parsed = urlparse(url)
    query = "&".join(
        p
        for p in parsed.query.split("&")
        if not p.lower().startswith(("utm_", "fbclid", "ref=", "source=", "campaign="))
    )
    cleaned = urlunparse(
        (parsed.scheme, parsed.netloc.lower().replace("www.", ""), parsed.path.rstrip("/"), parsed.params, query, "")
    )
    return cleaned


def safe_published_datetime(parsed_tuple):
    return parse_datetime(parsed_tuple)


def extract_featured_image(entry, base_url):
    image_url = None

    # Buscar en media_content
    if "media_content" in entry:
        for media in entry.media_content:
            if media.get("medium") == "image":
                image_url = media.get("url")
                break

    # Buscar en media_thumbnail
    if not image_url and "media_thumbnail" in entry:
        thumbs = entry.media_thumbnail
        if thumbs and len(thumbs) > 0:
            image_url = thumbs[0].get("url")

    # Buscar en content/summary HTML
    if not image_url:
        content = entry.get("summary") or entry.get("description", "")
        if not content and "content" in entry:
            content = entry.content[0].get("value", "") if entry.content else ""

        if content:
            try:
                soup = BeautifulSoup(content, "html.parser")
                img = soup.find("img")
                if img and img.get("src"):
                    image_url = img["src"]
            except Exception:
                pass

    if image_url:
        image_url = urljoin(base_url, image_url)
        # Validar extensión de imagen
        if not re.search(r"\.(jpe?g|png|webp|gif|bmp|svg)(\?.*)?$", image_url, re.I):
            image_url = None

    return image_url


def _clean_and_extract_summary(summary_raw):
    """Limpia y extrae texto plano de HTML de manera segura y síncrona (CPU-bound)"""
    try:
        cleaned_html = cleaner.clean_html(summary_raw)
        soup = BeautifulSoup(cleaned_html, "html.parser")
        for script in soup.find_all("script"):
            script.decompose()
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return summary_raw


async def parse_single_feed_async(session, source, url, retry_count=0, problem_info=None):
    global _seen_links_lock, seen_links
    """Procesa un solo feed RSS con manejo de errores y reintentos"""

    # Circuit breaker: saltar feeds que han fallado consistentemente
    if not is_feed_available(source):
        logging.info(f"[FEED CB SKIP] {source} — circuito abierto")
        return source, []

    # Determinar timeout según si es feed problemático
    request_timeout = REQUEST_TIMEOUT
    if problem_info:
        status = problem_info.get("status", "")
        if status in ("intermitente", "dudoso", "lento"):
            request_timeout = REQUEST_TIMEOUT_PROBLEM
            logging.info(f"[PROBLEM FEED] {source}: timeout extendido a {request_timeout.total}s")

    # Aplicar humanización (delay mínimo, evitando acumular ~105s en 70 feeds)
    if HUMANIZATION_AVAILABLE:
        await asyncio.sleep(random.uniform(0.1, 0.3))

    content = None
    response = None

    try:
        cached_info = await asyncio.to_thread(get_http_cache, source)
        etag = cached_info.get("etag")
        last_mod = cached_info.get("last-modified")

        if HUMANIZATION_AVAILABLE:
            headers = get_headers_with_random_ua()
        else:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/rss+xml, application/rdf+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.7,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

        if etag:
            headers["If-None-Match"] = etag
        if last_mod:
            headers["If-Modified-Since"] = last_mod

        # Intento 1: HTTP directo
        try:
            ssl_val = None
            if "avn.info.ve" in url or "vencert.suscerte.gob.ve" in url:
                ssl_val = False
            elif problem_info and "ssl" in str(problem_info.get("notes", "")).lower():
                ssl_val = False

            async with session.get(url, headers=headers, timeout=request_timeout, ssl=ssl_val) as response:
                if response.status == 304:
                    logging.info(f"[CACHE HIT] {source}")
                    return source, []

                if response.status in (401, 403, 503, 429):
                    logging.warning(f"[{response.status}] {source} bloqueó petición directa.")
                    report_feed_failure(source)
                    response = None  # Marcar para usar Playwright
                else:
                    response.raise_for_status()
                    content = await response.read()
                    try:
                        await asyncio.to_thread(
                            update_http_cache,
                            source,
                            response.headers.get("ETag"),
                            response.headers.get("Last-Modified"),
                        )
                    except Exception:
                        pass  # Cache failure no debe afectar el circuit breaker
                    report_feed_success(source)
        except asyncio.TimeoutError:
            logging.warning(f"[TIMEOUT DIRECT] {source}")
            report_feed_failure(source)
            response = None
        except Exception as net_err:
            err_name = type(net_err).__name__
            logging.warning(f"[NETWORK {err_name}] {source}: {str(net_err)[:80]}")
            report_feed_failure(source)
            response = None

        # Intento 1.5: Fallback a tls_client para evadir bloqueos TLS ligeros antes de Playwright
        if content is None and response is None and is_feed_available(source):
            try:
                def fetch_with_tls():
                    session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
                    return session.get(url, headers=headers, timeout_seconds=request_timeout.total)

                logging.info(f"[TLS_CLIENT] Intentando evasión ligera para {source}...")
                tls_resp = await asyncio.to_thread(fetch_with_tls)

                if tls_resp.status_code == 200:
                    content = tls_resp.content
                    report_feed_success(source)
                    logging.info(f"[TLS_CLIENT OK] {source} evadido con éxito.")
                else:
                    logging.warning(f"[TLS_CLIENT FAIL] {source} retornó {tls_resp.status_code}.")
            except Exception as e:
                logging.warning(f"[TLS_CLIENT ERROR] {source}: {e}")

        # Intento 2: Playwright si el directo falló o fue bloqueado
        # Solo en el primer fallo consecutivo; si ya falló antes, evitamos 30s de navegador
        _skip_pw = False
        if content is None and response is None:
            with _feed_cb_lock:
                fcount, _ = _feed_failures.get(source, (0, 0))
                if fcount >= 2:
                    _skip_pw = True
        if content is None and response is None and not _skip_pw and is_feed_available(source):
            logging.info(f"[PLAYWRIGHT] Intentando {source} con navegador...")
            try:
                content = await fetch_rss_with_browser(url)
                if not content:
                    logging.error(f"[PLAYWRIGHT FALLÓ] {source}")
                    return source, []
                report_feed_success(source)
            except Exception as e:
                logging.error(f"[PLAYWRIGHT ERROR] {source}: {e}")
                return source, []

        # Si no hay contenido tras ambos intentos, salir
        if content is None:
            return source, []
        # Parsear feed
        feed = await asyncio.to_thread(feedparser.parse, content)

        # Si es bozo, intentar reparación profunda
        if (feed.bozo or not feed.entries) and retry_count < MAX_RETRIES:
            logging.info(f"[DEEP REPAIR] {source} - buscando alternativas...")
            new_url = await repair_feed(source, url)
            if new_url and new_url != url:
                logging.info(f"[DEEP REPAIR] Reintentando con: {new_url}")
                return await parse_single_feed_async(session, source, new_url, retry_count + 1, problem_info)

        if feed.bozo:
            logging.warning(f"[BOZO] {source}: {getattr(feed, 'bozo_exception', 'unknown')}")

        if not feed.entries:
            logging.info(f"[VACÍO] {source}: sin entradas")
            return source, []

        # Procesar entradas
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=config.ENTRY_MAX_AGE_HOURS)

        entries = []
        raw_count = len(feed.entries)

        # Fuentes prioritarias para bajar guardia del filtro
        priority_sources = {
            "El Nacional",
            "El Estímulo",
            "La Patilla",
            "Runrun.es",
            "Efecto Cocuyo",
            "Banca y Negocios",
        }
        is_priority = source in priority_sources
        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            published_raw = entry.get("published") or entry.get("updated")
            published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            dt = parse_datetime(published_raw) or parse_datetime(published_parsed)

            if not dt:
                dt = now  # Fallback

            if dt < cutoff_time:
                continue

            title = entry.get("title", "Sin título").strip()
            link = entry.get("link", "#")

            if not is_valid_url(link):
                continue

            link_clean = normalize_url(link)

            async with _seen_links_lock:
                if link_clean in seen_links:
                    continue
                if len(seen_links) >= MAX_SEEN_LINKS:
                    seen_links = set(list(seen_links)[-MAX_SEEN_LINKS // 2 :])
                seen_links.add(link_clean)

            # Limpiar summary (Operación CPU-bound offloaded a hilo separado)
            summary_raw = entry.get("summary", entry.get("description", ""))
            if not summary_raw and "content" in entry:
                summary_raw = entry.content[0].get("value", "") if entry.content else ""

            summary = await asyncio.to_thread(_clean_and_extract_summary, summary_raw)

            # Filtrado por keywords (incluyendo auto-trackers cosechados por el sistema)
            text = (title + " " + summary).lower()
            active_keywords = set(k.lower() for k in KEYWORDS)
            try:
                import auto_tracker
                active_keywords.update(auto_tracker.get_active_auto_keywords_set())
            except Exception:
                pass
            matches_keyword = any(kw in text for kw in active_keywords)

            if matches_keyword or is_priority:
                # Offload de parsing de imágenes (BeautifulSoup) a hilo separado
                image_url = await asyncio.to_thread(extract_featured_image, entry, url)

                try:
                    import theaters_config
                    c_tags = theaters_config.detect_country_tags(text=text, domain=url, source=source)
                except Exception:
                    c_tags = ["GLOBAL"]

                entries.append(
                    {
                        "title": title,
                        "link": link,
                        "summary": textwrap.shorten(summary, width=280, placeholder="..."),
                        "published": entry.get("published", entry.get("updated", str(now))),
                        "published_dt": dt,
                        "published_iso": dt.isoformat(),
                        "image": image_url,
                        "source": source,
                        "type": "external",
                        "priority": is_priority,
                        "country_tags": c_tags,
                    }
                )

        # Fallback si quedó vacío pero tenía entradas recientes
        if not entries and feed.entries:
                entry = feed.entries[0]
                dt = parse_datetime(entry.get("published")) or parse_datetime(entry.get("published_parsed")) or now
                if dt >= cutoff_time:
                    try:
                        import theaters_config
                        c_tags = theaters_config.detect_country_tags(text=entry.get("title", ""), domain=url, source=source)
                    except Exception:
                        c_tags = ["GLOBAL"]
                    entries.append(
                        {
                            "title": "[MONITOREO] " + entry.get("title", "Sin título"),
                            "link": entry.get("link", "#"),
                            "summary": "(Noticia general - sistema de monitoreo)",
                            "published_dt": dt,
                            "published_iso": dt.isoformat(),
                            "source": source,
                            "type": "external_low_priority",
                            "priority": False,
                            "country_tags": c_tags,
                        }
                    )

        entries.sort(key=lambda x: x["published_dt"], reverse=True)
        entries = entries[:MAX_RELEVANT_PER_FEED]

        report_feed_success(source)
        logging.info(f"[EXTRACTOR] {source}: {len(entries)}/{raw_count} noticias")
        return source, entries

    except asyncio.TimeoutError:
        report_feed_failure(source)
        if retry_count < MAX_RETRIES:
            wait_time = 2**retry_count + random.uniform(0, 1)
            logging.info(f"[RETRY {retry_count + 1}] {source} tras {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            return await parse_single_feed_async(session, source, url, retry_count + 1, problem_info)
        logging.error(f"[TIMEOUT FINAL] {source}")
        return source, []

    except Exception as e:
        report_feed_failure(source)
        logging.exception(f"[CRITICAL] {source}: {e}")
        return source, []


async def fetch_telegram_source(source_name, url):
    """Scrapea canales públicos de Telegram vía t.me/s/ (vista web pública)"""
    global _seen_links_lock, seen_links
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-ES,es;q=0.9",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logging.warning(f"[TELEGRAM {resp.status}] {source_name}")
                    return source_name, []
                html = await resp.text()

        # Offload del pesado parser HTML de Telegram (CPU-bound) a un hilo de procesamiento de asyncio
        soup = await asyncio.to_thread(BeautifulSoup, html, "html.parser")
        messages = soup.select(".tgme_widget_message_wrap")
        if not messages:
            messages = soup.select(".tgme_widget_message")
        if not messages:
            logging.info(f"[TELEGRAM VACÍO] {source_name}: sin mensajes visibles")
            return source_name, []

        entries = []
        skipped_no_text = 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=config.ENTRY_MAX_AGE_HOURS)

        for msg in messages[:25]:
            try:
                text_el = msg.select_one(".tgme_widget_message_text")
                text = text_el.get_text(strip=True) if text_el else ""

                if not text:
                    # Si no hay texto, verificar si hay contenido multimedia para no omitir la publicación
                    has_media = (
                        msg.select_one(".tgme_widget_message_photo_wrap") or
                        msg.select_one(".tgme_widget_message_video_player") or
                        msg.select_one(".tgme_widget_message_video") or
                        msg.select_one(".tgme_widget_message_roundvideo") or
                        msg.select_one(".tgme_widget_message_document")
                    )
                    if has_media:
                        text = f"Reporte multimedia (Foto o Video) publicado por {source_name}"
                    else:
                        skipped_no_text += 1
                        continue

                date_el = msg.select_one("time")
                pub_dt = None
                if date_el and date_el.get("datetime"):
                    try:
                        pub_dt = datetime.fromisoformat(date_el["datetime"].replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                if not pub_dt:
                    pub_dt = datetime.now(timezone.utc)

                if pub_dt < cutoff:
                    continue

                link_el = msg.select_one("a.tgme_widget_message_date")
                msg_link = link_el["href"] if link_el and link_el.get("href") else url

                async with _seen_links_lock:
                    if msg_link in seen_links:
                        continue
                    if len(seen_links) >= MAX_SEEN_LINKS:
                        seen_links = set(list(seen_links)[-MAX_SEEN_LINKS // 2 :])
                    seen_links.add(msg_link)

                title = text.split("\n")[0][:100]
                summary = textwrap.shorten(text, width=280, placeholder="...")

                # Extract featured image from Telegram post
                photo_el = msg.select_one(".tgme_widget_message_photo_wrap")
                tg_image_url = ""
                if photo_el:
                    style = photo_el.get("style", "")
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        tg_image_url = match.group(1)

                entries.append(
                    {
                        "title": title,
                        "link": msg_link,
                        "summary": summary,
                        "published": pub_dt.isoformat(),
                        "published_dt": pub_dt,
                        "published_iso": pub_dt.isoformat(),
                        "image": tg_image_url,
                        "source": source_name,
                        "type": "telegram",
                    }
                )
            except Exception as e:
                logging.warning(f"[TELEGRAM PARSE] {source_name}: {e}")
                continue

        if skipped_no_text > 0 and len(entries) == 0:
            logging.warning(
                f"[TELEGRAM SELECTOR] {source_name}: se encontraron {len(messages)} mensajes pero todos fueron omitidos por falta de texto. ¿Ha cambiado la clase CSS de Telegram?"
            )

        entries.sort(key=lambda x: x["published_dt"], reverse=True)
        logging.info(f"[TELEGRAM] {source_name}: {len(entries)} mensajes")
        return source_name, entries

    except asyncio.TimeoutError:
        logging.warning(f"[TELEGRAM TIMEOUT] {source_name}")
        return source_name, []
    except Exception as e:
        logging.warning(f"[TELEGRAM ERROR] {source_name}: {e}")
        return source_name, []


async def fetch_external_news_async(priority_only=False):
    """Orquestador de extracción de noticias externas (RSS + Telegram)"""
    global seen_links, _seen_links_lock
    all_news = {}
    async with _seen_links_lock:
        seen_links.clear()

    # Cargar patches y preparar fuentes
    from config import PRIORITY_FEEDS

    patches = load_patches()

    # Combinar RSS + Telegram, aplicando parches
    # Si el patch es None/null → feed deshabilitado, se omite
    all_rss = {}
    for k, v in RSS_FEEDS.items():
        patched = patches.get(k, v)
        if patched is None:
            logging.info(f"[PATCH DISABLED] {k} deshabilitado en feed_patches.json")
            continue
        all_rss[k] = patched

    all_telegram = {}
    for k, v in TELEGRAM_SOURCES.items():
        patched = patches.get(k, v)
        if patched is None:
            logging.info(f"[PATCH DISABLED] {k} (Telegram) deshabilitado en feed_patches.json")
            continue
        all_telegram[k] = patched

    if priority_only:
        all_rss = {k: v for k, v in all_rss.items() if k in PRIORITY_FEEDS}
        all_telegram = {k: v for k, v in all_telegram.items() if k in PRIORITY_FEEDS}
        logging.info(f"[MODE] Prioritario: {len(all_rss)} RSS + {len(all_telegram)} Telegram")

    # Configurar SSL según variable de entorno
    ssl_context = False if not config.SSL_VERIFY else None

    connector = aiohttp.TCPConnector(limit=8, limit_per_host=2, ssl=ssl_context, use_dns_cache=True, ttl_dns_cache=300)

    async with aiohttp.ClientSession(
        timeout=REQUEST_TIMEOUT, connector=connector, headers={"Accept-Encoding": "gzip, deflate"}
    ) as session:
        # Procesar RSS en batches
        rss_items = list(all_rss.items())
        telegram_items = list(all_telegram.items())

        all_results = []

        # Procesar RSS
        for i in range(0, len(rss_items), BATCH_SIZE):
            batch = rss_items[i : i + BATCH_SIZE]
            tasks = [
                parse_single_feed_async(session, source, url, problem_info=PROBLEM_FEEDS.get(source))
                for source, url in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception):
                    logging.warning(f"[RSS SKIP] {res}")
                else:
                    all_results.append(res)

            # Delay entre batches
            if i + BATCH_SIZE < len(rss_items):
                await asyncio.sleep(random.uniform(0.1, 0.3))

        # Procesar Telegram (si hay implementación)
        for source, url in telegram_items:
            result = await fetch_telegram_source(source, url)
            all_results.append(result)

        # Consolidar resultados
        for source, entries in all_results:
            if isinstance(entries, list):
                all_news[source] = entries
                status = "OK" if entries else "VACÍO"
                logging.info(f"[{status}] {source}: {len(entries)} noticias")

    return all_news


def get_own_intel():
    if not isinstance(OWN_POSTS, (list, tuple)):
        logging.warning("OWN_POSTS no es lista/tupla")
        return []
    return list(OWN_POSTS)


def get_all_data(priority_only=False):
    """Entrada síncrona para el dashboard"""
    from utils import safe_async_run

    external = safe_async_run(fetch_external_news_async(priority_only))
    own = get_own_intel()
    return {
        "external": external,
        "own": own,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "priority" if priority_only else "full",
    }


# Para testing directo
if __name__ == "__main__":
    data = get_all_data(priority_only=True)
    print(f"Total fuentes: {len(data['external'])}")
    print(f"Posts propios: {len(data['own'])}")
