"""
dossier_engine.py - Motor de Expedientes Tácticos 360° para Personas e Instituciones de Interés

Consolida la inteligencia distribuida en COBALTO HUB (Noticias, Redes, FININT, HUMINT,
Sanciones OFAC SDN, Wikidata, Sensores) para generar expedientes holísticos de objetivos.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import get_connection

logger = logging.getLogger(__name__)


def build_target_dossier(target_query: str, theater_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Construye un expediente táctico 360° para una persona o institución.

    Args:
        target_query: Nombre, alias, username o ID del objetivo/institución.
        theater_filter: Opcional ('COL', 'VEN', 'GLOBAL').

    Returns:
        Diccionario estructurado con la ficha táctica completa.
    """
    query_clean = target_query.strip().lower()
    now_iso = datetime.now().isoformat()

    dossier = {
        "query": target_query,
        "generated_at": now_iso,
        "profile": {
            "name": target_query,
            "aliases": [],
            "entity_type": "UNKNOWN",  # PERSON, ORGANIZATION, INSTITUTION, FINANCIAL
            "ofac_flag": False,
            "wikidata_id": None,
            "country_tags": [],
            "risk_score": 0.0,
            "risk_level": "ESTABLE",  # CRÍTICO, ALERTA, ELEVADO, ESTABLE
        },
        "metrics": {
            "total_mentions": 0,
            "recent_24h_mentions": 0,
            "sentiment_score": 0.0,  # -1.0 a +1.0
            "media_pressure": "BAJA",
            "finint_exposure": False,
            "humint_reports_count": 0,
        },
        "timeline": [],
        "associated_entities": [],
        "related_incidents": [],
        "recent_sources": [],
    }

    # 1. Buscar en Entity Registry
    try:
        import entity_registry
        reg_entity = entity_registry.search_entities(query_clean, limit=1)
        if reg_entity:
            ent = reg_entity[0]
            dossier["profile"]["name"] = ent.get("canonical_name", target_query)
            dossier["profile"]["entity_type"] = ent.get("entity_type", "PERSON").upper()
            dossier["profile"]["ofac_flag"] = bool(ent.get("ofac_flag", False))
            dossier["profile"]["wikidata_id"] = ent.get("wikidata_id")
            if ent.get("aliases"):
                dossier["profile"]["aliases"] = ent.get("aliases")
    except Exception as e:
        logger.warning(f"[DOSSIER] Error buscando en entity_registry: {e}")

    # 2. Buscar menciones en Base de Datos Principal / Caché Histórica
    entries_found = []
    try:
        with get_connection() as conn:
            # Buscar en noticias/reportes procesados
            rows = conn.fetchall(
                """
                SELECT title, summary, link, source, published, country_tags
                FROM sent_news
                WHERE lower(title) LIKE ? OR lower(summary) LIKE ?
                ORDER BY published DESC LIMIT 50
                """,
                (f"%{query_clean}%", f"%{query_clean}%"),
            )
            for r in rows:
                entries_found.append({
                    "title": r[0],
                    "summary": r[1],
                    "link": r[2],
                    "source": r[3],
                    "published": r[4],
                    "country_tags": r[5] or "GLOBAL",
                })
    except Exception as e:
        logger.warning(f"[DOSSIER] Error consultando sent_news: {e}")

    # Fallback/Complemento: Buscar en historical_store si está disponible
    try:
        import historical_store
        hist_results = historical_store.query_historical(search=query_clean, limit=30)
        for h in hist_results:
            entries_found.append({
                "title": h.get("title", "Reporte Histórico"),
                "summary": h.get("summary", ""),
                "link": h.get("url", "#"),
                "source": h.get("source", "Historical Store"),
                "published": h.get("timestamp", now_iso),
                "country_tags": h.get("country_tags", "GLOBAL"),
            })
    except Exception as e:
        logger.warning(f"[DOSSIER] Error consultando historical_store: {e}")

    # Deduplicar entradas por título/link
    seen_keys = set()
    unique_entries = []
    for e in entries_found:
        k = (e["title"], e["link"])
        if k not in seen_keys:
            seen_keys.add(k)
            unique_entries.append(e)

    # 3. Filtrar por Teatro Operacional si fue especificado
    if theater_filter and theater_filter != "ALL":
        unique_entries = [
            e for e in unique_entries
            if theater_filter in str(e.get("country_tags", "")) or "GLOBAL" in str(e.get("country_tags", ""))
        ]

    dossier["metrics"]["total_mentions"] = len(unique_entries)

    # 4. Calcular Métricas de Menciones 24h y Presión Mediática
    cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    mentions_24h = [e for e in unique_entries if str(e.get("published", "")) >= cutoff_24h]
    dossier["metrics"]["recent_24h_mentions"] = len(mentions_24h)

    if len(mentions_24h) >= 10:
        dossier["metrics"]["media_pressure"] = "ALTA"
    elif len(mentions_24h) >= 3:
        dossier["metrics"]["media_pressure"] = "MODERADA"
    else:
        dossier["metrics"]["media_pressure"] = "BAJA"

    # 5. Generar Línea de Tiempo de Intervenciones y Eventos
    for e in unique_entries[:20]:
        dossier["timeline"].append({
            "timestamp": e.get("published", now_iso),
            "title": e.get("title", ""),
            "summary": e.get("summary", "")[:200],
            "source": e.get("source", ""),
            "link": e.get("link", "#"),
        })

    # 6. Consultar HUMINT Reports
    try:
        with get_connection() as conn:
            humint_rows = conn.fetchall(
                """
                SELECT id, summary, severity, created_at, source_user
                FROM humint_reports
                WHERE lower(summary) LIKE ? OR lower(details) LIKE ?
                ORDER BY created_at DESC LIMIT 10
                """,
                (f"%{query_clean}%", f"%{query_clean}%"),
            )
            dossier["metrics"]["humint_reports_count"] = len(humint_rows)
            for hr in humint_rows:
                dossier["related_incidents"].append({
                    "id": hr[0],
                    "type": "HUMINT",
                    "summary": hr[1],
                    "severity": hr[2],
                    "timestamp": hr[3],
                })
    except Exception:
        pass

    # 7. Consultar FININT / Wallets & DarkWeb Exposure
    try:
        with get_connection() as conn:
            finint_rows = conn.fetchall(
                """
                SELECT address, chain, ofac_sanctioned, label
                FROM finint_wallets
                WHERE lower(label) LIKE ? OR lower(address) LIKE ?
                """,
                (f"%{query_clean}%", f"%{query_clean}%"),
            )
            if finint_rows:
                dossier["metrics"]["finint_exposure"] = True
                for fw in finint_rows:
                    dossier["associated_entities"].append({
                        "name": f"Wallet {fw[1].upper()}: {fw[0][:10]}...",
                        "type": "FINANCIAL_ADDRESS",
                        "ofac_flag": bool(fw[2]),
                    })
    except Exception:
        pass

    # 8. Extraer Entidades Asociadas desde el Grafo / Menciones
    sources_set = set(e["source"] for e in unique_entries if e.get("source"))
    dossier["recent_sources"] = list(sources_set)[:8]

    # Detectar tags de país más comunes
    country_tag_counts: Dict[str, int] = {}
    for e in unique_entries:
        c_str = str(e.get("country_tags", ""))
        for tag in ["COL", "VEN", "GLOBAL"]:
            if tag in c_str:
                country_tag_counts[tag] = country_tag_counts.get(tag, 0) + 1

    dossier["profile"]["country_tags"] = [
        k for k, _ in sorted(country_tag_counts.items(), key=lambda x: x[1], reverse=True)
    ] or ["GLOBAL"]

    # 9. Cálculo de Risk Score & Level
    score = 0.0
    if dossier["profile"]["ofac_flag"]:
        score += 4.0
    if dossier["metrics"]["finint_exposure"]:
        score += 2.0
    score += min(len(unique_entries) * 0.2, 2.5)
    score += min(dossier["metrics"]["humint_reports_count"] * 0.5, 1.5)

    dossier["profile"]["risk_score"] = round(min(score, 10.0), 1)

    if score >= 7.0:
        dossier["profile"]["risk_level"] = "CRÍTICO"
    elif score >= 4.5:
        dossier["profile"]["risk_level"] = "ALERTA"
    elif score >= 2.0:
        dossier["profile"]["risk_level"] = "ELEVADO"
    else:
        dossier["profile"]["risk_level"] = "ESTABLE"

    return dossier


