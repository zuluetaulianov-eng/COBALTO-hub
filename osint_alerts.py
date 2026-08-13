# osint_alerts.py - Módulo 5: Sistema de Alertas Tácticas
# Detecta palabras clave críticas en las noticias y genera alertas

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
SENT_ALERTS_FILE = str(BASE_DIR / "sent_alerts.json")
_sent_alerts_lock = threading.Lock()


def send_telegram_push(alert: Dict[str, Any]):
    """Envía una alerta táctica vía Telegram usando peticiones directas."""
    import config
    token = config.TELEGRAM_TOKEN
    chat_id = config.TELEGRAM_PUSH_CHAT_ID
    if not token or not chat_id:
        logger.warning("[ALERTAS] TELEGRAM_TOKEN o TELEGRAM_PUSH_CHAT_ID no configurados")
        return

    with _sent_alerts_lock:
        try:
            if os.path.exists(SENT_ALERTS_FILE):
                with open(SENT_ALERTS_FILE, "r", encoding="utf-8") as f:
                    sent = json.load(f)
            else:
                sent = []
        except Exception:
            sent = []

        link_id = alert.get("link", "")
        title_id = alert.get("title", "")
        if link_id in sent or title_id in sent:
            return

        icon = "🚨" if "CRÍTICO" in alert["level"] else "⚠️"
        msg = f"{icon} *ALERTA TÁCTICA: {alert['level']}*\n\n*{alert['title']}*\n{alert['summary']}\n\n[Ver fuente]({alert['link']})"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}

        try:
            resp = requests.post(url, json=payload, timeout=5)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                sent.append(link_id)
                sent.append(title_id)
                with open(SENT_ALERTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(sent[-100:], f)
            else:
                logger.warning(f"[ALERTAS] Telegram API error: {data}")
        except Exception as e:
            logger.warning(f"[ALERTAS] Error enviando Push: {e}")


# ============================================================
# MATRIZ DE ALERTAS — Palabras clave por nivel de severidad
# ============================================================
ALERT_MATRIX = {
    # ── NIVEL 1: CRÍTICO — Requiere acción inmediata ─────────────────────
    "🔴 CRÍTICO": {
        "keywords": [
            # Infraestructura
            "apagón nacional",
            "apagón",
            "corte eléctrico",
            "blackout",
            "caída de red",
            "corte de fibra óptica",
            "falla de borde",
            # Seguridad / Conflicto
            "movilización militar",
            "estado de excepción",
            "toque de queda",
            "ley marcial",
            "golpe de estado",
            "golpe militar",
            "evacuación diplomática",
            "cierre de fronteras",
            "restricción de espacio aéreo",
            "muertos",
            "fallecidos",
            "masacre",
            "ejecución",
            "bomba",
            "atentado",
            "explosión",
            # Ciberseguridad
            "0-day",
            "zero-day",
            "vulnerabilidad crítica",
            "ransomware",
            "shell upload",
            "admin access",
        ],
        "color": "#FF2D55",
        "icon": "🚨",
    },
    # ── NIVEL 2: URGENTE — Alta prioridad de monitoreo ───────────────────
    "🟠 URGENTE": {
        "keywords": [
            # Legal / Gobierno
            "decreto presidencial",
            "providencia administrativa",
            "expropiación",
            "intervención",
            "adjudicación directa",
            "gaceta oficial extraordinaria",
            # Economía
            "inflación interanual",
            "déficit fiscal",
            "canasta básica",
            "reserva internacional",
            "liquidez monetaria",
            "devaluación",
            # Logística
            "desabastecimiento",
            "escasez de combustible",
            "puerto cerrado",
            "paralización de transporte",
            "desvío de carga",
            # Sanciones
            "sanciones ofac",
            "embargo comercial",
            "congelación de activos",
            "lista negra",
            "evasión de sanciones",
            # Ciberseguridad
            "data breach",
            "exfiltración",
            "ataque ddos",
            "leak",
            "database dump",
            "credenciales expuestas",
            # Protesta
            "protestas",
            "manifestación",
            "represión",
            "gas lacrimógeno",
            # Desastres / Satélite (NASA FIRMS integration)
            "incendio forestal",
            "anomalía térmica",
            "fuego masivo",
            "punto de calor",
        ],
        "color": "#FF9500",
        "icon": "⚠️",
    },
    # ── NIVEL 3: ATENCIÓN — Monitoreo activo ─────────────────────────────
    "🟡 ATENCIÓN": {
        "keywords": [
            # Legal / Gobierno
            "gaceta oficial",
            "resolución",
            "licitación",
            "presupuesto aprobado",
            "contrato estatal",
            "asignación de recursos",
            # Economía
            "tasa de cambio",
            "dólar paralelo",
            "bcv",
            "pdvsa",
            "suministro eléctrico",
            "racionamiento eléctrico",
            "subestación",
            # Internacional
            "notam",
            "tráfico marítimo",
            "buque sombra",
            "cve-2025",
            "cve-2026",
            "vulnerabilidad",
            # Política
            "elecciones",
            "candidato",
            "campaña electoral",
            "cne",
            "acuerdo",
            "negociación",
            "diálogo",
            "reforma",
            # Actores clave Venezuela
            "maduro",
            "machado",
            "edmundo",
            "fanb",
            "militares",
            "general",
            "colombia",
            "frontera",
            "migrantes",
        ],
        "color": "#FFCC00",
        "icon": "👁️",
    },
    # ── NIVEL 4: CYBER — Inteligencia de ciberseguridad ──────────────────
    "🔵 CYBER": {
        "keywords": [
            "cve-2025",
            "cve-2026",
            "exploit",
            "malware",
            "phishing",
            "backdoor",
            "c2",
            "command and control",
            "inyección sql",
            "xss",
            "rce",
            "escalada de privilegios",
            "exfiltración",
            "movimiento lateral",
        ],
        "color": "#00E5FF",
        "icon": "💻",
    },
}


def _normalize(text: str) -> str:
    """Normaliza texto para comparación (minúsculas, sin tildes)."""
    t = text.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ñ", "n")]:
        t = t.replace(a, b)
    return t


# Precompilar patrones de búsqueda al cargar módulo
_ALERT_PATTERNS = {}
for _level, _config in ALERT_MATRIX.items():
    _compiled = []
    for _kw in _config["keywords"]:
        _compiled.append((_kw, re.compile(r"\b" + re.escape(_normalize(_kw)) + r"\b")))
    _ALERT_PATTERNS[_level] = _compiled


def analyze_entry(entry: Dict) -> Tuple[str, List[str]]:
    import config
    if entry.get("type") in ["adsb_high_interest", "vessel_high_interest", "ioda_outage"]:
        return "🔴 CRÍTICO", ["Rastreo Táctico HVT"]

    text = _normalize(f"{entry.get('title', '')} {entry.get('summary', '')}")

    # Re-compilar dinámicamente si los keywords cambian o usar una matriz local
    matrix = {
        "🔴 CRÍTICO": {
            "keywords": config.ALERT_CRITICAL_KEYWORDS,
        },
        "🟠 URGENTE": {
            "keywords": config.ALERT_URGENT_KEYWORDS,
        },
        "🟡 ATENCIÓN": {
            "keywords": ALERT_MATRIX["🟡 ATENCIÓN"]["keywords"],
        },
        "🔵 CYBER": {
            "keywords": ALERT_MATRIX["🔵 CYBER"]["keywords"],
        }
    }

    for level, cfg in matrix.items():
        found = []
        for kw in cfg["keywords"]:
            pattern = re.compile(r"\b" + re.escape(_normalize(kw)) + r"\b")
            if pattern.search(text):
                found.append(kw)
        if found:
            return level, found
    return "", []


def generate_alerts(all_entries: List[Dict]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Procesa todas las noticias y genera lista de alertas tácticas.
    Solo devuelve noticias que dispararon al menos una palabra clave.
    """
    alerts = []
    seen_titles = set()

    for entry in all_entries:
        title = entry.get("title", "")
        if title in seen_titles:
            continue

        level, keywords = analyze_entry(entry)
        if level:
            seen_titles.add(title)
            config = ALERT_MATRIX[level]
            alert_item = {
                "level": level,
                "color": config["color"],
                "icon": config["icon"],
                "keywords": keywords[:5],  # máx 5 palabras clave mostradas
                "title": title,
                "summary": entry.get("summary", "")[:200],
                "link": entry.get("link", "#"),
                "source": entry.get("source", ""),
                "published": entry.get("published", ""),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }

            # Enviar PUSH automático si es nivel CRÍTICO
            if "CRÍTICO" in level:
                send_telegram_push(alert_item)

            alerts.append(alert_item)

    # Ordenar: CRÍTICO > URGENTE > ATENCIÓN
    order = {"🔴 CRÍTICO": 0, "🟠 URGENTE": 1, "🔵 CYBER": 2, "🟡 ATENCIÓN": 3}
    alerts.sort(key=lambda x: order.get(x["level"], 4))

    counts = {
        "critico": sum(1 for a in alerts if "CRÍTICO" in a["level"]),
        "urgente": sum(1 for a in alerts if "URGENTE" in a["level"]),
        "cyber": sum(1 for a in alerts if "CYBER" in a["level"]),
        "atencion": sum(1 for a in alerts if "ATENCIÓN" in a["level"]),
        "total": len(alerts),
    }

    if alerts:
        print(
            f"[ALERTAS] {counts['critico']} criticas | {counts['urgente']} urgentes | {counts['cyber']} cyber | {counts['atencion']} atencion"
        )

    return alerts, counts


def get_alert_summary(alerts: List[Dict]) -> str:
    """Genera un resumen HTML compacto para el widget de alertas del dashboard."""
    if not alerts:
        return "<span style='color:#aaa'>Sin alertas activas</span>"

    lines = []
    for a in alerts[:5]:
        kws = ", ".join(a["keywords"][:3])
        lines.append(
            f"<div style='color:{a['color']};margin:4px 0'>"
            f"{a['icon']} <b>{a['level']}</b> — "
            f"<a href='{a['link']}' target='_blank' style='color:inherit'>{a['title'][:70]}...</a>"
            f"<br><small style='opacity:.7'>Detectado: {kws} | {a['source']}</small>"
            f"</div>"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print("=== TEST MÓDULO ALERTAS ===")
    test_entries = [
        {
            "title": "Apagón masivo en Caracas deja sin luz a millones",
            "summary": "El corte eléctrico afectó...",
            "source": "Test",
            "link": "#",
        },
        {
            "title": "Protestas en Maracaibo por escasez de gasolina",
            "summary": "Manifestaciones en la ciudad...",
            "source": "Test",
            "link": "#",
        },
        {
            "title": "Maduro firmó decreto sobre petróleo",
            "summary": "El presidente anunció...",
            "source": "Test",
            "link": "#",
        },
        {
            "title": "Venezuela clasifica al mundial de fútbol",
            "summary": "La selección vinotinto...",
            "source": "Test",
            "link": "#",
        },
    ]
    alerts, counts = generate_alerts(test_entries)
    print(f"Alertas generadas: {counts}")
    for a in alerts:
        print(f"  {a['icon']} {a['level']}: {a['title'][:60]}")
        print(f"     Keywords: {a['keywords']}")
