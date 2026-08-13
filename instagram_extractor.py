# instagram_extractor.py - Extracción de contenido de Instagram para OSINT
# Versión 1.1 - Circuit breaker (endpoint ?__a=1 permanentemente deprecado)

import time
from datetime import datetime
from typing import Any, Dict, List

from social_public_extractor import safe_get

# Circuit breaker: Instagram deprecó ?__a=1, falla siempre
_ig_cb = {"failures": 0, "last_fail": 0.0}
_IG_CB_THRESHOLD = 1
_IG_CB_RECOVERY = 3600


def _is_ig_available() -> bool:
    if _ig_cb["failures"] >= _IG_CB_THRESHOLD:
        if time.time() - _ig_cb["last_fail"] > _IG_CB_RECOVERY:
            _ig_cb["failures"] = 0
            return True
        return False
    return True


# ==========================================
# INSTAGRAM - Hashtags relevantes a Venezuela
# ==========================================
INSTAGRAM_HASHTAGS = [
    "#venezuela",
    "#noticiasvenezuela",
    "#politicavenezuela",
    "#economíavenezuela",
    "#crisisvenezuela",
    "#dolarvenezuela",
    "#maduro",
    "#mariacorinamachado",
    "#oposicionvenezuela",
    "#vzla",
    "#venezolanos",
    "#migracionvenezuela",
    "#crisishumanitaria",
    "#petroleo",
    "#pdvsa",
    "#sanciones",
]

# ==========================================
# INSTAGRAM - Perfiles de medios y políticos
# ==========================================
INSTAGRAM_PROFILES = [
    "elnacionalweb",
    "efectococuyo",
    "lapatilla",
    "runrunes",
    "ultimasnoticias",
    "diariolosandes",
    "elcarabobeno",
]


def scrape_instagram_hashtag(hashtag: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Scraping de Instagram vía API web (sin autenticación)
    Nota: Instagram requiere login para la mayoría de endpoints
    Este es un enfoque simplificado que puede requerir actualizaciones frecuentes
    """
    results = []
    try:
        # Instagram GraphQL API (público pero con limitaciones)
        url = f"https://www.instagram.com/explore/tags/{hashtag}/?__a=1&__d=dis"

        resp = safe_get(url)
        if resp is None or resp.status_code != 200:
            _ig_cb["failures"] = _IG_CB_THRESHOLD
            _ig_cb["last_fail"] = time.time()
            return results
        try:
            data = resp.json()
            if not data.get("graphql"):
                print(f"[INSTAGRAM] API endpoint ?__a=1 deprecado para #{hashtag}. Instagram requiere login.")
                _ig_cb["failures"] = _IG_CB_THRESHOLD
                _ig_cb["last_fail"] = time.time()
                return results
            hashtag_data = data["graphql"]["hashtag"]
            edge_data = hashtag_data.get("edge_hashtag_to_media", {})
            edges = edge_data.get("edges", [])

            for edge in edges[:limit]:
                node = edge.get("node", {})
                caption = node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")
                display_url = node.get("display_url", "")
                likes = node.get("edge_liked_by", {}).get("count", 0)
                comments = node.get("edge_media_to_comment", {}).get("count", 0)

                results.append(
                    {
                        "title": caption[:140] if caption else f"Post #{hashtag}",
                        "summary": caption[:280],
                        "link": f"https://www.instagram.com/p/{node.get('shortcode', '')}/",
                        "published": datetime.now().isoformat(),
                        "source": f"Instagram #{hashtag}",
                        "type": "instagram",
                        "image": display_url,
                        "likes": likes,
                        "comments": comments,
                    }
                )
        except ValueError:
            print(f"[INSTAGRAM] Respuesta no JSON para #{hashtag}. Endpoint ?__a=1 puede estar deprecado.")
            _ig_cb["failures"] = _IG_CB_THRESHOLD
            _ig_cb["last_fail"] = time.time()
    except Exception as e:
        print(f"[WARN] Instagram scraper error: {e}")

    return results


def get_instagram_all() -> List[Dict[str, Any]]:
    """Extrae de todos los hashtags configurados"""
    if not _is_ig_available():
        return []
    results = []
    for hashtag in INSTAGRAM_HASHTAGS:
        if not _is_ig_available():
            break
        items = scrape_instagram_hashtag(hashtag)
        results.extend(items)
    if not results:
        _ig_cb["failures"] = max(_ig_cb["failures"] + 1, _IG_CB_THRESHOLD)
        _ig_cb["last_fail"] = time.time()
    else:
        _ig_cb["failures"] = 0
    return results


def scrape_instagram_profile(username: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Scraping de perfil específico de Instagram"""
    results = []
    try:
        url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"

        resp = safe_get(url)
        if resp is None or resp.status_code != 200:
            _ig_cb["failures"] = _IG_CB_THRESHOLD
            _ig_cb["last_fail"] = time.time()
            return results
        try:
            data = resp.json()
            if not data.get("graphql") or not data["graphql"].get("user"):
                print(f"[INSTAGRAM] API ?__a=1 deprecado para @{username}")
                _ig_cb["failures"] = _IG_CB_THRESHOLD
                _ig_cb["last_fail"] = time.time()
                return results
            user_data = data["graphql"]["user"]
            edge_data = user_data.get("edge_owner_to_timeline_media", {})
            edges = edge_data.get("edges", [])

            for edge in edges[:limit]:
                node = edge.get("node", {})
                caption = node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")
                display_url = node.get("display_url", "")
                likes = node.get("edge_liked_by", {}).get("count", 0)
                comments = node.get("edge_media_to_comment", {}).get("count", 0)

                results.append(
                    {
                        "title": caption[:140] if caption else f"Post @{username}",
                        "summary": caption[:280],
                        "link": f"https://www.instagram.com/p/{node.get('shortcode', '')}/",
                        "published": datetime.now().isoformat(),
                        "source": f"Instagram @{username}",
                        "type": "instagram_profile",
                        "image": display_url,
                        "likes": likes,
                        "comments": comments,
                    }
                )
        except ValueError:
            print(f"[INSTAGRAM] Respuesta no JSON para @{username}. Endpoint ?__a=1 deprecado.")
            _ig_cb["failures"] = _IG_CB_THRESHOLD
            _ig_cb["last_fail"] = time.time()
    except Exception as e:
        print(f"[WARN] Instagram profile scraper error: {e}")

    return results


def get_instagram_profiles() -> List[Dict[str, Any]]:
    """Extrae de todos los perfiles configurados"""
    if not _is_ig_available():
        return []
    results = []
    for profile in INSTAGRAM_PROFILES:
        if not _is_ig_available():
            break
        items = scrape_instagram_profile(profile)
        results.extend(items)
    if not results:
        _ig_cb["failures"] = max(_ig_cb["failures"] + 1, _IG_CB_THRESHOLD)
        _ig_cb["last_fail"] = time.time()
    else:
        _ig_cb["failures"] = 0
    return results
