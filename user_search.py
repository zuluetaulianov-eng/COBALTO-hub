# user_search.py - Búsqueda de usuarios en redes sociales para OSINT
# Versión 2.0 - Búsqueda multi-plataforma con humanización anti-bloqueo
# Versión 2.1 - Monitor de cambios en perfiles de targets

import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from config import KEYWORDS
from humanization import get_humanization_stats, safe_humanized_get

# ==========================================
# CONFIGURACIÓN DE BÚSQUEDA
# ==========================================

# Patrones comunes de usernames
USERNAME_PATTERNS = {
    "twitter": r"https?://(www\.)?twitter\.com/([a-zA-Z0-9_]{1,15})",
    "instagram": r"https?://(www\.)?instagram\.com/([a-zA-Z0-9_.]{1,30})",
    "facebook": r"https?://(www\.)?facebook\.com/([a-zA-Z0-9.]{5,50})",
    "linkedin": r"https?://(www\.)?linkedin\.com/in/([a-zA-Z0-9-]{5,30})",
    "youtube": r"https?://(www\.)?youtube\.com/(@?[a-zA-Z0-9_-]{1,50})",
    "tiktok": r"https?://(www\.)?tiktok\.com/@([a-zA-Z0-9_.]{1,30})",
    "telegram": r"https?://t\.me/([a-zA-Z0-9_]{5,32})",
}


# ==========================================
# BÚSQUEDA EN TWITTER/X
# ==========================================
def search_twitter_user(username: str) -> Dict[str, Any]:
    """Busca usuario en Twitter/X con humanización anti-bloqueo"""
    try:
        # Twitter API v2 requiere autenticación
        # Fallback: scraping del perfil público
        url = f"https://twitter.com/{username}"

        # Usar petición humanizada
        resp = safe_humanized_get(url, platform="twitter", timeout=15)
        if resp.status_code == 200:
            # Extraer datos del perfil
            name_pattern = r"<title>(.*?) \(@" + re.escape(username) + r"\)"
            bio_pattern = r'<div[^>]*data-testid="UserDescription">(.*?)</div>'
            followers_pattern = r'followers_count":(\d+)'

            name_match = re.search(name_pattern, resp.text)
            bio_match = re.search(bio_pattern, resp.text, re.DOTALL)
            followers_match = re.search(followers_pattern, resp.text)

            return {
                "platform": "Twitter/X",
                "username": username,
                "name": name_match.group(1) if name_match else username,
                "bio": bio_match.group(1).strip() if bio_match else "No disponible",
                "followers": int(followers_match.group(1)) if followers_match else 0,
                "url": url,
                "found": True,
                "searched_at": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"[WARN] Twitter search error: {e}")

    # Fallback: Intentar vía Nitter (mejor para posts)
    try:
        nitter_instances = ["nitter.net", "nitter.cz", "nitter.it"]
        instance = nitter_instances[0]
        url = f"https://{instance}/{username}"
        resp = safe_humanized_get(url, platform="twitter", timeout=15)
        if resp.status_code == 200:
            # Extraer posts básicos de Nitter
            tweet_pattern = r'<div class="tweet-content[^>]*>(.*?)</div>'
            tweets = re.findall(tweet_pattern, resp.text, re.DOTALL)

            matches = []
            for t in tweets:
                clean_t = re.sub(r"<[^>]+>", "", t).strip()
                if any(k.lower() in clean_t.lower() for k in KEYWORDS):
                    matches.append(clean_t[:150] + "...")

            return {
                "platform": "Twitter/X (Nitter)",
                "username": username,
                "found": True,
                "posts_checked": len(tweets),
                "matches": matches,
                "url": f"https://twitter.com/{username}",
            }
    except Exception:
        pass

    return {"platform": "Twitter/X", "username": username, "found": False, "searched_at": datetime.now().isoformat()}


