# osint_alerts.py - Módulo 5: Sistema de Alertas Tácticas Ponderadas y Deduplicadas
# Detecta palabras clave, calcula scoring multivariable y agrupa eventos semánticamente.

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
SENT_ALERTS_FILE = str(BASE_DIR / "sent_alerts.json")
_sent_alerts_lock = threading.Lock()


def send_telegram_push(alert: Dict[str, Any]):
    """Envía una alerta táctica vía Telegram usando peticiones directas."""
    import config
    token = getattr(config, "TELEGRAM_TOKEN", None)
    chat_id = getattr(config, "TELEGRAM_PUSH_CHAT_ID", None)
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

        icon = "🚨" if "CRÍTICO" in alert.get("level", "") else "⚠️"
        msg = f"{icon} *ALERTA TÁCTICA: {alert.get('level', '')}*\n\n*{alert.get('title', '')}*\n{alert.get('summary', '')}\n\n[Ver fuente]({alert.get('link', '')})"
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
# MATRIZ DE ALERTAS — Palabras clave y Ponderación por Nivel
# ============================================================
ALERT_MATRIX = {
    "🔴 CRÍTICO": {
        "weight": 35,
        "keywords": [
            "apagón nacional", "apagón", "corte eléctrico", "blackout", "caída de red",
            "corte de fibra óptica", "falla de borde", "movilización militar", "estado de excepción",
            "toque de queda", "ley marcial", "golpe de estado", "golpe militar", "evacuación diplomática",
            "cierre de fronteras", "restricción de espacio aéreo", "muertos", "fallecidos", "masacre",
            "ejecución", "bomba", "atentado", "explosión", "0-day", "zero-day", "vulnerabilidad crítica",
            "ransomware", "shell upload", "admin access"
        ],
        "color": "#FF2D55",
        "icon": "🚨",
    },
    "🟠 URGENTE": {
        "weight": 20,
        "keywords": [
            "decreto presidencial", "providencia administrativa", "expropiación", "intervención",
            "adjudicación directa", "gaceta oficial extraordinaria", "inflación interanual", "déficit fiscal",
            "canasta básica", "reserva internacional", "liquidez monetaria", "devaluación", "desabastecimiento",
            "escasez de combustible", "puerto cerrado", "paralización de transporte", "desvío de carga",
            "sanciones ofac", "embargo comercial", "congelación de activos", "lista negra", "evasión de sanciones",
            "data breach", "exfiltración", "ataque ddos", "leak", "database dump", "credenciales expuestas",
            "protestas", "manifestación", "represión", "gas lacrimógeno", "incendio forestal", "anomalía térmica",
            "fuego masivo", "punto de calor"
        ],
        "color": "#FF9500",
        "icon": "⚠️",
    },
    "🔵 CYBER": {
        "weight": 25,
        "keywords": [
            "cve-2025", "cve-2026", "exploit", "malware", "phishing", "backdoor", "c2", "command and control",
            "inyección sql", "xss", "rce", "escalada de privilegios", "exfiltración", "movimiento lateral",
            "pastebin", "darkweb", "tor onion", "botnet"
        ],
        "color": "#00E5FF",
        "icon": "💻",
    },
    "🟡 ATENCIÓN": {
        "weight": 10,
        "keywords": [
            "gaceta oficial", "resolución", "licitación", "presupuesto aprobado", "contrato estatal",
            "asignación de recursos", "tasa de cambio", "dólar paralelo", "bcv", "pdvsa", "suministro eléctrico",
            "racionamiento eléctrico", "subestación", "notam", "tráfico marítimo", "buque sombra",
            "elecciones", "candidato", "campaña electoral", "cne", "acuerdo", "negociación", "diálogo",
            "reforma", "maduro", "machado", "edmundo", "fanb", "militares", "general", "colombia",
            "frontera", "migrantes"
        ],
        "color": "#FFCC00",
        "icon": "👁️",
    },
}

# Términos contextuales que otorgan un multiplicador / bonificación de severidad
CONTEXT_BOOSTERS = {
    "venezuela": 5, "caracas": 5, "maracaibo": 5, "valencia": 4, "zulia": 4, "tachira": 4,
    "fanb": 5, "sebin": 5, "dgcim": 5, "ofac": 5, "pdvsa": 4, "bcv": 4, "ceofanb": 5
}


def _normalize(text: str) -> str:
    """Normaliza texto para comparación (minúsculas, sin tildes)."""
    if not text:
        return ""
    t = text.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ñ", "n")]:
        t = t.replace(a, b)
    return t


