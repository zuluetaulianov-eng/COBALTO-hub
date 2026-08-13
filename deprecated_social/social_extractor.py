# social_extractor.py - v1.1.0
# Módulo para extracción de datos de redes sociales
# Integración con dashboard.py (se espera que llame a get_social_data())
# Soporta: X/Twitter, Telegram, Reddit, Bluesky
# ──────────────────────────────────────────────────────────────
# Requisitos: pip install twikit telethon python-dotenv praw atproto
# Configuración en .env (nunca commitear)

import json
import os
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

# ── Carga segura de credenciales ────────────────────────────────
load_dotenv()

TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_EMAIL = os.getenv("TWITTER_EMAIL")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

# ── Reddit ──────────────────────────────────────────────────────
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "CobaltoHub/1.1.0")

# ── Bluesky ─────────────────────────────────────────────────────
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

# ── Importaciones condicionales (evitamos errores si no hay creds) ──
reddit_client = None
if all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD]):
    try:
        import praw

        reddit_client = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            user_agent=REDDIT_USER_AGENT,
        )
        print("[OK] Reddit client inicializado")
    except ImportError:
        print("[ADVERTENCIA] praw no instalado -> Reddit desactivado")
    except Exception as e:
        print(f"[ERROR] Fallo al inicializar Reddit: {e}")
else:
    print("[INFO] Credenciales de Reddit incompletas -> Reddit desactivado")

bluesky_client = None
if all([BLUESKY_HANDLE, BLUESKY_PASSWORD]):
    try:
        from atproto import Client as BlueskyClient

        bluesky_client = BlueskyClient()
        bluesky_client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        print("[OK] Bluesky client inicializado")
    except ImportError:
        print("[ADVERTENCIA] atproto no instalado -> Bluesky desactivado")
    except Exception as e:
        print(f"[ERROR] Fallo al inicializar Bluesky: {e}")
else:
    print("[INFO] Credenciales de Bluesky incompletas -> Bluesky desactivado")

twitter_client = None
if all([TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD]):
    try:
        from twikit import Client

        twitter_client = Client("es-CO")  # o tu locale
    except ImportError:
        print("[ADVERTENCIA] twikit no instalado -> X scraping desactivado")
else:
    print("[INFO] Credenciales de Twitter no encontradas en .env -> X desactivado")


# ── Estructura de dato esperada por el dashboard ────────────────
# Cada item debe tener: title, summary, link, published, image?, source
def _format_tweet_to_card(tweet) -> Dict[str, Any]:
    """Convierte tweet de twikit a formato compatible con generate_source_html"""
    return {
        "title": tweet.text[:140] + "..." if len(tweet.text) > 140 else tweet.text,
        "summary": tweet.text,
        "link": f"https://x.com/{tweet.user.username}/status/{tweet.id}",
        "published": tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "Reciente",
        "image": tweet.media[0].media_url_https if tweet.media else None,
        "source": f"X @{tweet.user.username}",
        # Extra (opcional para tooltips o expansión futura)
        "author": tweet.user.name,
        "likes": tweet.favorite_count,
        "retweets": tweet.retweet_count,
    }