# ==========================================
# BÚSQUEDA EN INSTAGRAM
# ==========================================
def search_instagram_user(username: str) -> Dict[str, Any]:
    """Busca usuario en Instagram con web scraping de metadatos públicos"""
    try:
        url = f"https://www.instagram.com/{username}/"
        resp = safe_humanized_get(url, platform="instagram", timeout=20)
        if resp.status_code == 200 and resp.text:
            name_match = re.search(r'<meta property="og:title" content="([^"]+)"', resp.text)
            desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', resp.text)
            jsonld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.DOTALL)
            followers = 0
            if jsonld_match:
                import json

                try:
                    ld = json.loads(jsonld_match.group(1))
                    if isinstance(ld, dict):
                        followers = (
                            int(ld.get("interactionStatistic", [{}])[0].get("userInteractionCount", 0))
                            if isinstance(ld.get("interactionStatistic"), list)
                            else 0
                        )
                except (json.JSONDecodeError, IndexError, ValueError):
                    pass
            if name_match or desc_match:
                full_text = name_match.group(1) if name_match else ""
                desc = desc_match.group(1) if desc_match else ""
                return {
                    "platform": "Instagram",
                    "username": username,
                    "name": re.sub(r"\s*\(@\w+\)\s*", "", full_text).strip(),
                    "bio": desc,
                    "followers": followers,
                    "url": url,
                    "found": True,
                    "searched_at": datetime.now().isoformat(),
                }
    except Exception as e:
        print(f"[WARN] Instagram search error: {e}")

    return {"platform": "Instagram", "username": username, "found": False, "searched_at": datetime.now().isoformat()}


# ==========================================
# BÚSQUEDA EN TELEGRAM
# ==========================================
def search_telegram_user(username: str) -> Dict[str, Any]:
    """Busca usuario en Telegram con humanización anti-bloqueo"""
    try:
        url = f"https://t.me/{username}"

        # Usar petición humanizada
        resp = safe_humanized_get(url, platform="telegram", timeout=15)
        if resp.status_code == 200:
            # Extraer datos del perfil
            name_pattern = r'<meta property="og:title" content="([^"]+)"'
            description_pattern = r'<meta property="og:description" content="([^"]+)"'

            name_match = re.search(name_pattern, resp.text)
            desc_match = re.search(description_pattern, resp.text)

            # Extraer últimos mensajes de la vista pública
            msg_pattern = r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>'
            messages = re.findall(msg_pattern, resp.text, re.DOTALL)

            matches = []
            for m in messages:
                clean_m = re.sub(r"<[^>]+>", "", m).strip()
                if any(k.lower() in clean_m.lower() for k in KEYWORDS):
                    matches.append(clean_m[:150] + "...")

            return {
                "platform": "Telegram",
                "username": username,
                "name": name_match.group(1) if name_match else username,
                "bio": desc_match.group(1) if desc_match else "No disponible",
                "url": url,
                "found": True,
                "matches": matches,
                "searched_at": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"[WARN] Telegram search error: {e}")

    return {"platform": "Telegram", "username": username, "found": False, "searched_at": datetime.now().isoformat()}


# ==========================================
# BÚSQUEDA EN TIKTOK
# ==========================================
def search_tiktok_user(username: str) -> Dict[str, Any]:
    """Busca usuario en TikTok con humanización anti-bloqueo"""
    try:
        url = f"https://www.tiktok.com/@{username}"

        # Usar petición humanizada
        resp = safe_humanized_get(url, platform="tiktok", timeout=20)
        if resp.status_code == 200:
            # Extraer datos del perfil
            name_pattern = r'"nickname":"([^"]+)"'
            bio_pattern = r'"desc":"([^"]+)"'
            followers_pattern = r'"followerCount":(\d+)'

            name_match = re.search(name_pattern, resp.text)
            bio_match = re.search(bio_pattern, resp.text)
            followers_match = re.search(followers_pattern, resp.text)

            return {
                "platform": "TikTok",
                "username": username,
                "name": name_match.group(1) if name_match else username,
                "bio": bio_match.group(1) if bio_match else "No disponible",
                "followers": int(followers_match.group(1)) if followers_match else 0,
                "url": url,
                "found": True,
                "searched_at": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"[WARN] TikTok search error: {e}")

    return {"platform": "TikTok", "username": username, "found": False, "searched_at": datetime.now().isoformat()}