def _tokenize(text: str) -> Set[str]:
    """Extrae palabras clave significativas para comparación de similitud."""
    clean = _normalize(text)
    words = re.findall(r"\b[a-z0-9_]{3,}\b", clean)
    stopwords = {"del", "los", "las", "por", "para", "con", "una", "uno", "unos", "unas", "que", "como", "mas", "sin", "sobre", "este", "esta", "entre"}
    return {w for w in words if w not in stopwords}


def compute_entry_threat_score(entry: Dict) -> Tuple[str, List[str], float]:
    """
    Calcula el puntaje de amenaza ponderado (0 - 100) y determina el nivel de alerta.
    Devuelve (level, matched_keywords, threat_score).
    """
    import config

    if entry.get("type") in ["adsb_high_interest", "vessel_high_interest", "ioda_outage"]:
        return "🔴 CRÍTICO", ["Rastreo Táctico HVT"], 95.0

    text = _normalize(f"{entry.get('title', '')} {entry.get('summary', '')}")
    matched_kws = []
    matched_levels = set()
    total_score = 0.0

    # Obtener palabras clave configuradas dinámicamente o por matriz por defecto
    critical_kws = getattr(config, "ALERT_CRITICAL_KEYWORDS", ALERT_MATRIX["🔴 CRÍTICO"]["keywords"])
    urgent_kws = getattr(config, "ALERT_URGENT_KEYWORDS", ALERT_MATRIX["🟠 URGENTE"]["keywords"])

    dynamic_matrix = {
        "🔴 CRÍTICO": {"weight": 35, "keywords": critical_kws},
        "🟠 URGENTE": {"weight": 20, "keywords": urgent_kws},
        "🔵 CYBER": {"weight": 25, "keywords": ALERT_MATRIX["🔵 CYBER"]["keywords"]},
        "🟡 ATENCIÓN": {"weight": 10, "keywords": ALERT_MATRIX["🟡 ATENCIÓN"]["keywords"]},
    }

    for lvl, cfg in dynamic_matrix.items():
        base_weight = cfg["weight"]
        found_in_lvl = 0
        for kw in cfg["keywords"]:
            norm_kw = _normalize(kw)
            pattern = re.compile(r"\b" + re.escape(norm_kw) + r"\b")
            if pattern.search(text):
                if kw not in matched_kws:
                    matched_kws.append(kw)
                found_in_lvl += 1

        if found_in_lvl > 0:
            matched_levels.add(lvl)
            # Primer keyword del nivel otorga el peso completo, subsiguientes agregan bonus
            total_score += base_weight + (found_in_lvl - 1) * 5

    # Aplicar bonificadores de contexto estratégico
    for context_word, boost in CONTEXT_BOOSTERS.items():
        if re.search(r"\b" + re.escape(context_word) + r"\b", text):
            total_score += boost

    # Normalizar puntaje máximo a 100
    final_score = min(round(total_score, 1), 100.0)

    # Clasificación por nivel de severidad basado en scoring
    if "🔴 CRÍTICO" in matched_levels or final_score >= 45.0:
        level = "🔴 CRÍTICO"
    elif "🟠 URGENTE" in matched_levels or final_score >= 28.0:
        level = "🟠 URGENTE"
    elif "🔵 CYBER" in matched_levels or final_score >= 22.0:
        level = "🔵 CYBER"
    elif "🟡 ATENCIÓN" in matched_levels or final_score >= 12.0:
        level = "🟡 ATENCIÓN"
    else:
        level = ""

    return level, matched_kws, final_score


def analyze_entry(entry: Dict) -> Tuple[str, List[str]]:
    """Función de compatibilidad que invoca el motor de scoring."""
    level, keywords, _ = compute_entry_threat_score(entry)
    return level, keywords