def _format_reddit_to_card(submission) -> Dict[str, Any]:
    """Convierte submission de Reddit a formato compatible con generate_source_html"""
    # Extraer imagen si existe
    image_url = None
    if hasattr(submission, "url"):
        # Si es link directo a imagen
        if any(submission.url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            image_url = submission.url
        # Si es link de i.redd.it
        elif "i.redd.it" in submission.url:
            image_url = submission.url
        # Si es post con thumbnail
        elif (
            hasattr(submission, "thumbnail")
            and submission.thumbnail
            and submission.thumbnail not in ("self", "default", "nsfw")
        ):
            image_url = submission.thumbnail

    # Crear título resumido
    title = submission.title
    if len(title) > 140:
        title = title[:140] + "..."

    # Crear resumen con selftext si existe
    summary = (
        submission.selftext[:280]
        if hasattr(submission, "selftext") and submission.selftext
        else f"Post en r/{submission.subreddit.display_name}"
    )
    if len(summary) > 280:
        summary = summary[:280] + "..."

    # Formatear fecha
    try:
        published = datetime.fromtimestamp(submission.created_utc).strftime("%Y-%m-%d %H:%M")
    except Exception:
        published = "Reciente"

    return {
        "title": title,
        "summary": summary,
        "link": f"https://reddit.com{submission.permalink}",
        "published": published,
        "image": image_url,
        "source": f"r/{submission.subreddit.display_name}",
        "author": str(submission.author) if submission.author else "[deleted]",
        "score": submission.score,
        "upvote_ratio": getattr(submission, "upvote_ratio", None),
    }


def _format_bluesky_to_card(post) -> Dict[str, Any]:
    """Convierte post de Bluesky a formato compatible con generate_source_html"""
    record = post.record
    author = post.author

    # Extraer texto
    text = getattr(record, "text", "") or str(record)
    title = text[:140] if len(text) > 140 else text
    if len(text) > 140:
        title = title + "..."

    # Extraer imagen si existe
    image_url = None
    try:
        if hasattr(record, "embed") and record.embed:
            embed = record.embed
            if hasattr(embed, "images") and embed.images:
                image_url = embed.images[0].fullsize if hasattr(embed.images[0], "fullsize") else None
    except Exception:
        pass

    # Formatear fecha
    try:
        published = datetime.fromisoformat(record.created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        published = "Reciente"

    return {
        "title": title,
        "summary": text,
        "link": f"https://bsky.app/profile/{author.handle}/post/{post.uri.split('/')[-1]}",
        "published": published,
        "image": image_url,
        "source": f"@{author.handle}",
        "author": author.display_name if hasattr(author, "display_name") else author.handle,
    }


# ── Función principal que llama el dashboard ────────────────────
def get_social_data() -> Dict[str, Any]:
    """
    Devuelve datos de redes sociales en formato listo para el dashboard.
    Estructura:
    {
        "timestamp": str,
        "sources": {
            "X": [lista de cards],
            "Telegram": [lista futura],
            ...
        },
        "count": total_items
    }
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    social_data = {"timestamp": now, "sources": {}, "count": 0}

    # ── Twitter / X ─────────────────────────────────────────────
    if twitter_client:
        try:
            twitter_client.login(auth_info_1=TWITTER_USERNAME, auth_info_2=TWITTER_EMAIL, password=TWITTER_PASSWORD)
            print("[OK] Login en X exitoso")

            # Ejemplo: buscar tweets recientes sobre un tema de interés
            # Puedes parametrizar esto después (keywords desde config o UI)
            keywords = "ciberseguridad OR pentesting OR IA lang:es -filter:replies"
            tweets = twitter_client.search_tweet(keywords, product="Latest", count=12)

            x_cards = [_format_tweet_to_card(t) for t in tweets if t.text.strip()]
            if x_cards:
                social_data["sources"]["X"] = x_cards
                social_data["count"] += len(x_cards)
                print(f"[OK] Capturados {len(x_cards)} tweets relevantes")

        except Exception as e:
            print(f"[ERROR] Fallo en X scraping: {str(e)}")
    else:
        print("[SKIP] Twitter desactivado (credenciales o librería)")

    # ── Reddit ────────────────────────────────────────────────────
    if reddit_client:
        try:
            # Subreddits relevantes para Venezuela y ciberseguridad
            subreddits = ["vzla", "venezuela", "ciberseguridad", "netsec", "osint", "privacy"]
            reddit_cards = []

            for sub_name in subreddits:
                try:
                    subreddit = reddit_client.subreddit(sub_name)
                    # Tomar los 3 posts más hot de cada subreddit
                    for submission in subreddit.hot(limit=3):
                        if submission.stickied:  # Saltar pinned posts
                            continue
                        reddit_cards.append(_format_reddit_to_card(submission))
                except Exception as e:
                    print(f"[AVISO] Error al leer r/{sub_name}: {e}")
                    continue

            if reddit_cards:
                social_data["sources"]["Reddit"] = reddit_cards[:12]  # Limitar a 12 total
                social_data["count"] += len(reddit_cards[:12])
                print(f"[OK] Capturados {len(reddit_cards[:12])} posts de Reddit")

        except Exception as e:
            print(f"[ERROR] Fallo en Reddit scraping: {str(e)}")
    else:
        print("[SKIP] Reddit desactivado (credenciales o librería)")

    # ── Bluesky ───────────────────────────────────────────────────
    if bluesky_client:
        try:
            # Buscar posts recientes con keywords relevantes
            # Usamos la búsqueda nativa de Bluesky (AT Protocol)
            keywords_bluesky = "venezuela OR ciberseguridad OR osint"

            # Obtener timeline personal o buscar posts
            # Nota: Bluesky API es diferente, usamos feed de autor o búsqueda
            bluesky_cards = []

            # Buscar posts recientes (últimas 24h aprox)
            try:
                # Intentar búsqueda global si está disponible
                response = bluesky_client.app.bsky.feed.search_posts({"q": keywords_bluesky, "limit": 12})
                if response and hasattr(response, "posts"):
                    for post in response.posts:
                        bluesky_cards.append(_format_bluesky_to_card(post))
            except Exception as search_error:
                print(f"[AVISO] Búsqueda Bluesky falló, intentando timeline: {search_error}")
                # Fallback: obtener posts del propio usuario
                try:
                    timeline = bluesky_client.get_timeline(limit=10)
                    for feed_item in timeline.feed:
                        bluesky_cards.append(_format_bluesky_to_card(feed_item.post))
                except Exception as timeline_error:
                    print(f"[ERROR] Timeline Bluesky también falló: {timeline_error}")

            if bluesky_cards:
                social_data["sources"]["Bluesky"] = bluesky_cards[:12]
                social_data["count"] += len(bluesky_cards[:12])
                print(f"[OK] Capturados {len(bluesky_cards[:12])} posts de Bluesky")

        except Exception as e:
            print(f"[ERROR] Fallo en Bluesky scraping: {str(e)}")
    else:
        print("[SKIP] Bluesky desactivado (credenciales o librería)")

    # ── Telegram ──────────────────────────────────────────────────

    if all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE]):
        try:
            # ... implementación futura ...
            social_data["sources"]["Telegram"] = []  # placeholder
        except Exception as e:
            print(f"[ERROR] Fallo al preparar Telethon: {str(e)}")
    else:
        print("[INFO] Credenciales Telegram no encontradas -> placeholder activado")

    # Si no hay nada → mensaje informativo
    if not social_data["sources"]:
        social_data["sources"]["info"] = [
            {
                "title": "Sin datos capturados aún",
                "summary": "Configura .env con credenciales o espera próxima actualización del scraper.",
                "link": "#",
                "published": now,
                "source": "Sistema",
            }
        ]

    return social_data


# ── Prueba standalone (ejecuta este archivo directamente) ───────
if __name__ == "__main__":
    print("=== TEST social_extractor.py ===")
    data = get_social_data()
    print(f"Timestamp: {data['timestamp']}")
    print(f"Total items: {data['count']}")
    for source, items in data["sources"].items():
        print(f"\n-> {source} ({len(items)})")
        for i, item in enumerate(items[:3], 1):  # solo primeros 3 para no spamear
            print(f"  {i}. {item['title'][:60]}... -> {item['link']}")
    # Opcional: guardar a JSON para debug
    with open("social_sample.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n-> Muestra guardada en social_sample.json")