def get_preloaded_tactical_targets() -> List[Dict[str, Any]]:
    """
    Retorna una lista de objetivos e instituciones prioritarias precargadas
    desde la configuración de teatros regionales (Colombia, Venezuela, Global).
    """
    targets = []
    try:
        import theaters_config
        active = theaters_config.get_active_theaters()
        for code, data in active.items():
            users = data.get("target_users", [])
            for u in users:
                targets.append({
                    "name": u,
                    "theater": code,
                    "type": "PERSON",
                })
            insts = data.get("institutions", ["Presidencia", "Ministerio de Defensa", "Fiscalía General"])
            for inst in insts:
                targets.append({
                    "name": inst,
                    "theater": code,
                    "type": "INSTITUTION",
                })
    except Exception as e:
        logger.warning(f"[DOSSIER] Error cargando objetivos de teatros: {e}")
        # Fallback básico
        targets = [
            {"name": "Abelardo de la Espriella", "theater": "COL", "type": "PERSON"},
            {"name": "Gustavo Petro", "theater": "COL", "type": "PERSON"},
            {"name": "Iván Cepeda", "theater": "COL", "type": "PERSON"},
            {"name": "Ministerio de Defensa Colombia", "theater": "COL", "type": "INSTITUTION"},
            {"name": "Fiscalía General de la Nación", "theater": "COL", "type": "INSTITUTION"},
            {"name": "Presidencia de la República", "theater": "COL", "type": "INSTITUTION"},
        ]
    return targets