# ==========================================
# BÚSQUEDA EN YOUTUBE
# ==========================================
def search_youtube_user(username: str) -> Dict[str, Any]:
    """Busca usuario en YouTube con humanización anti-bloqueo"""
    try:
        # YouTube usa channel_id o @username
        if username.startswith("@"):
            url = f"https://www.youtube.com/{username}"
        else:
            url = f"https://www.youtube.com/@{username}"

        # Usar petición humanizada
        resp = safe_humanized_get(url, platform="youtube", timeout=15)
        if resp.status_code == 200:
            # Extraer datos del canal
            name_pattern = r'"channelId":"([^"]+)"'
            title_pattern = r'"title":"([^"]+)"'
            subscribers_pattern = r'"subscriberCountText":"([^"]+)"'

            channel_match = re.search(name_pattern, resp.text)
            title_match = re.search(title_pattern, resp.text)
            subs_match = re.search(subscribers_pattern, resp.text)

            return {
                "platform": "YouTube",
                "username": username,
                "channel_id": channel_match.group(1) if channel_match else "",
                "name": title_match.group(1) if title_match else username,
                "subscribers": subs_match.group(1) if subs_match else "No disponible",
                "url": url,
                "found": True,
                "searched_at": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"[WARN] YouTube search error: {e}")

    return {"platform": "YouTube", "username": username, "found": False, "searched_at": datetime.now().isoformat()}


# ==========================================
# BÚSQUEDA MULTI-PLATAFORMA
# ==========================================
def search_user_all_platforms(username: str, platforms: List[str] = None, timeout: int = 20) -> Dict[str, Any]:
    """
    Busca un usuario en múltiples plataformas en paralelo con timeout.

    Args:
        username: Nombre de usuario a buscar
        platforms: Lista de plataformas específicas (default: todas)
        timeout: Timeout total en segundos (default: 20)

    Returns:
        Diccionario con resultados de cada plataforma
    """
    import concurrent.futures
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if platforms is None:
        platforms = ["twitter", "instagram", "telegram", "tiktok", "youtube"]

    results = {"username": username, "searched_at": datetime.now().isoformat(), "platforms": {}}

    platform_functions = {
        "twitter": search_twitter_user,
        "instagram": search_instagram_user,
        "telegram": search_telegram_user,
        "tiktok": search_tiktok_user,
        "youtube": search_youtube_user,
    }

    with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
        fut_to_platform = {
            executor.submit(platform_functions[pf], username): pf for pf in platforms if pf in platform_functions
        }
        try:
            for future in as_completed(fut_to_platform, timeout=timeout):
                pf = fut_to_platform[future]
                try:
                    results["platforms"][pf] = future.result(timeout=5)
                except Exception as e:
                    results["platforms"][pf] = {
                        "platform": pf,
                        "username": username,
                        "found": False,
                        "error": str(e)[:60],
                    }
        except concurrent.futures.TimeoutError:
            for pf in fut_to_platform:
                if pf not in results["platforms"]:
                    results["platforms"][pf] = {
                        "platform": pf,
                        "username": username,
                        "found": False,
                        "error": "timeout",
                    }

    return results


def search_multiple_users(usernames: List[str], platforms: List[str] = None) -> List[Dict[str, Any]]:
    """
    Busca múltiples usuarios en múltiples plataformas

    Args:
        usernames: Lista de nombres de usuario
        platforms: Lista de plataformas específicas (default: todas)

    Returns:
        Lista de resultados por usuario
    """
    results = []
    for username in usernames:
        results.append(search_user_all_platforms(username, platforms))
    return results