def generate_alerts(all_entries: List[Dict]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Procesa las noticias, calcula el scoring de amenaza y aplica deduplicación
    semántica por superposición de tokens Jaccard.
    """
    alerts: List[Dict[str, Any]] = []

    for entry in all_entries:
        title = entry.get("title", "")
        if not title:
            continue

        level, keywords, score = compute_entry_threat_score(entry)
        if not level:
            continue

        entry_tokens = _tokenize(title)

        # Deduplicación semántica contra alertas previamente aceptadas
        is_duplicate = False
        for existing in alerts:
            existing_tokens = existing.get("_tokens", set())
            if not existing_tokens or not entry_tokens:
                continue

            intersection = entry_tokens.intersection(existing_tokens)
            union = entry_tokens.union(existing_tokens)
            similarity = len(intersection) / float(len(union)) if union else 0.0

            # Umbral de similitud semántica (>= 50% de palabras compartidas)
            if similarity >= 0.50 or _normalize(title) == _normalize(existing["title"]):
                is_duplicate = True
                existing["sources_count"] = existing.get("sources_count", 1) + 1
                rel_sources = existing.setdefault("related_sources", [])
                src_name = entry.get("source", "Desconocido")
                if src_name not in rel_sources:
                    rel_sources.append(src_name)

                # Si el duplicado tiene mayor puntaje de amenaza, actualizar nivel
                if score > existing.get("score", 0):
                    existing["score"] = score
                    existing["level"] = level
                    config_level = ALERT_MATRIX.get(level, ALERT_MATRIX["🟡 ATENCIÓN"])
                    existing["color"] = config_level["color"]
                    existing["icon"] = config_level["icon"]
                break

        if not is_duplicate:
            config_level = ALERT_MATRIX.get(level, ALERT_MATRIX["🟡 ATENCIÓN"])
            alert_item = {
                "level": level,
                "score": score,
                "color": config_level["color"],
                "icon": config_level["icon"],
                "keywords": keywords[:5],
                "title": title,
                "summary": entry.get("summary", "")[:200],
                "link": entry.get("link", "#"),
                "source": entry.get("source", ""),
                "sources_count": 1,
                "related_sources": [entry.get("source", "")],
                "published": entry.get("published", ""),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "_tokens": entry_tokens
            }

            if "CRÍTICO" in level:
                send_telegram_push(alert_item)

            alerts.append(alert_item)

    # Limpiar campo auxiliar _tokens antes de retornar
    for a in alerts:
        a.pop("_tokens", None)

    # Ordenar por Severidad y Puntaje de Amenaza (Mayor a Menor)
    order = {"🔴 CRÍTICO": 0, "🟠 URGENTE": 1, "🔵 CYBER": 2, "🟡 ATENCIÓN": 3}
    alerts.sort(key=lambda x: (order.get(x["level"], 4), -x.get("score", 0)))

    counts = {
        "critico": sum(1 for a in alerts if "CRÍTICO" in a["level"]),
        "urgente": sum(1 for a in alerts if "URGENTE" in a["level"]),
        "cyber": sum(1 for a in alerts if "CYBER" in a["level"]),
        "atencion": sum(1 for a in alerts if "ATENCIÓN" in a["level"]),
        "total": len(alerts),
    }

    if alerts:
        logger.info(
            f"[ALERTAS] Generadas: {counts['critico']} críticas | {counts['urgente']} urgentes | {counts['cyber']} cyber | {counts['atencion']} atención"
        )

    return alerts, counts


def get_alert_summary(alerts: List[Dict]) -> str:
    """Genera un resumen HTML compacto para el widget de alertas del dashboard."""
    if not alerts:
        return "<span style='color:#aaa'>Sin alertas activas</span>"

    lines = []
    for a in alerts[:5]:
        kws = ", ".join(a.get("keywords", [])[:3])
        sources_info = f" ({a.get('sources_count', 1)} fuentes)" if a.get("sources_count", 1) > 1 else ""
        lines.append(
            f"<div style='color:{a['color']};margin:4px 0'>"
            f"{a['icon']} <b>{a['level']}</b> [{a.get('score', 0)} pts] — "
            f"<a href='{a['link']}' target='_blank' style='color:inherit'>{a['title'][:70]}...</a>"
            f"<br><small style='opacity:.7'>Detectado: {kws} | {a['source']}{sources_info}</small>"
            f"</div>"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=== TEST MÓDULO ALERTAS PONDERADAS Y DEDUPLICADAS ===")
    test_entries = [
        {
            "title": "Apagón masivo en Caracas deja sin luz a millones de usuarios",
            "summary": "El corte eléctrico afectó el sistema nacional...",
            "source": "El Nacional",
            "link": "https://example.com/1",
        },
        {
            "title": "Sin luz en Caracas por grave apagón masivo",
            "summary": "Reportan falla eléctrica nacional en la capital...",
            "source": "Lapatilla",
            "link": "https://example.com/2",
        },
        {
            "title": "Protestas en Maracaibo por escasez de gasolina",
            "summary": "Manifestaciones en la ciudad por combustible...",
            "source": "Panorama",
            "link": "https://example.com/3",
        },
        {
            "title": "Ataque Ransomware compromete servidores de entidad petrolera con 0-day",
            "summary": "Exfiltración de credenciales detectada...",
            "source": "CyberNews",
            "link": "https://example.com/4",
        },
    ]
    alerts, counts = generate_alerts(test_entries)
    print(f"Alertas generadas: {counts}")
    for a in alerts:
        print(f"  [{a['level']}] (Score: {a['score']}): {a['title']}")
        print(f"     Fuentes detectadas ({a['sources_count']}): {', '.join(a['related_sources'])}")
        print(f"     Palabras clave: {a['keywords']}")
