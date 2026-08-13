# tiktok_extractor.py - Extracción de contenido de TikTok para OSINT
# Versión 1.1 - Circuit breaker para evitar reintentos en bucle

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List

from social_public_extractor import safe_get

# Circuit breaker: si todos los hashtags fallan, no reintentar por 30 min
_tiktok_cb = {"failures": 0, "last_fail": 0.0}
_TIKTOK_CB_THRESHOLD = 1
_TIKTOK_CB_RECOVERY = 1800


def _is_tiktok_available() -> bool:
    if _tiktok_cb["failures"] >= _TIKTOK_CB_THRESHOLD:
        if time.time() - _tiktok_cb["last_fail"] > _TIKTOK_CB_RECOVERY:
            _tiktok_cb["failures"] = 0
            return True
        return False
    return True


# ==========================================
# TIKTOK - Hashtags relevantes a Venezuela
# ==========================================
TIKTOK_HASHTAGS = [
    "#Venezuela",
    "#NoticiasVenezuela",
    "#PoliticaVenezuela",
    "#EconomiaVenezuela",
    "#CrisisVenezuela",
    "#DolarVenezuela",
    "#Maduro",
    "#MariaCorinaMachado",
    "#OposicionVenezuela",
    "#Vzla",
    "#Venezolanos",
    "#MigracionVenezuela",
    "#CrisisHumanitaria",
    "#PetroleoVenezuela",
    "#PDVSA",
    "#SancionesVenezuela",
]

# ==========================================
# TIKTOK - Perfiles de medios y políticos
# ==========================================
TIKTOK_PROFILES = [
    "@efectococuyo",
    "@elnacionalweb",
    "@lapatilla",
    "@runrunes",
    "@nicolasmaduro",
    "@mariacorinamachado",
    "@juan_guaido",
    "@jorgerodriguezve",
]


def _extract_sigma_data(html: str) -> dict:
    """Extrae el objeto Sigma de la página (window.__SIGMA_STATE__)"""
    m = re.search(r"window\.__SIGMA_STATE__\s*=\s*", html)
    if not m:
        return {}
    start = m.end()
    depth = 0
    for i in range(start, len(html)):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    pass
                break
    return {}


def _tiktok_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.tiktok.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


