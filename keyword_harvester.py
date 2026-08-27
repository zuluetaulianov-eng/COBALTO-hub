"""
keyword_harvester.py - Motor de Cosecha y Auto-Alimentación de Términos Emergentes

Analiza el flujo continuo de inteligencia extraída para descubrir palabras clave,
hashtags, acrónimos y entidades emergentes en tiempo real por teatro operacional.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import get_connection

logger = logging.getLogger(__name__)

# Stopwords comunes en español y términos genéricos a ignorar
SPANISH_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a", "ante",
    "bajo", "cabe", "con", "contra", "desde", "sin", "sobre", "tras", "en", "entre",
    "hacia", "hasta", "para", "por", "según", "y", "o", "u", "e", "ni", "que", "si",
    "no", "se", "su", "sus", "como", "mas", "más", "pero", "este", "esta", "estos",
    "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "fue", "han", "ha",
    "son", "ser", "esta", "está", "están", "hubo", "hacer", "decir", "sobre", "tras",
    "tras", "cada", "mismo", "misma", "donde", "cuando", "quien", "quienes", "cual",
    "noticias", "reporte", "informe", "lunes", "martes", "miércoles", "jueves", "viernes",
    "sábado", "domingo", "hoy", "ayer", "mañana", "luego", "años", "año", "días", "día",
}


def harvest_emerging_keywords(
    hours_back: int = 48,
    theater_filter: Optional[str] = None,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    Cosecha y retorna los términos y palabras clave emergentes más frecuentes
    extraídas del flujo reciente de noticias e inteligencia.

    Args:
        hours_back: Ventana de tiempo a analizar en horas (default: 48h).
        theater_filter: Filtro por teatro ('COL', 'VEN', 'GLOBAL' o None).
        top_n: Número de términos a retornar.

    Returns:
        Lista de diccionarios con el término, frecuencia y tendencia.
    """
    cutoff_dt = datetime.now() - timedelta(hours=hours_back)
    text_corpus = []

    try:
        import historical_store
        hist_data = historical_store.query_range(from_dt=cutoff_dt, to_dt=datetime.now(), limit=500)
        entries = hist_data.get("entries", [])
        for entry in entries:
            c_tags = str(entry.get("country_tags") or "GLOBAL")
            if theater_filter and theater_filter != "ALL":
                if theater_filter not in c_tags and "GLOBAL" not in c_tags:
                    continue
            full_text = f"{entry.get('title') or ''} {entry.get('summary') or ''}"
            if full_text.strip():
                text_corpus.append(full_text)
    except Exception as e:
        logger.warning(f"[HARVESTER] Error leyendo almacenamiento histórico: {e}")

    if not text_corpus:
        return []

    # Extraer palabras, hashtags y términos compuestos
    word_counter = Counter()
    hashtag_counter = Counter()

    for text in text_corpus:
        # Extraer hashtags (#ejemplo)
        hashtags = re.findall(r"#\w+", text.lower())
        for ht in hashtags:
            if len(ht) > 2:
                hashtag_counter[ht] += 1

        # Limpiar y extraer palabras significativas (mínimo 4 caracteres)
        words = re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_-]{4,}\b", text.lower())
        for w in words:
            if w not in SPANISH_STOPWORDS and not w.isdigit():
                word_counter[w] += 1

    # Consolidar resultados
    emerging = []

    # 1. Hashtags emergentes (prioridad alta)
    for ht, count in hashtag_counter.most_common(5):
        emerging.append({
            "term": ht,
            "type": "HASHTAG",
            "frequency": count,
            "score": round(count * 1.5, 1),
        })

    # 2. Palabras clave más frecuentes
    for word, count in word_counter.most_common(top_n):
        if any(item["term"] == word for item in emerging):
            continue
        emerging.append({
            "term": word.upper(),
            "type": "KEYWORD",
            "frequency": count,
            "score": float(count),
        })

    # Ordenar por score descendente
    emerging.sort(key=lambda x: x["score"], reverse=True)
    return emerging[:top_n]


def get_emerging_summary_by_theater() -> Dict[str, List[Dict[str, Any]]]:
    """
    Retorna un resumen de términos emergentes desglosado por teatros operacionales.
    """
    return {
        "COL": harvest_emerging_keywords(theater_filter="COL", top_n=10),
        "VEN": harvest_emerging_keywords(theater_filter="VEN", top_n=10),
        "GLOBAL": harvest_emerging_keywords(theater_filter="GLOBAL", top_n=10),
    }
