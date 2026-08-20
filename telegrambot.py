import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from time import mktime

import aiohttp
import feedparser
from aiohttp import ClientTimeout
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from PIL import Image
from telegram import Update
from telegram.error import RetryAfter, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from config import RSS_FEEDS
from database import clean_old_sent_news, is_news_sent, mark_news_sent

# =========================================
# CONFIGURACIÓN - Cargar desde .env
# =========================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
PAGINA_OFICIAL = os.getenv("PAGINA_OFICIAL", "https://t.me/notivenezuelaarma")
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "15"))
REQUEST_TIMEOUT = 12
MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 200
MAX_ENTRIES_PER_FEED = 12

# Ruta al caché persistente del dashboard
BASE_DIR = Path(__file__).parent
CACHE_FILE = BASE_DIR / "dashboard_persistent_cache.json"


def _load_cache() -> dict:
    """Carga el contexto actual desde el caché persistente del dashboard."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[BOT CACHE] Error cargando caché: {e}")
    return {}


def _fmt_num(n):
    """Formatea números grandes: 1234 -> 1,234"""
    if n is None:
        return "0"
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)


# ── Comandos C4I ──────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bienvenida y lista de comandos."""
    user = update.effective_user
    msg = (
        f"🛡️ *Bienvenido, {user.first_name or 'Operador'}*\n\n"
        "Sistema de Inteligencia COBALTO — C4I Interface\n\n"
        "Comandos disponibles:\n"
        "• `/status` — Estado del sistema y métricas\n"
        "• `/alerts` — Últimas alertas tácticas\n"
        "• `/search <usuario>` — Buscar usuario en redes\n"
        "• `/outages` — Apagones de red detectados\n"
        "• `/briefing` — Resumen ejecutivo IA\n"
        "• `/help` — Esta ayuda\n\n"
        "Powered by COBALTO v9.4"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra ayuda."""
    await cmd_start(update, context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estado del sistema con métricas clave."""
    ctx = _load_cache()
    entries = ctx.get("all_entries", [])
    alerts = ctx.get("alerts", [])
    cb_count = ctx.get("cb_count", 0)
    total_sources = ctx.get("total_sources", 0)
    timestamp = ctx.get("timestamp") or ctx.get("now") or "desconocido"
    alert_counts = ctx.get("alert_counts", {})
    cycle_id = ctx.get("cycle_id", 0)

    status_icon = "⚠️" if cb_count > 0 else "✅"
    msg = (
        f"📊 *ESTADO DEL SISTEMA*\n\n"
        f"🆔 Ciclo: `#{cycle_id}`\n"
        f"📰 Entradas: `{_fmt_num(len(entries))}`\n"
        f"🚨 Alertas activas: `{len(alerts)}`\n"
        f"📡 Fuentes: `{_fmt_num(total_sources)}`\n"
        f"{status_icon} Circuitos abiertos: `{cb_count}`\n"
        f"🕐 Último ciclo: `{timestamp}`\n\n"
        f"Desglose alertas:\n"
        f"• Críticas: `{alert_counts.get('critico', 0)}`\n"
        f"• Urgentes: `{alert_counts.get('urgente', 0)}`\n"
        f"• Atención: `{alert_counts.get('atencion', 0)}`"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Últimas alertas tácticas."""
    ctx = _load_cache()
    alerts = ctx.get("alerts", [])[:10]

    if not alerts:
        await update.message.reply_text("✅ *No hay alertas activas*", parse_mode="MarkdownV2")
        return

    lines = ["🚨 *ALERTAS TÁCTICAS* (últimas 10)\n"]
    for i, a in enumerate(alerts, 1):
        title = a.get("title", "Sin título")
        sev = a.get("severity", "info")
        sev_icon = {"critico": "🔴", "urgente": "🟠", "atencion": "🟡", "warning": "⚠️", "info": "ℹ️"}
        icon = sev_icon.get(sev, "ℹ️")
        lines.append(f"{i}\\. `{icon}` {title[:100]}")
        desc = a.get("description", "")
        if desc:
            lines.append(f"   _{desc[:120]}_")
    lines.append(f"\nTotal: `{len(alerts)}` alertas activas")

    msg = "\n".join(lines)
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca un usuario en redes sociales."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Uso:* `/search <usuario>`\nEjemplo: `/search NicolasMaduro`",
            parse_mode="MarkdownV2",
        )
        return

    username = context.args[0].strip()
    await update.message.reply_text(f"🔍 Buscando `@{username}` en todas las plataformas...", parse_mode="MarkdownV2")

    try:
        from user_search import search_user_all_platforms

        result = await asyncio.to_thread(search_user_all_platforms, username)
        if not result:
            await update.message.reply_text(f"❌ No se encontraron resultados para `@{username}`", parse_mode="MarkdownV2")
            return

        platforms = result.get("platforms", {})
        found_any = any(p.get("found") for p in platforms.values())
        if not found_any:
            await update.message.reply_text(f"❌ Usuario `@{username}` no encontrado en ninguna plataforma", parse_mode="MarkdownV2")
            return

        lines = [f"🔍 *Resultados para @{username}*\n"]
        for plat, data in platforms.items():
            if data.get("found"):
                name = data.get("name") or data.get("display_name") or username
                followers = data.get("followers", 0)
                bio = (data.get("bio") or "")[:80]
                lines.append(f"• *{plat}*: {name}")
                if followers:
                    lines.append(f"   👥 {_fmt_num(followers)} seguidores")
                if bio:
                    lines.append(f"   📝 _{bio}_")
                lines.append(f"   🔗 {data.get('url', 'N/A')}")

        await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"[BOT SEARCH] Error: {e}")
        await update.message.reply_text(f"❌ Error en la búsqueda: {str(e)[:100]}")


async def cmd_outages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apagones de red detectados."""
    ctx = _load_cache()
    events = ctx.get("events_data", {})
    outages = events.get("network_outages", []) if isinstance(events, dict) else []

    if not outages:
        await update.message.reply_text("✅ *No hay apagones de red reportados*", parse_mode="MarkdownV2")
        return

    lines = ["⚡ *APAGONES DE RED DETECTADOS*\n"]
    for o in outages[:10]:
        provider = o.get("provider", "Desconocido")
        asn = o.get("asn", "N/A")
        drop = o.get("drop_percentage", 0)
        severity = o.get("severity", "info")
        icon = "🔴" if severity in ("critical", "critico") else "🟠"
        ts = o.get("timestamp", "")
        lines.append(f"{icon} *{provider}* \\(AS{asn}\\)")
        lines.append(f"   Drop: `{drop}%` | {ts[:16]}")

    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumen ejecutivo IA."""
    ctx = _load_cache()
    briefing = ctx.get("global_briefing", {})

    if not briefing or not isinstance(briefing, dict):
        await update.message.reply_text("ℹ️ *No hay briefing disponible*\nEl análisis IA aún no se ha completado.", parse_mode="MarkdownV2")
        return

    consensus = briefing.get("consensus") or briefing.get("global_briefing", {}).get("consensus", "")
    if not consensus:
        await update.message.reply_text("ℹ️ *Briefing vacío*\nEl agente IA no ha generado resumen aún.", parse_mode="MarkdownV2")
        return

    reliability = ctx.get("reliability_score", 100)
    color = "🟢" if reliability > 80 else "🟡" if reliability > 50 else "🔴"

    msg = (
        f"🧠 *BRIEFING EJECUTIVO COBALTO*\n\n"
        f"{consensus[:1500]}\n\n"
        f"{color} Fiabilidad: `{reliability}%`"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "CobaltoHub/7.1.1 (Red-Team Intelligence Feed)",
]

if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
    raise ValueError("ERROR: TELEGRAM_TOKEN y TELEGRAM_CHANNEL deben estar en .env")

_cached_keywords_list = None
_KEYWORD_PATTERNS = []

def get_keyword_patterns():
    global _cached_keywords_list, _KEYWORD_PATTERNS
    import config
    current_keywords = config.KEYWORDS
    if _cached_keywords_list != current_keywords:
        _KEYWORD_PATTERNS = [re.compile(r"\b" + re.escape(kw.lower()) + r"\b") for kw in current_keywords if kw]
        _cached_keywords_list = list(current_keywords)
    return _KEYWORD_PATTERNS

http_session = None
logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s")


def escape_markdown_v2(text):
    if not text:
        return ""
    reserved = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(reserved)}])", r"\\\1", str(text))


async def get_image_candidates(entry):
    candidates = []
    if "media_content" in entry:
        for media in entry.media_content:
            if media.get("medium") == "image" and media.get("url"):
                candidates.append(media["url"])
    if "enclosures" in entry:
        for enc in entry.enclosures:
            if "image" in enc.get("type", "").lower() and enc.get("href"):
                candidates.append(enc["href"])
    if "media_thumbnail" in entry:
        thumb = entry.media_thumbnail
        if isinstance(thumb, list) and thumb:
            candidates.append(thumb[0].get("url", ""))
        elif isinstance(thumb, dict) and thumb.get("url"):
            candidates.append(thumb["url"])

    content = entry.get("content", [{}])[0].get("value") or entry.get("summary", "") or entry.get("description", "")
    if content:
        matches = re.findall(r'<img[^>]+src=["\'](.*?)["\']', content, re.IGNORECASE)
        candidates.extend(matches[:3])

    return list(dict.fromkeys(candidates))


async def validate_and_get_image(image_url):
    if not image_url or not http_session:
        return None
    try:
        async with http_session.get(image_url, timeout=ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
            if resp.status != 200:
                return None
            content_type = resp.headers.get("content-type", "").lower()
            if not any(x in content_type for x in ["jpeg", "png", "webp", "jpg"]):
                return None
            data = await resp.read()
            if len(data) < 25 * 1024:
                return None
            img = Image.open(BytesIO(data))
            width, height = img.size
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                return None
            return data
    except Exception:
        return None


async def send_news(bot, title, source, link, summary, published, image_data=None):
    title_esc = escape_markdown_v2(title)
    source_esc = escape_markdown_v2(source)
    summary_esc = escape_markdown_v2(summary[:400])
    caption = f"📰 *{title_esc}*\n**{source_esc}** • {published}\n\n{summary_esc}...\n\n🔗 {link}"

    if image_data:
        for attempt in range(2):
            try:
                await bot.send_photo(
                    chat_id=TELEGRAM_CHANNEL, photo=image_data, caption=caption, parse_mode="MarkdownV2"
                )
                return True
            except TelegramError as e:
                if "parse entities" in str(e).lower():
                    logger.warning("MarkdownV2 fallo en foto -> fallback texto plano")
                    await bot.send_photo(
                        chat_id=TELEGRAM_CHANNEL,
                        photo=image_data,
                        caption=f"{title}\nFuente: {source}\n{published}\n{summary[:400]}...\n{link}",
                        parse_mode=None,
                    )
                    return True
                else:
                    logger.warning(f"Foto fallida intento {attempt + 1}: {e}")
                    await asyncio.sleep(3)

    for attempt in range(3):
        try:
            await bot.send_message(
                chat_id=TELEGRAM_CHANNEL, text=caption, parse_mode="MarkdownV2", disable_web_page_preview=False
            )
            return True
        except TelegramError as e:
            if "parse entities" in str(e).lower():
                logger.warning("MarkdownV2 fallo en texto -> fallback plano")
                await bot.send_message(
                    chat_id=TELEGRAM_CHANNEL,
                    text=f"{title}\nFuente: {source}\n{published}\n{summary[:400]}...\n{link}",
                    parse_mode=None,
                    disable_web_page_preview=False,
                )
                return True
            elif isinstance(e, RetryAfter):
                wait = e.retry_after + random.uniform(8, 18)
                logger.warning(f"Rate limit -> espera {wait:.1f}s")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"Envío texto fallido intento {attempt + 1}: {e}")
                await asyncio.sleep(5)

    return False


async def send_invitation_message(bot):
    message = (
        "🛡️ *Ciclo completado* – Noticias verificadas y listas para acción.\n\n"
        "Únete a nuestra red oficial para análisis profundos, "
        "alertas en tiempo real y más.\n\n"
        f"🔗 [Acceder ahora]({PAGINA_OFICIAL})\n"
        "Mantente alerta. Mantente conectado."
    )
    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHANNEL, text=message, parse_mode="MarkdownV2", disable_web_page_preview=True
        )
        logger.info("  Mensaje de invitacion enviado")
    except Exception as e:
        logger.warning(f"Invitación fallida: {e}")


async def generate_html_report(enviadas, noticias):
    if enviadas == 0:
        return
    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Cobalto Cycle Report</title>
    <style>
        body {{background:#0a0015; color:#00ffea; font-family: 'Courier New', monospace; margin:20px;}}
        h1 {{text-shadow: 0 0 10px #00ffea; color:#00ffea;}}
        ul {{list-style:none; padding:0;}}
        li {{margin:12px 0; padding:10px; border:1px solid #00ffea33; border-radius:6px; background:#0f002a;}}
        a {{color:#00ffea; text-decoration:none;}}
        a:hover {{text-shadow:0 0 8px #00ffea;}}
    </style>
</head>
<body>
    <h1>Cobalto News Cycle – {}</h1>
    <p>Noticias enviadas este ciclo: <strong>{}</strong></p>
    <ul>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), enviadas)

    for title, source, link in noticias:
        html += f'        <li><a href="{link}" target="_blank">{title[:80]}...</a> <small>— {source}</small></li>\n'

    html += """    </ul>
</body>
</html>"""

    (Path(__file__).parent / "cobalto_last_cycle.html").write_text(html, encoding="utf-8")
    logger.info("Reporte HTML cyberpunk generado -> cobalto_last_cycle.html")


async def fetch_and_send(context):
    bot = context.bot
    await asyncio.to_thread(clean_old_sent_news, max_days=3)
    enviadas = 0
    noticias_enviadas = []

    logger.info(f"\033[38;5;46mCiclo iniciado – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\033[0m")

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    for source, url in RSS_FEEDS.items():
        try:
            ua = random.choice(USER_AGENTS)
            feed = await asyncio.to_thread(feedparser.parse, url, agent=ua)
            if not feed.entries:
                continue

            candidatos = []
            for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
                title = entry.get("title", "Sin título").strip()
                link = entry.get("link", "#")
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                published_str = entry.get("published") or entry.get("updated") or str(datetime.now())

                pub_date = None
                published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                if published_parsed:
                    try:
                        pub_date = datetime.fromtimestamp(mktime(published_parsed)).date()
                    except Exception:
                        pass

                if pub_date is None and published_str:
                    try:
                        pub_date = dateutil_parser.parse(published_str, fuzzy=True).date()
                    except Exception:
                        pass

                if pub_date is None:
                    pub_date = today

                if pub_date not in (today, yesterday):
                    continue

                text = (title + summary).lower()
                if not any(p.search(text) for p in get_keyword_patterns()):
                    continue

                unique_id = f"{source}::{title[:120]}"
                if await asyncio.to_thread(is_news_sent, unique_id):
                    continue

                candidatos.append((entry, title, link, summary, published_str, unique_id))

            if not candidatos:
                continue

            selected = random.choice(candidatos)
            entry, title, link, summary, published, unique_id = selected

            image_candidates = await get_image_candidates(entry)
            image_data = None
            for img_url in image_candidates[:3]:
                image_data = await validate_and_get_image(img_url)
                if image_data:
                    break

            delay = random.uniform(8, 14) if image_data else random.uniform(6, 11)

            success = False
            backoff = 8
            for attempt in range(4):
                try:
                    success = await send_news(bot, title, source, link, summary, published, image_data)
                    if success:
                        await asyncio.to_thread(mark_news_sent, unique_id)
                        enviadas += 1
                        noticias_enviadas.append((title, source, link))
                        logger.info(
                            f"  \033[38;5;46m[OK] Enviado\033[0m {'[IMG]' if image_data else ''} | {title[:60]}..."
                        )
                        await asyncio.sleep(delay)
                        break
                except RetryAfter as e:
                    wait = e.retry_after + random.uniform(10, 25)
                    logger.warning(f"Rate limit -> espera {wait:.1f}s")
                    await asyncio.sleep(wait)
                except Exception as e:
                    logger.error(f"Error envío intento {attempt + 1}: {e}")
                    await asyncio.sleep(backoff)
                    backoff *= 1.6

        except Exception as e:
            logger.error(f"Error procesando {source}: {e}")

    logger.info(f"\033[38;5;46mCiclo terminado – {enviadas} noticias enviadas\033[0m")

    if enviadas > 0:
        await send_invitation_message(bot)
        await generate_html_report(enviadas, noticias_enviadas)


async def scheduled_task(context):
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=ClientTimeout(total=REQUEST_TIMEOUT))
    await fetch_and_send(context)


def main():
    logger.info("\033[38;5;201m=== COBALTO TELEGRAM v9.4 – Application Edition ===\033[0m")
    logger.info(f"Canal: {TELEGRAM_CHANNEL} | Ciclo: {INTERVALO_MINUTOS} min | Arquitectura JobQueue + C4I")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # ── Comandos C4I ──
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("alerts", cmd_alerts))
    application.add_handler(CommandHandler("search", cmd_search))
    application.add_handler(CommandHandler("outages", cmd_outages))
    application.add_handler(CommandHandler("briefing", cmd_briefing))

    interval_seconds = INTERVALO_MINUTOS * 60
    application.job_queue.run_repeating(scheduled_task, interval=interval_seconds, first=5)

    try:
        application.run_polling()
    finally:
        logger.info("Detenido por usuario. Limpiando...")
        if http_session and not http_session.closed:
            # En un entorno no asíncrono, cerrar la sesión requiere correr el loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(http_session.close())
                else:
                    loop.run_until_complete(http_session.close())
            except Exception:
                pass
        logger.info("Sesión cerrada – perímetro seguro.")


if __name__ == "__main__":
    main()