def scrape_tiktok_hashtag(hashtag: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Scraping de hashtags de TikTok vía la página web pública.
    Primero obtiene la página del tag y extrae datos del SSR.
    """
    results = []
    try:
        tag = hashtag.lstrip("#")
        url = f"https://www.tiktok.com/tag/{tag}"
        import requests as _req

        try:
            resp = _req.get(url, headers=_tiktok_headers(), timeout=15, allow_redirects=True)
        except Exception:
            resp = safe_get(url)

        if resp is None or resp.status_code != 200:
            print(f"[TIKTOK] HTTP {getattr(resp, 'status_code', 'N/A')} para #{tag}")
            _tiktok_cb["failures"] = _TIKTOK_CB_THRESHOLD
            _tiktok_cb["last_fail"] = time.time()
            return results

        html = resp.text
        if not html or len(html) < 200:
            print(f"[TIKTOK] Respuesta vacía o demasiado corta para #{tag}")
            _tiktok_cb["failures"] = _TIKTOK_CB_THRESHOLD
            _tiktok_cb["last_fail"] = time.time()
            return results
        if "<html>" not in html.lower():
            print(f"[TIKTOK] Respuesta no contiene HTML (posible bloqueo) para #{tag}")
            _tiktok_cb["failures"] = _TIKTOK_CB_THRESHOLD
            _tiktok_cb["last_fail"] = time.time()
            return results

        # Intentar extraer datos embebidos desde window.__SIGMA_STATE__
        sigma = _extract_sigma_data(html)
        if sigma:
            items = _parse_sigma_items(sigma, limit)
            if items:
                return items

        # Fallback: buscar JSON-LD o datos inline
        _id = 0
        for match in re.finditer(
            r'"id":"(\d+)".*?"desc":"((?:[^"\\]|\\.)*)"',
            html,
        ):
            video_id, desc = match.group(1), match.group(2)
            if len(desc) > 300:
                continue
            results.append(
                {
                    "title": desc[:140] if desc else "Sin descripción",
                    "summary": desc[:280],
                    "link": f"https://www.tiktok.com/@user/video/{video_id}",
                    "published": datetime.now().isoformat(),
                    "source": f"TikTok #{tag}",
                    "type": "tiktok",
                    "author": "",
                    "views": 0,
                    "likes": 0,
                    "shares": 0,
                }
            )
            _id += 1
            if _id >= limit:
                break
    except Exception as e:
        print(f"[WARN] TikTok hashtag scraper error: {e}")

    return results


def _parse_sigma_items(sigma: dict, limit: int) -> List[Dict[str, Any]]:
    results = []
    # Sigma state structure: { "App": { "main": { "module": { "data": [...] } } } }
    try:
        data = sigma.get("App", {}).get("main", {})
        modules = ["tag", "search"]
        for mod_key in modules:
            module_data = data.get(mod_key, {})
            if isinstance(module_data, dict):
                items = module_data.get("data", module_data.get("items", []))
                if isinstance(items, list):
                    for item in items[:limit]:
                        video = item.get("item", item) if isinstance(item, dict) else {}
                        desc = video.get("desc", "")
                        author = video.get("author", {}) or {}
                        stats = video.get("stats", {}) or {}
                        uid = ""
                        if isinstance(author, dict):
                            uid = author.get("uniqueId", "")
                        results.append(
                            {
                                "title": desc[:140] if desc else "Sin descripción",
                                "summary": desc[:280],
                                "link": f"https://www.tiktok.com/@{uid}/video/{video.get('id', '')}",
                                "published": datetime.now().isoformat(),
                                "source": "TikTok",
                                "type": "tiktok",
                                "author": author.get("nickname", "") if isinstance(author, dict) else "",
                                "views": stats.get("playCount", 0),
                                "likes": stats.get("diggCount", 0),
                                "shares": stats.get("shareCount", 0),
                            }
                        )
    except Exception as e:
        print(f"[TIKTOK] Error parseando sigma state: {e}")
    return results


def get_tiktok_all() -> List[Dict[str, Any]]:
    """Extrae de todos los hashtags configurados"""
    if not _is_tiktok_available():
        return []
    results = []
    for hashtag in TIKTOK_HASHTAGS:
        if not _is_tiktok_available():
            break
        items = scrape_tiktok_hashtag(hashtag)
        results.extend(items)
    if not results:
        _tiktok_cb["failures"] = max(_tiktok_cb["failures"] + 1, _TIKTOK_CB_THRESHOLD)
        _tiktok_cb["last_fail"] = time.time()
    else:
        _tiktok_cb["failures"] = 0
    return results


def scrape_tiktok_profile(username: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Scraping de perfil específico de TikTok vía SSR de la página web"""
    results = []
    try:
        url = f"https://www.tiktok.com/@{username}"
        import requests as _req

        try:
            resp = _req.get(url, headers=_tiktok_headers(), timeout=15, allow_redirects=True)
        except Exception:
            resp = safe_get(url)

        if resp is None or resp.status_code != 200:
            print(f"[TIKTOK] HTTP {getattr(resp, 'status_code', 'N/A')} para @{username}")
            _tiktok_cb["failures"] = _TIKTOK_CB_THRESHOLD
            _tiktok_cb["last_fail"] = time.time()
            return results

        html = resp.text
        if not html or len(html) < 200:
            _tiktok_cb["failures"] = _TIKTOK_CB_THRESHOLD
            _tiktok_cb["last_fail"] = time.time()
            return results
        if "<html>" not in html.lower():
            _tiktok_cb["failures"] = _TIKTOK_CB_THRESHOLD
            _tiktok_cb["last_fail"] = time.time()
            return results

        # Intentar extraer datos embebidos desde window.__SIGMA_STATE__
        sigma = _extract_sigma_data(html)
        if sigma:
            items = _parse_sigma_items(sigma, limit)
            if items:
                return items

        # Fallback regex para extraer IDs y descripciones del HTML
        video_pattern = r'"id":"(\d+)".*?"desc":"((?:[^"\\]|\\.)*)"'
        matches = re.findall(video_pattern, html)

        for video_id, desc in matches[:limit]:
            if len(desc) > 300:
                continue
            results.append(
                {
                    "title": desc[:140] if desc else "Sin descripción",
                    "summary": desc[:280],
                    "link": f"https://www.tiktok.com/@{username}/video/{video_id}",
                    "published": datetime.now().isoformat(),
                    "source": f"TikTok @{username}",
                    "type": "tiktok_profile",
                }
            )
    except Exception as e:
        print(f"[WARN] TikTok profile scraper error: {e}")

    return results


def get_tiktok_profiles() -> List[Dict[str, Any]]:
    """Extrae de todos los perfiles configurados"""
    if not _is_tiktok_available():
        return []
    results = []
    for profile in TIKTOK_PROFILES:
        if not _is_tiktok_available():
            break
        items = scrape_tiktok_profile(profile)
        results.extend(items)
    if not results:
        _tiktok_cb["failures"] = max(_tiktok_cb["failures"] + 1, _TIKTOK_CB_THRESHOLD)
        _tiktok_cb["last_fail"] = time.time()
    else:
        _tiktok_cb["failures"] = 0
    return results
