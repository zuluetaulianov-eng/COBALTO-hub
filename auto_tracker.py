"""
auto_tracker.py - Motor de Auto-Ingestión y Seguimiento Activo de Objetivos y Temas

Cuando el sistema detecta individuos, entidades u organizaciones emergentes de alto interés
(o términos/hashtags con aceleración atípica), los auto-registra en la lista de seguimiento activo.
Esto permite que los siguientes ciclos de extracción (RSS, Telegram, OSINT) monitoreen automáticamente
dichos temas e individuos sin requerir intervención manual del operador.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

import entity_registry
import keyword_harvester
from database import get_connection

logger = logging.getLogger(__name__)

AUTO_TRACKED_FILE = Path("data/auto_tracked_keywords.json")


def load_auto_tracked_keywords() -> List[Dict[str, Any]]:
    """Carga la lista de palabras clave y temas auto-detectados y seguidos."""
    if not AUTO_TRACKED_FILE.exists():
        return []
    try:
        with open(AUTO_TRACKED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[AUTO_TRACKER] Error cargando auto_tracked_keywords.json: {e}")
        return []


def save_auto_tracked_keywords(keywords: List[Dict[str, Any]]) -> bool:
    """Guarda la lista de temas auto-detectados."""
    try:
        AUTO_TRACKED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTO_TRACKED_FILE, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"[AUTO_TRACKER] Error guardando auto_tracked_keywords.json: {e}")
        return False


def get_active_auto_keywords_set() -> Set[str]:
    """Retorna un set con los términos emergentes actualmente bajo seguimiento activo."""
    kw_list = load_auto_tracked_keywords()
    return {k["term"].lower() for k in kw_list if k.get("active", True)}


def process_auto_ingestion(min_frequency: int = 3) -> Dict[str, Any]:
    """
    Analiza los hallazgos recientes, auto-registra nuevos individuos de interés en el
    Entity Registry y agrega palabras clave emergentes de alta frecuencia al motor de monitoreo.

    Returns:
        Diccionario con las estadísticas del ciclo de auto-ingestión.
    """
    stats = {
        "new_entities_registered": 0,
        "new_keywords_tracked": 0,
        "total_active_keywords": 0,
    }

    # 1. Cosechar términos emergentes recientes
    harvested = keyword_harvester.harvest_emerging_keywords(hours_back=48, top_n=30)
    existing_kw = load_auto_tracked_keywords()
    existing_terms = {k["term"].lower(): k for k in existing_kw}

    new_additions = False

    for item in harvested:
        term = item["term"].strip()
        term_lower = term.lower()
        freq = item.get("frequency", 0)

        # Si el término tiene suficiente frecuencia y no está registrado
        if freq >= min_frequency and term_lower not in existing_terms:
            existing_kw.append({
                "term": term,
                "type": item.get("type", "KEYWORD"),
                "frequency": freq,
                "score": item.get("score", 0.0),
                "added_at": keyword_harvester.datetime.now().isoformat(),
                "active": True,
            })
            existing_terms[term_lower] = existing_kw[-1]
            stats["new_keywords_tracked"] += 1
            new_additions = True
            logger.info(f"[AUTO_TRACKER] Auto-ingresado nuevo tema de interés: '{term}' (Freq: {freq})")

    if new_additions:
        # Mantener un máximo de 50 palabras clave auto-seguidas
        existing_kw.sort(key=lambda x: x.get("score", 0), reverse=True)
        existing_kw = existing_kw[:50]
        save_auto_tracked_keywords(existing_kw)

    stats["total_active_keywords"] = len(existing_kw)

    # 2. Auto-Registrar Individuos / Entidades de Interés en Entity Registry
    try:
        with get_connection() as conn:
            # Verificar existencia de la tabla humint_reports
            tables = [row[0] for row in conn.fetchall("SELECT name FROM sqlite_master WHERE type='table' AND name='humint_reports'")]
            if tables:
                rows = conn.fetchall(
                    """
                    SELECT summary, details FROM humint_reports
                    WHERE severity IN ('critica', 'alta')
                    ORDER BY created_at DESC LIMIT 20
                    """
                )
                for r in rows:
                    text = f"{r[0] or ''} {r[1] or ''}"
                    words = [w for w in text.split() if w.istitle() and len(w) > 3]
                    if len(words) >= 2:
                        potential_name = " ".join(words[:2])
                        existing_ent = entity_registry.search_entities(potential_name, limit=1)
                        if not existing_ent:
                            entity_registry.register_entity(
                                canonical_name=potential_name,
                                entity_type="PERSON",
                                aliases=[],
                                wikidata_id=None,
                                ofac_flag=False,
                            )
                            stats["new_entities_registered"] += 1
                            logger.info(f"[AUTO_TRACKER] Auto-registrado individuo de interés HUMINT: '{potential_name}'")
    except Exception as e:
        logger.debug(f"[AUTO_TRACKER] Auto-registro de entidades omitido: {e}")

    return stats
