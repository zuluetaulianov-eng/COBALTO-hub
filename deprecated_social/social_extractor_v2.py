# social_extractor_v3.py - Red Team Edition 2026 (Cobalto)
# Optimización completa: RSSHub fallback, Nitter robusto, YouTube real, caché ligero
# Enfoque: fuentes públicas, anonimato y máxima estabilidad para monitoreo de amenazas

import hashlib
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import feedparser
import tls_client
from bs4 import BeautifulSoup
from lxml_html_clean import Cleaner

# DB Setup for Deduplication
DB_FILE = Path(__file__).parent / "cobalto_cache.db"
_db_lock = threading.Lock()

def _init_social_db():
    with _db_lock:
        conn = sqlite3.connect(str(DB_FILE))
        conn.execute('''
            CREATE TABLE IF NOT EXISTS social_dedup (
                hash TEXT PRIMARY KEY,
                source TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Clean old entries
        conn.execute("DELETE FROM social_dedup WHERE timestamp < datetime('now', '-7 days')")
        conn.commit()
        conn.close()

_init_social_db()

def get_tls_session():
    return tls_client.Session(
        client_identifier="chrome_120",
        random_tls_extension_order=True
    )

# ──────────────────────────────────────────────────────────────
# CLEANER OPTIMIZADO
# ──────────────────────────────────────────────────────────────
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

# ──────────────────────────────────────────────────────────────
# 1. RSS PÚBLICOS + RSSHub (mejora clave 2026)
# ──────────────────────────────────────────────────────────────
RSSHUB_BASE = "https://rsshub.app"  # Usa instancia pública o self-host para mayor control

SOCIAL_RSS_FEEDS = {
    # Venezuela
    "Reddit Venezuela": "https://www.reddit.com/r/vzla/new/.rss",
    "Reddit Venezuela2": "https://www.reddit.com/r/venezuela/new/.rss",
    "Venezuela Analysis": "https://venezuelanalysis.com/feed/",
    "Caracas Chronicles": "https://www.caracaschronicles.com/feed/",
    "El Nacional": "https://www.el-nacional.com/feed/",
    # Ciberseguridad y OSINT
    "Reddit Ciberseguridad": "https://www.reddit.com/r/ciberseguridad/new/.rss",
    "Reddit Netsec": "https://www.reddit.com/r/netsec/new/.rss",
    "Reddit OSINT": "https://www.reddit.com/r/osint/new/.rss",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "Schneier on Security": "https://www.schneier.com/feed/",
    "Dark Reading": "https://www.darkreading.com/rss.xml",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "Bleeping Computer": "https://www.bleepingcomputer.com/feed/",
    "Medium Ciberseguridad": "https://medium.com/feed/tag/ciberseguridad",
    "Medium Venezuela": "https://medium.com/feed/tag/venezuela",
}

# ──────────────────────────────────────────────────────────────
# 2. AGREGADORES PÚBLICOS
# ──────────────────────────────────────────────────────────────
PUBLIC_AGREGATORS = {
    "Hacker News": {
        "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "item_url": "https://hacker-news.firebaseio.com/v0/item/{}.json",
        "max_items": 8,
    },
    "Lobsters": {"url": "https://lobste.rs/hottest.json", "max_items": 6},
    "Slashdot": {"url": "https://slashdot.org/slashdot.rss", "type": "rss"},
}

# ──────────────────────────────────────────────────────────────
# 3. HASHTAGS (Nitter con fallback)
# ──────────────────────────────────────────────────────────────
HASHTAG_SITES = {
    "Nitter Venezuela": {
        "base_url": "https://nitter.net/search?q=%23venezuela&f=recent",
        "posts_selector": ".timeline-item",
        "max_posts": 5,
    },
    "Nitter Ciberseguridad": {
        "base_url": "https://nitter.net/search?q=%23ciberseguridad&f=recent",
        "posts_selector": ".timeline-item",
        "max_posts": 5,
    },
}

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://twitt.re",
    "https://nitter.eu",
    "https://nitter.poast.org",
    "https://nitter.it",
    "https://nitter.cz",
    "https://nitter.snopyta.org",
]

# ──────────────────────────────────────────────────────────────
# 4. CANALES PÚBLICOS
# ──────────────────────────────────────────────────────────────
PUBLIC_CHANNELS = {
    "Telegram NoticiaVenezuela": {"type": "telegram_public", "username": "notivenezuelaarma", "max_posts": 5},
    "YouTube Security": {
        "type": "youtube_rss",
        "channel_id": "UCoyH1f_T4Z0p2p1xTfGtP-A",  # Cambia por el que necesites
        "max_videos": 3,
    },
}

# ── Lock para thread-safety de caché y métricas ──
_cache_lock = threading.Lock()

# Caché simple en memoria
_cache = {}

# Performance tracking por fuente
_SOURCE_PERFORMANCE = {"avg_response_time": {}, "success_rate": {}, "last_success": {}, "timeout_history": {}}

# Timeout dinámico base por tipo de fuente
BASE_TIMEOUTS = {"rss": 8, "api": 6, "nitter": 12, "telegram": 10, "youtube": 8}


def _get_adaptive_timeout(source_type: str, source_name: str) -> int:
    """Timeout adaptativo basado en rendimiento histórico"""
    base_timeout = BASE_TIMEOUTS.get(source_type, 10)

    with _cache_lock:
        if source_name in _SOURCE_PERFORMANCE["avg_response_time"]:
            times = _SOURCE_PERFORMANCE["avg_response_time"][source_name]
            avg_time = sum(times) / len(times) if times else 0
            success_rate = _SOURCE_PERFORMANCE["success_rate"].get(source_name, 1.0)

            # Si es rápido y confiable, reducimos timeout
            if avg_time < 2 and success_rate > 0.8:
                return max(4, int(base_timeout * 0.7))
            # Si es lento o poco confiable, aumentamos
            elif avg_time > 8 or success_rate < 0.5:
                return min(20, int(base_timeout * 1.5))

    return base_timeout


def _update_performance_metrics(source_name: str, response_time: float, success: bool):
    """Actualiza métricas de rendimiento (thread-safe)"""
    with _cache_lock:
        if source_name not in _SOURCE_PERFORMANCE["avg_response_time"]:
            _SOURCE_PERFORMANCE["avg_response_time"][source_name] = []
            _SOURCE_PERFORMANCE["success_rate"][source_name] = 1.0
            _SOURCE_PERFORMANCE["timeout_history"][source_name] = []

        # Actualizar tiempo de respuesta
        times = _SOURCE_PERFORMANCE["avg_response_time"][source_name]
        times.append(response_time)
        if len(times) > 10:
            times.pop(0)

        # Actualizar tasa de éxito (ventana deslizante)
        history = _SOURCE_PERFORMANCE["timeout_history"][source_name]
        history.append(1 if success else 0)
        if len(history) > 20:
            history.pop(0)

        _SOURCE_PERFORMANCE["success_rate"][source_name] = sum(history) / len(history)

        if success:
            _SOURCE_PERFORMANCE["last_success"][source_name] = time.time()


def _cache_cleanup(now: float):
    """Limpia entradas expiradas del caché (debe llamarse con _cache_lock held)"""
    expired = [k for k, v in _cache.items() if now - v["time"] > 600]
    for k in expired:
        del _cache[k]


def _get_with_cache(url: str, timeout=12, ttl=300, source_type="rss", source_name="unknown"):
    """Cache ligero con timeout adaptativo y métricas"""
    start_time = time.time()
    key = hashlib.md5(url.encode()).hexdigest()
    now = time.time()

    with _cache_lock:
        _cache_cleanup(now)
        if key in _cache and now - _cache[key]["time"] < ttl:
            return _cache[key]["data"]

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; CobaltoRedTeam/3.0)"}
        session = get_tls_session()
        resp = session.get(url, headers=headers, timeout_seconds=timeout)

        if resp.status_code >= 400:
            _update_performance_metrics(source_name, time.time() - start_time, False)
            return None

        if not resp.content:
            _update_performance_metrics(source_name, time.time() - start_time, False)
            return None

        content_type = resp.headers.get("content-type", "").lower()
        if "xml" in content_type or "rss" in url:
            data = resp.content
        else:
            try:
                data = resp.json()
            except json.JSONDecodeError:
                _update_performance_metrics(source_name, time.time() - start_time, False)
                return None

        with _cache_lock:
            _cache[key] = {"data": data, "time": now}

        # Actualizar métricas de éxito
        response_time = time.time() - start_time
        _update_performance_metrics(source_name, response_time, True)

        return data

    except Exception:
        # Actualizar métricas de fallo
        response_time = time.time() - start_time
        _update_performance_metrics(source_name, response_time, False)
        return None


# ──────────────────────────────────────────────────────────────
# FUNCIONES DE EXTRACCIÓN (nombres originales mantenidos)
# ──────────────────────────────────────────────────────────────

# Sistema de deduplicación (protegido por _cache_lock)
_CONTENT_SEEN = set()
_CONTENT_HASHES = {}  # hash -> source_name para tracking


def _generate_content_hash(title: str, link: str, summary: str) -> str:
    """Genera hash único para deduplicación"""
    content = f"{title.lower().strip()}|{link.lower().strip()}|{summary[:100].lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()


def _is_duplicate(item: Dict) -> bool:
    """Verifica si el contenido ya fue procesado usando SQLite para memoria compartida"""
    content_hash = _generate_content_hash(item.get("title", ""), item.get("link", ""), item.get("summary", ""))

    with _db_lock:
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cur = conn.cursor()
            cur.execute("SELECT source FROM social_dedup WHERE hash = ?", (content_hash,))
            row = cur.fetchone()
            if row:
                print(f"[DUPLICATE] '{item.get('title', '')[:50]}...' ya visto en {row[0]}")
                conn.close()
                return True

            cur.execute("INSERT INTO social_dedup (hash, source) VALUES (?, ?)", (content_hash, item.get("source", "unknown")))
            conn.commit()
            conn.close()
            return False
        except Exception as e:
            print(f"[DB ERROR] Deduplicación falló: {e}")
            return False


def _extract_rss_feed(name: str, url: str, max_items: int = 6) -> List[Dict]:
    """Extrae RSS con fallback a RSSHub y deduplicación"""
    timeout = _get_adaptive_timeout("rss", name)

    try:
        # Usar cache con timeout adaptativo
        feed_data = _get_with_cache(url, timeout=timeout, ttl=300, source_type="rss", source_name=name)
        if feed_data is None:
            return []

        feed = feedparser.parse(feed_data)
        if not feed.entries and RSSHUB_BASE not in url.lower():
            # Fallback RSSHub
            clean_url = url.replace("https://", "").replace("http://", "")
            rsshub_url = f"{RSSHUB_BASE}/rss/{clean_url}"
            feed_data = _get_with_cache(rsshub_url, timeout=timeout, source_type="rss", source_name=f"{name}_rsshub")
            if feed_data:
                feed = feedparser.parse(feed_data)

        items = []
        for entry in feed.entries[:max_items]:
            summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
            summary = cleaner.clean(summary_raw)
            summary = BeautifulSoup(summary, "html.parser").get_text()[:300]

            image = None
            if hasattr(entry, "media_content") and entry.media_content:
                image = entry.media_content[0].get("url")

            item = {
                "title": entry.title[:140] if hasattr(entry, "title") else "Sin título",
                "summary": summary,
                "link": getattr(entry, "link", "#"),
                "published": getattr(entry, "published", "Reciente"),
                "image": image,
                "source": name,
                "author": getattr(entry, "author", "Anónimo"),
            }

            # Deduplicación
            if not _is_duplicate(item):
                items.append(item)

        return items
    except Exception as e:
        print(f"[ERROR] RSS {name}: {str(e)}")
        return []


def _extract_hacker_news() -> List[Dict]:
    """Hacker News API pública con timeout adaptativo"""
    timeout = _get_adaptive_timeout("api", "Hacker News")

    try:
        data = _get_with_cache(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=timeout,
            source_type="api",
            source_name="Hacker News",
        )
        if not data:
            return []

        story_ids = data[:8]
        items = []
        for story_id in story_ids:
            try:
                story = _get_with_cache(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=timeout // 2,
                    source_type="api",
                    source_name=f"Hacker News_{story_id}",
                )
                if story and story.get("type") == "story" and story.get("url"):
                    item = {
                        "title": story.get("title", "")[:140],
                        "summary": story.get("text", "")[:300]
                        or f"Score: {story.get('score', 0)} | Comentarios: {story.get('descendants', 0)}",
                        "link": story.get("url"),
                        "published": datetime.fromtimestamp(story.get("time", 0)).strftime("%Y-%m-%d %H:%M"),
                        "image": None,
                        "source": "Hacker News",
                        "score": story.get("score", 0),
                    }

                    # Deduplicación
                    if not _is_duplicate(item):
                        items.append(item)

            except Exception:
                continue
        return items
    except Exception as e:
        print(f"[ERROR] Hacker News: {str(e)}")
        return []


def _extract_nitter_posts(site_config: Dict) -> List[Dict]:
    """Nitter con 8 instancias de respaldo y timeout adaptativo"""
    timeout = _get_adaptive_timeout("nitter", site_config.get("name", "Nitter"))

    for i, base in enumerate(NITTER_INSTANCES):
        url = site_config["base_url"].replace("https://nitter.net", base)
        try:
            start_time = time.time()
            session = get_tls_session()
            response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout_seconds=timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                posts = soup.select(site_config["posts_selector"])[: site_config["max_posts"]]
                items = []

                for post in posts:
                    try:
                        content_elem = post.select_one(".tweet-content") or post.select_one(".tweet-text")
                        content = content_elem.get_text().strip()[:280] if content_elem else ""
                        if not content:
                            continue

                        link_elem = post.select_one(".tweet-link")
                        link = link_elem.get("href") if link_elem else "#"
                        author_elem = post.select_one(".username")
                        author = author_elem.get_text().strip() if author_elem else "Anónimo"

                        item = {
                            "title": content[:140],
                            "summary": content,
                            "link": link,
                            "published": "Reciente",
                            "image": None,
                            "source": f"X @{author}",
                            "author": author,
                        }

                        # Deduplicación
                        if not _is_duplicate(item):
                            items.append(item)

                    except Exception:
                        continue

                # Actualizar métricas de éxito para esta instancia
                instance_name = f"Nitter_{i}_{base.split('//')[1].split('.')[0]}"
                _update_performance_metrics(instance_name, response_time, True)

                if items:
                    print(f"[OK] Nitter instancia {i + 1}/8 ({base}): {len(items)} items en {response_time:.1f}s")
                    return items

            else:
                # Actualizar métricas de fallo
                instance_name = f"Nitter_{i}_{base.split('//')[1].split('.')[0]}"
                _update_performance_metrics(instance_name, response_time, False)

        except Exception:
            # Actualizar métricas de fallo
            instance_name = f"Nitter_{i}_{base.split('//')[1].split('.')[0]}"
            _update_performance_metrics(instance_name, timeout, False)
            continue

    print(f"[FALLBACK] Todas las 8 instancias Nitter fallaron para {site_config['base_url']}")
    return []


def _extract_telegram_public(channel_config: Dict) -> List[Dict]:
    """Telegram vía RSSHub con timeout adaptativo"""
    username = channel_config["username"]
    rss_url = f"{RSSHUB_BASE}/telegram/channel/{username}"
    _get_adaptive_timeout("telegram", f"Telegram_{username}")
    return _extract_rss_feed(f"Telegram @{username}", rss_url, channel_config["max_posts"])


def _extract_youtube_rss(config: Dict) -> List[Dict]:
    """YouTube RSS oficial con timeout adaptativo"""
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={config['channel_id']}"
    _get_adaptive_timeout("youtube", f"YouTube_{config['channel_id']}")
    return _extract_rss_feed("YouTube Security", rss_url, config["max_videos"])


# ──────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────


def get_social_data_v2() -> Dict[str, Any]:
    """Versión optimizada v3 - Compatible con dashboard"""
    social_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": {},
        "count": 0,
        "method": "public_apis_v3_redteam_cobalto",
    }

    print("[COBALTO] Iniciando extracción social v3 - Modo Red Team activado")
    print(f"[INFO] Instancias Nitter: {len(NITTER_INSTANCES)} | Cache TTL: 5 min | Deduplicación: ACTIVA")

    # Limpiar cache de duplicados para cada ejecución
    global _CONTENT_SEEN, _CONTENT_HASHES
    with _cache_lock:
        _CONTENT_SEEN.clear()
        _CONTENT_HASHES.clear()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        # RSS feeds
        for name, url in SOCIAL_RSS_FEEDS.items():
            futures.append(("rss", name, executor.submit(_extract_rss_feed, name, url, 5)))

        # Hacker News
        futures.append(("api", "Hacker News", executor.submit(_extract_hacker_news)))

        # Nitter
        for name, config in HASHTAG_SITES.items():
            futures.append(("nitter", name, executor.submit(_extract_nitter_posts, config)))

        # Canales públicos
        for name, config in PUBLIC_CHANNELS.items():
            if config["type"] == "telegram_public":
                futures.append(("telegram", name, executor.submit(_extract_telegram_public, config)))
            elif config["type"] == "youtube_rss":
                futures.append(("youtube", name, executor.submit(_extract_youtube_rss, config)))

        # Recolectar resultados
        for source_type, source_name, future in futures:
            try:
                items = future.result(timeout=20)
                if items:
                    social_data["sources"][source_name] = items
                    social_data["count"] += len(items)
                    print(f"[OK] {source_name}: {len(items)} items ({source_type})")
                else:
                    print(f"[VACÍO] {source_name}")
            except Exception as e:
                print(f"[ERROR] {source_name}: {str(e)}")

    print(f"[TOTAL] {social_data['count']} items únicos capturados de {len(social_data['sources'])} fuentes")

    # Mostrar estadísticas de rendimiento
    with _cache_lock:
        if _SOURCE_PERFORMANCE["success_rate"]:
            print("\n[PERFORMANCE] Top fuentes por tasa de éxito:")
            sorted_sources = sorted(_SOURCE_PERFORMANCE["success_rate"].items(), key=lambda x: x[1], reverse=True)[:5]
            for source, rate in sorted_sources:
                avg_time = _SOURCE_PERFORMANCE["avg_response_time"].get(source, [0])
                avg_time = sum(avg_time) / len(avg_time) if avg_time else 0
                print(f"   • {source}: {rate:.1%} | {avg_time:.1f}s avg")

    return social_data


def get_social_data():
    """Alias para compatibilidad con otros scripts"""
    return get_social_data_v2()


def generate_html_content(sources):
    """Generate HTML content from sources data"""
    html_parts = []
    for src, items in sources.items():
        items_html = "".join(
            [f"<p><strong>{item.get('title', '')}</strong><br>{item.get('summary', '')}</p>" for item in items]
        )
        html_parts.append(f"<div class='item'><h3>{src}</h3>{items_html}</div>")
    return "".join(html_parts)


# ──────────────────────────────────────────────────────────────
# MODO TEST + EXPORT HTML CYBERPUNK
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data = get_social_data_v2()

    # Exportar a HTML (preparado para tu diseño cyberpunk)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Social Extractor v3 - Cobalto Red Team</title>
        <style>
            body {{ background: #0a0a1f; color: #00ffcc; font-family: 'Courier New', monospace; }}
            h1 {{ text-shadow: 0 0 10px #00ffcc; }}
            .item {{ border: 1px solid #00ffcc; padding: 10px; margin: 10px 0; background: rgba(0,255,204,0.05); }}
        </style>
    </head>
    <body>
        <h1>Social Extractor v3 - {data["timestamp"]}</h1>
        <p>Total: {data["count"]} items</p>
        {generate_html_content(data["sources"])}
    </body>
    </html>
    """

    with open("social_dashboard_v3.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("[OK] Archivo social_dashboard_v3.html generado con estilo cyberpunk básico")
    print(json.dumps(data, indent=2, ensure_ascii=False))