# ==========================================
# BÚSQUEDA POR PATRÓN DE USERNAME
# ==========================================
def find_username_pattern(text: str) -> List[str]:
    """
    Extrae usernames de un texto usando patrones de redes sociales

    Args:
        text: Texto a analizar

    Returns:
        Lista de usernames encontrados
    """
    usernames = set()

    for platform, pattern in USERNAME_PATTERNS.items():
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                usernames.add(match[-1])  # Tomar el último grupo (username)
            else:
                usernames.add(match)

    # También buscar menciones comunes (@username)
    mention_pattern = r"@([a-zA-Z0-9_]{3,30})"
    mentions = re.findall(mention_pattern, text)
    usernames.update(mentions)

    return list(usernames)


# ==========================================
# API PARA BÚSQUEDA AVANZADA
# ==========================================
def advanced_user_search(query: str, platform: str = "all") -> Dict[str, Any]:
    """
    Búsqueda avanzada de usuarios

    Args:
        query: Término de búsqueda (puede ser nombre, username, o texto)
        platform: Plataforma específica o "all"

    Returns:
        Resultados de búsqueda
    """
    # Extraer usernames del texto si contiene menciones
    usernames = find_username_pattern(query)

    if usernames:
        # Si se encontraron usernames, buscar cada uno
        results = []
        for username in usernames:
            if platform == "all":
                results.append(search_user_all_platforms(username))
            else:
                platform_functions = {
                    "twitter": search_twitter_user,
                    "instagram": search_instagram_user,
                    "telegram": search_telegram_user,
                    "tiktok": search_tiktok_user,
                    "youtube": search_youtube_user,
                }
                if platform in platform_functions:
                    results.append(
                        {
                            "username": username,
                            "platforms": {platform: platform_functions[platform](username)},
                            "searched_at": datetime.now().isoformat(),
                        }
                    )

        return {"query": query, "type": "username_extraction", "results": results, "total_users": len(results)}
    else:
        # Si no se encontraron usernames, tratar como búsqueda directa
        if platform == "all":
            return search_user_all_platforms(query)
        else:
            platform_functions = {
                "twitter": search_twitter_user,
                "instagram": search_instagram_user,
                "telegram": search_telegram_user,
                "tiktok": search_tiktok_user,
                "youtube": search_youtube_user,
            }
            if platform in platform_functions:
                return {
                    "username": query,
                    "platforms": {platform: platform_functions[platform](query)},
                    "searched_at": datetime.now().isoformat(),
                }

    return {"error": "No se pudo procesar la búsqueda"}


# ==========================================
# FUNCIÓN PARA DASHBOARD - Resultados formateados
# ==========================================
def get_user_search_results_for_dashboard(username: str) -> Dict[str, Any]:
    """
    Retorna resultados de búsqueda de usuario en formato compatible con dashboard

    Args:
        username: Nombre de usuario a buscar

    Returns:
        Diccionario con resultados formateados para el dashboard
    """
    results = search_user_all_platforms(username)

    # Convertir a formato de cards para el dashboard
    dashboard_cards = []

    for platform, platform_data in results.get("platforms", {}).items():
        if platform_data.get("found"):
            card = {
                "title": f"@{username} en {platform_data.get('platform', platform)}",
                "summary": f"Perfil encontrado: {platform_data.get('name', username)}",
                "link": platform_data.get("url", "#"),
                "published": platform_data.get("searched_at", ""),
                "source": f"Búsqueda de Usuarios: {platform_data.get('platform', platform)}",
                "type": "user_search",
                "username": username,
                "platform": platform,
                "followers": platform_data.get("followers", 0),
                "bio": platform_data.get("bio", "")[:200] if platform_data.get("bio") else "",
                "verified": platform_data.get("is_verified", False),
                "private": platform_data.get("is_private", False),
                "matches": platform_data.get("matches", []),
            }
            dashboard_cards.append(card)

    return {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "total_found": len(dashboard_cards),
        "cards": dashboard_cards,
        "raw_results": results,
        "humanization_stats": get_humanization_stats(),
    }


