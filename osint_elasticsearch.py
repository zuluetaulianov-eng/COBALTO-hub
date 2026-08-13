"""
COBALTO HUB — Elasticsearch Integration
Indexación de documentos OSINT para búsqueda Full-Text rápida y faceteo.
Con soporte de fallback transparente (No-op si ES no está disponible).
"""
import hashlib
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")
_ES_CLIENT = None

if ELASTICSEARCH_URL:
    try:
        from elasticsearch import Elasticsearch
        _ES_CLIENT = Elasticsearch(ELASTICSEARCH_URL)
        # Verify connection and create index if not exists
        if _ES_CLIENT.ping():
            if not _ES_CLIENT.indices.exists(index="cobalto-osint-feed"):
                _ES_CLIENT.indices.create(
                    index="cobalto-osint-feed",
                    mappings={
                        "properties": {
                            "hash": {"type": "keyword"},
                            "source": {"type": "keyword"},
                            "title": {"type": "text"},
                            "summary": {"type": "text"},
                            "link": {"type": "keyword"},
                            "published_raw": {"type": "keyword"},
                            "ingested_at": {"type": "date"}
                        }
                    }
                )
                logger.info("[ELASTICSEARCH] Índice 'cobalto-osint-feed' creado.")
            else:
                logger.info("[ELASTICSEARCH] Conexión establecida y lista.")
        else:
            logger.warning("[ELASTICSEARCH] Servidor configurado pero inalcanzable. Ping fallido.")
            _ES_CLIENT = None
    except Exception as e:
        logger.error(f"[ELASTICSEARCH] Error de conexión o configuración: {e}")
        _ES_CLIENT = None


def hash_entry(entry: dict) -> str:
    key = f"{entry.get('link','')}{entry.get('title','')}{entry.get('published','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def index_entries(entries: list[dict]):
    """Envía las entradas recolectadas al índice de Elasticsearch. Si ES no está configurado, ignora."""
    if not _ES_CLIENT or not entries:
        return

    try:
        from elasticsearch import helpers
        actions = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for entry in entries:
            doc_id = hash_entry(entry)

            source_doc = {
                "hash": doc_id,
                "source": entry.get("source", "Unknown"),
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "published_raw": entry.get("published", ""),
                "ingested_at": now_ts
            }

            actions.append({
                "_index": "cobalto-osint-feed",
                "_id": doc_id,
                "_op_type": "index",
                "_source": source_doc
            })

        success, _ = helpers.bulk(_ES_CLIENT, actions, raise_on_error=False)
        logger.info(f"[ELASTICSEARCH] {success} documentos indexados exitosamente de un lote de {len(entries)}.")
    except Exception as e:
        logger.error(f"[ELASTICSEARCH] Error en bulk index: {e}")

def search_entries(query: str, limit: int = 50) -> list[dict]:
    """Busca en Elasticsearch usando query_string."""
    if not _ES_CLIENT or not query:
        return []

    try:
        response = _ES_CLIENT.search(
            index="cobalto-osint-feed",
            body={
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3", "summary^2", "source"],
                        "fuzziness": "AUTO"
                    }
                },
                "size": limit,
                "sort": [
                    {"ingested_at": {"order": "desc"}}
                ]
            }
        )
        hits = response.get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            source = hit.get("_source", {})
            source["_score"] = hit.get("_score", 0)
            results.append(source)

        return results
    except Exception as e:
        logger.error(f"[ELASTICSEARCH] Error en búsqueda: {e}")
        return []