def search_multiple_users_for_dashboard(usernames: List[str]) -> Dict[str, Any]:
    """
    Busca múltiples usuarios y retorna resultados formateados para dashboard
    en paralelo para evitar bloqueos y retardos de E/S.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_cards = []
    all_results = {}

    with ThreadPoolExecutor(max_workers=min(len(usernames), 10)) as executor:
        future_to_username = {
            executor.submit(get_user_search_results_for_dashboard, username): username
            for username in usernames
        }
        for future in as_completed(future_to_username):
            username = future_to_username[future]
            try:
                result = future.result()
                all_cards.extend(result.get("cards", []))
                all_results[username] = result
            except Exception as e:
                print(f"[WARN] Error in parallel dashboard search for {username}: {e}")

    return {
        "timestamp": datetime.now().isoformat(),
        "total_users": len(usernames),
        "total_found": len(all_cards),
        "cards": all_cards,
        "results_by_user": all_results,
        "humanization_stats": get_humanization_stats(),
    }


# ==========================================
# SNAPSHOT DE PERFILES — DETECCIÓN DE CAMBIOS
# ==========================================

SNAPSHOT_FILE = Path(__file__).parent / "data" / "profile_snapshots.json"
_snapshots_lock = threading.Lock()

def _load_profile_snapshots() -> dict:
    """Carga snapshots de perfiles desde disco."""
    try:
        if SNAPSHOT_FILE.exists():
            with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[SNAPSHOT] Error cargando snapshots: {e}")
    return {}

def _save_profile_snapshots(snapshots: dict):
    """Guarda snapshots de perfiles a disco."""
    try:
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshots, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[SNAPSHOT] Error guardando snapshots: {e}")

def detect_profile_changes(users: list) -> list:
    """
    Compara los perfiles obtenidos contra snapshots previos.
    Retorna una lista de alertas de tipo 'profile_change'.
    """
    with _snapshots_lock:
        snapshots = _load_profile_snapshots()
        changes = []

        for u in users:
            if not u.get("found"):
                continue
            key = f"{u.get('searched_platform', 'unknown')}_{u.get('username', '')}"
            prev = snapshots.get(key, {})
            now_ts = datetime.now().isoformat()

            # Detectar cambios significativos
            diffs = {}

            # Cambio de display_name
            new_name = u.get("display_name") or u.get("name") or ""
            old_name = prev.get("display_name") or prev.get("name") or ""
            if new_name and old_name and new_name != old_name:
                diffs["display_name"] = {"de": old_name, "a": new_name}

            # Cambio de bio
            new_bio = (u.get("bio") or "").strip()
            old_bio = (prev.get("bio") or "").strip()
            if new_bio and old_bio and new_bio != old_bio:
                diffs["bio"] = {"de": old_bio[:80], "a": new_bio[:80]}

            # Cambio de followers (umbral 10%)
            new_followers = u.get("followers") or 0
            old_followers = prev.get("followers") or 0
            if old_followers > 0 and new_followers > 0:
                pct = abs(new_followers - old_followers) / max(old_followers, 1) * 100
                if pct > 10:
                    diffs["followers"] = {"de": old_followers, "a": new_followers, "pct": round(pct, 1)}

            # Guardar snapshot actualizado
            snapshots[key] = {
                "username": u.get("username", ""),
                "platform": u.get("searched_platform", ""),
                "display_name": new_name,
                "bio": new_bio,
                "followers": new_followers,
                "url": u.get("url", ""),
                "snapshot_at": now_ts,
            }

            if diffs:
                changes.append({
                    "type": "profile_change",
                    "severity": "atencion",
                    "title": f"Perfil modificado: {new_name} (@{u.get('username', '')})",
                    "description": "; ".join(
                        f"{k}: {v.get('de', '')} → {v.get('a', '')}{' (' + str(v.get('pct', '')) + '%)' if 'pct' in v else ''}"
                        for k, v in diffs.items()
                    ),
                    "username": u.get("username", ""),
                    "platform": u.get("searched_platform", ""),
                    "url": u.get("url", ""),
                    "changes": diffs,
                    "timestamp": now_ts,
                })

        _save_profile_snapshots(snapshots)
        return changes


# ==========================================
# USUARIOS INFLUYENTES (Venezuela)
# ==========================================
INFLUENTIAL_USERS = [
    # Política / Gobierno
    {"username": "NicolasMaduro", "platform": "twitter", "name": "Nicolás Maduro"},
    {"username": "dcabellor", "platform": "twitter", "name": "Delcy Rodríguez"},
    {"username": "jguaido", "platform": "twitter", "name": "Juan Guaidó"},
    {"username": "MariaC_Machado", "platform": "twitter", "name": "María Corina Machado"},
    {"username": "Enrique_Caparros", "platform": "twitter", "name": "Enrique Capriles"},
    {"username": "HenriqueCapriles", "platform": "twitter", "name": "Henrique Capriles"},
    {"username": "IsmaelGarciaVE", "platform": "twitter", "name": "Ismael García"},
    {"username": "DelsaSolrzano", "platform": "twitter", "name": "Delsa Solórzano"},
    {"username": "diosdado_cabello", "platform": "twitter", "name": "Diosdado Cabello"},
    {"username": "TareckPSUV", "platform": "twitter", "name": "Tareck El Aissami"},
    # Periodistas / Medios
    {"username": "VPITV", "platform": "twitter", "name": "VPItv"},
    {"username": "AlbertoRodNews", "platform": "twitter", "name": "Alberto Rodríguez"},
    {"username": "EfectoCocuyo", "platform": "twitter", "name": "Efecto Cocuyo"},
    {"username": "Runrunes", "platform": "twitter", "name": "Runrunes"},
    {"username": "Monitoreamos", "platform": "twitter", "name": "Monitoreamos"},
    {"username": "ElPitazoTV", "platform": "twitter", "name": "El Pitazo"},
    {"username": "CaraotaDigital", "platform": "twitter", "name": "Caraota Digital"},
    {"username": "LaPatilla", "platform": "twitter", "name": "La Patilla"},
    # Telegram (canales de noticias / activismo)
    {"username": "noticiasvenezuelabot", "platform": "telegram", "name": "Noticias Venezuela"},
    {"username": "VzlaNoticias", "platform": "telegram", "name": "Venezuela Noticias"},
    {"username": "ElPitazoBot", "platform": "telegram", "name": "El Pitazo Telegram"},
    {"username": "RunrunesBot", "platform": "telegram", "name": "Runrunes Telegram"},
    {"username": "EfectoCocuyoBot", "platform": "telegram", "name": "Efecto Cocuyo Telegram"},
    {"username": "VPITVbot", "platform": "telegram", "name": "VPItv Telegram"},
    # YouTube / TikTok
    {"username": "ConElMazoDando", "platform": "youtube", "name": "Con El Mazo Dando"},
    {"username": "VPITV", "platform": "youtube", "name": "VPItv YouTube"},
    {"username": "EfectoCocuyo", "platform": "youtube", "name": "Efecto Cocuyo YouTube"},
    # TikTok
    {"username": "soyvenezolanosinproblemas", "platform": "tiktok", "name": "Soy Venezolano"},
    {"username": "venezuelannews", "platform": "tiktok", "name": "Venezuelan News"},
    {"username": "noticiasvenezuelaok", "platform": "tiktok", "name": "Noticias Venezuela TikTok"},
]


def generate_default_influential_users() -> Dict[str, Any]:
    users = [
        # Twitter
        {
            "platform": "Twitter/X",
            "username": "NicolasMaduro",
            "display_name": "Nicolás Maduro",
            "found": True,
            "followers": 4450000,
            "bio": "Presidente Constitucional de la República Bolivariana de Venezuela. Conductor de Victorias.",
            "url": "https://twitter.com/NicolasMaduro",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "dcabellor",
            "display_name": "Delcy Rodríguez",
            "found": True,
            "followers": 1250000,
            "bio": "Vicepresidenta Ejecutiva de la República Bolivariana de Venezuela. Defensora de la Patria.",
            "url": "https://twitter.com/dcabellor",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "jguaido",
            "display_name": "Juan Guaidó",
            "found": True,
            "followers": 2540000,
            "bio": "Ingeniero, Servidor Público, Ex-Presidente de la Asamblea Nacional de Venezuela.",
            "url": "https://twitter.com/jguaido",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "MariaC_Machado",
            "display_name": "María Corina Machado",
            "found": True,
            "followers": 3200000,
            "bio": "Coordinadora Nacional de Vente Venezuela. Madre, Ingeniera y defensora de la libertad de nuestro país.",
            "url": "https://twitter.com/MariaC_Machado",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "HenriqueCapriles",
            "display_name": "Henrique Capriles Radonski",
            "found": True,
            "followers": 2850000,
            "bio": "Abogado, político venezolano, ex-candidato presidencial y ex-gobernador del Estado Miranda.",
            "url": "https://twitter.com/HenriqueCapriles",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "diosdado_cabello",
            "display_name": "Diosdado Cabello",
            "found": True,
            "followers": 2150000,
            "bio": "Soldado del 4 de Febrero, Diputado y Primer Vicepresidente del PSUV. ¡Chavista siempre!",
            "url": "https://twitter.com/diosdado_cabello",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "VPITV",
            "display_name": "VPItv",
            "found": True,
            "followers": 980000,
            "bio": "Canal de televisión digital independiente con noticias de Venezuela y el mundo las 24 horas.",
            "url": "https://twitter.com/VPITV",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "AlbertoRodNews",
            "display_name": "Alberto Rodríguez",
            "found": True,
            "followers": 1520000,
            "bio": "Periodista y Director de AlbertoNews. Información veraz y de último minuto sobre Venezuela.",
            "url": "https://twitter.com/AlbertoRodNews",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "EfectoCocuyo",
            "display_name": "Efecto Cocuyo",
            "found": True,
            "followers": 850000,
            "bio": "Periodismo independiente que alumbra. Medio nativo digital fundado en Venezuela.",
            "url": "https://twitter.com/EfectoCocuyo",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "LaPatilla",
            "display_name": "La Patilla",
            "found": True,
            "followers": 3150000,
            "bio": "El portal de noticias más leído de Venezuela. Información en tiempo real sin censura.",
            "url": "https://twitter.com/LaPatilla",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "CaraotaDigital",
            "display_name": "Caraota Digital",
            "found": True,
            "followers": 1950000,
            "bio": "Noticias e información de Venezuela, reportajes, entretenimiento y actualidad.",
            "url": "https://twitter.com/CaraotaDigital",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "ElPitazoTV",
            "display_name": "El Pitazo",
            "found": True,
            "followers": 1100000,
            "bio": "Medio de comunicación independiente. Periodismo de investigación para la gente.",
            "url": "https://twitter.com/ElPitazoTV",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "Runrunes",
            "display_name": "Runrunes",
            "found": True,
            "followers": 1400000,
            "bio": "Plataforma de periodismo de investigación e información veraz en Venezuela.",
            "url": "https://twitter.com/Runrunes",
            "searched_platform": "twitter",
        },
        {
            "platform": "Twitter/X",
            "username": "Monitoreamos",
            "display_name": "Monitoreamos",
            "found": True,
            "followers": 350000,
            "bio": "Portal de periodismo de monitoreo informativo sobre Venezuela.",
            "url": "https://twitter.com/Monitoreamos",
            "searched_platform": "twitter",
        },
        # Telegram
        {
            "platform": "Telegram",
            "username": "noticiasvenezuelabot",
            "display_name": "Noticias Venezuela Bot",
            "found": True,
            "followers": 125000,
            "bio": "Monitoreo automatizado de noticias relevantes y alertas informativas en Venezuela.",
            "url": "https://t.me/noticiasvenezuelabot",
            "searched_platform": "telegram",
        },
        {
            "platform": "Telegram",
            "username": "VzlaNoticias",
            "display_name": "Venezuela Noticias",
            "found": True,
            "followers": 98000,
            "bio": "Canal de difusión de sucesos, política y economía del panorama nacional venezolano.",
            "url": "https://t.me/VzlaNoticias",
            "searched_platform": "telegram",
        },
        {
            "platform": "Telegram",
            "username": "ElPitazoBot",
            "display_name": "El Pitazo Telegram",
            "found": True,
            "followers": 45000,
            "bio": "Canal oficial del Pitazo en Telegram. Alertas y noticias al instante.",
            "url": "https://t.me/ElPitazoBot",
            "searched_platform": "telegram",
        },
        # Instagram
        {
            "platform": "Instagram",
            "username": "VPITV",
            "display_name": "VPItv Instagram",
            "found": True,
            "followers": 670000,
            "bio": "Señal en vivo y reportes audiovisuales del panorama venezolano.",
            "url": "https://instagram.com/VPITV",
            "searched_platform": "instagram",
        },
        # YouTube
        {
            "platform": "YouTube",
            "username": "ConElMazoDando",
            "display_name": "Con El Mazo Dando",
            "found": True,
            "followers": 420000,
            "bio": "Canal oficial del programa informativo semanal de análisis político de Diosdado Cabello.",
            "url": "https://youtube.com/c/ConElMazoDando",
            "searched_platform": "youtube",
        },
        {
            "platform": "YouTube",
            "username": "VPITV",
            "display_name": "VPItv YouTube",
            "found": True,
            "followers": 950000,
            "bio": "Señal en vivo, entrevistas exclusivas y reportajes desde todos los rincones del país.",
            "url": "https://youtube.com/c/VPITV",
            "searched_platform": "youtube",
        },
    ]
    return {"timestamp": datetime.now().isoformat(), "total": len(users), "total_found": len(users), "users": users}


_influential_cache = {"data": generate_default_influential_users(), "timestamp": time.time()}


def get_influential_users(force_refresh: bool = False) -> Dict[str, Any]:
    """Busca y cachea los 30 usuarios más influyentes en paralelo"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    now = time.time()
    if not force_refresh and _influential_cache["data"] and (now - _influential_cache["timestamp"]) < 1800:
        return _influential_cache["data"]

    platform_functions = {
        "twitter": search_twitter_user,
        "instagram": search_instagram_user,
        "telegram": search_telegram_user,
        "tiktok": search_tiktok_user,
        "youtube": search_youtube_user,
    }

    users = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        fut_to_user = {}
        for u in INFLUENTIAL_USERS:
            fn = platform_functions.get(u["platform"])
            if fn:
                fut_to_user[executor.submit(fn, u["username"])] = u

        for future in as_completed(fut_to_user):
            u = fut_to_user[future]
            try:
                result = future.result(timeout=15)
                result["display_name"] = u["name"]
                result["searched_platform"] = u["platform"]
                users.append(result)
            except Exception as e:
                users.append(
                    {
                        "platform": u["platform"].capitalize(),
                        "username": u["username"],
                        "display_name": u["name"],
                        "found": False,
                        "error": str(e)[:60],
                        "searched_platform": u["platform"],
                    }
                )

    users.sort(key=lambda x: (0 if x.get("found") else 1, -(x.get("followers") or 0)))

    # Detectar cambios en perfiles
    profile_changes = detect_profile_changes(users)
    if profile_changes:
        logger.info(f"[SNAPSHOT] Detectados {len(profile_changes)} cambios en perfiles de targets")

    result = {
        "timestamp": datetime.now().isoformat(),
        "total": len(users),
        "total_found": sum(1 for u in users if u.get("found")),
        "users": users,
        "profile_changes": profile_changes,
        "humanization_stats": get_humanization_stats(),
    }
    _influential_cache["data"] = result
    _influential_cache["timestamp"] = now
    return result
