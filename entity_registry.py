"""
entity_registry.py — Canonical entity registry with SQLite persistence.
Stores resolved entities from OFAC, Wikidata, and social graph sources.
"""
import json
import logging
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "entity_registry.db"
db_lock = threading.RLock()


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    with db_lock:
        with _get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL,
                    aliases TEXT DEFAULT '[]',
                    entity_type TEXT NOT NULL DEFAULT 'unknown',
                    source TEXT NOT NULL DEFAULT 'manual',
                    source_id TEXT DEFAULT '',
                    properties TEXT DEFAULT '{}',
                    ofac_match INTEGER DEFAULT 0,
                    ofac_ids TEXT DEFAULT '[]',
                    wikidata_qid TEXT DEFAULT '',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    snapshot_ids TEXT DEFAULT '[]',
                    graph_node_id TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_ofac ON entities(ofac_match)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name)")


def _entity_id(canonical_name: str, source: str) -> str:
    import hashlib
    raw = f"{source}::{canonical_name.lower().strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]


def register(
    canonical_name: str,
    entity_type: str = "unknown",
    source: str = "manual",
    source_id: str = "",
    aliases: Optional[List[str]] = None,
    properties: Optional[Dict] = None,
    ofac_match: bool = False,
    ofac_ids: Optional[List[str]] = None,
    wikidata_qid: str = "",
    snapshot_id: Optional[int] = None,
    graph_node_id: str = "",
) -> str:
    """Register or update an entity in the registry. Returns entity ID."""
    _init()
    eid = _entity_id(canonical_name, source)
    now = datetime.now().isoformat()
    aliases_json = json.dumps(aliases or [], ensure_ascii=False)
    props_json = json.dumps(properties or {}, ensure_ascii=False)
    ofac_ids_json = json.dumps(ofac_ids or [], ensure_ascii=False)
    snap_ids = []

    with db_lock:
        with _get_conn() as conn:
            existing = conn.execute("SELECT * FROM entities WHERE id = ?", (eid,)).fetchone()
            if existing:
                # Merge aliases
                existing_aliases = set(json.loads(existing["aliases"]))
                new_aliases = set(aliases or [])
                merged_aliases = list(existing_aliases | new_aliases)

                # Merge snapshot_ids
                existing_snaps = set(json.loads(existing["snapshot_ids"]))
                if snapshot_id is not None:
                    existing_snaps.add(str(snapshot_id))
                snap_ids = list(existing_snaps)

                # Merge properties
                existing_props = json.loads(existing["properties"])
                if properties:
                    existing_props.update(properties)

                # Merge ofac_ids
                existing_ofac = set(json.loads(existing["ofac_ids"]))
                if ofac_ids:
                    existing_ofac.update(ofac_ids)

                conn.execute(
                    """UPDATE entities SET
                        canonical_name = ?, aliases = ?, entity_type = ?,
                        source = ?, source_id = ?, properties = ?,
                        ofac_match = ?, ofac_ids = ?, wikidata_qid = ?,
                        last_seen = ?, snapshot_ids = ?, graph_node_id = ?
                    WHERE id = ?""",
                    (
                        canonical_name, json.dumps(merged_aliases), entity_type,
                        source, source_id, props_json,
                        int(ofac_match or existing["ofac_match"]),
                        json.dumps(list(existing_ofac)),
                        wikidata_qid or existing["wikidata_qid"],
                        now, json.dumps(snap_ids),
                        graph_node_id or existing["graph_node_id"],
                        eid,
                    ),
                )
            else:
                snap_ids = [str(snapshot_id)] if snapshot_id is not None else []
                conn.execute(
                    """INSERT INTO entities
                    (id, canonical_name, aliases, entity_type, source, source_id,
                     properties, ofac_match, ofac_ids, wikidata_qid,
                     first_seen, last_seen, snapshot_ids, graph_node_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        eid, canonical_name, aliases_json, entity_type, source, source_id,
                        props_json, int(ofac_match), ofac_ids_json, wikidata_qid,
                        now, now, json.dumps(snap_ids), graph_node_id,
                    ),
                )

    return eid


def search(query: str, entity_type: Optional[str] = None, source: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Search entities by canonical name or aliases."""
    _init()
    results = []
    with db_lock:
        with _get_conn() as conn:
            sql = "SELECT * FROM entities WHERE (canonical_name LIKE ? OR aliases LIKE ?)"
            params = [f"%{query}%", f"%{query}%"]
            if entity_type:
                sql += " AND entity_type = ?"
                params.append(entity_type)
            if source:
                sql += " AND source = ?"
                params.append(source)
            sql += " ORDER BY last_seen DESC LIMIT ?"
            params.append(limit)
            for row in conn.execute(sql, params).fetchall():
                results.append(_row_to_dict(row))
    return results


def list_all(limit: int = 100) -> List[Dict]:
    """List all entities ordered by last_seen."""
    _init()
    results = []
    with db_lock:
        with _get_conn() as conn:
            for row in conn.execute(
                "SELECT * FROM entities ORDER BY last_seen DESC LIMIT ?", (limit,)
            ).fetchall():
                results.append(_row_to_dict(row))
    return results


def get_by_id(entity_id: str) -> Optional[Dict]:
    """Get a single entity by its ID."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            return _row_to_dict(row) if row else None


def get_by_graph_node(node_id: str) -> Optional[Dict]:
    """Get entity by graph_node_id."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM entities WHERE graph_node_id = ?", (node_id,)).fetchone()
            return _row_to_dict(row) if row else None


def get_ofac_matched(limit: int = 100) -> List[Dict]:
    """Get all entities that have OFAC matches."""
    _init()
    results = []
    with db_lock:
        with _get_conn() as conn:
            for row in conn.execute(
                "SELECT * FROM entities WHERE ofac_match = 1 ORDER BY last_seen DESC LIMIT ?", (limit,)
            ).fetchall():
                results.append(_row_to_dict(row))
    return results


def get_stats() -> Dict:
    """Registry statistics."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM entities").fetchone()["cnt"]
            by_type = {}
            for row in conn.execute("SELECT entity_type, COUNT(*) as cnt FROM entities GROUP BY entity_type"):
                by_type[row["entity_type"]] = row["cnt"]
            ofac_count = conn.execute("SELECT COUNT(*) as cnt FROM entities WHERE ofac_match = 1").fetchone()["cnt"]
            wikidata_count = conn.execute("SELECT COUNT(*) as cnt FROM entities WHERE wikidata_qid != ''").fetchone()["cnt"]
            return {
                "total_entities": total,
                "by_type": by_type,
                "ofac_matches": ofac_count,
                "wikidata_linked": wikidata_count,
                "db_path": str(DB_PATH),
            }


def link_to_snapshot(entity_id: str, snapshot_id: int):
    """Associate an entity with a graph snapshot ID."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            existing = conn.execute("SELECT snapshot_ids FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if existing:
                snaps = set(json.loads(existing["snapshot_ids"]))
                snaps.add(str(snapshot_id))
                conn.execute(
                    "UPDATE entities SET snapshot_ids = ?, last_seen = ? WHERE id = ?",
                    (json.dumps(list(snaps)), datetime.now().isoformat(), entity_id),
                )


def _row_to_dict(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "canonical_name": row["canonical_name"],
        "aliases": json.loads(row["aliases"]),
        "entity_type": row["entity_type"],
        "source": row["source"],
        "source_id": row["source_id"],
        "properties": json.loads(row["properties"]),
        "ofac_match": bool(row["ofac_match"]),
        "ofac_ids": json.loads(row["ofac_ids"]),
        "wikidata_qid": row["wikidata_qid"],
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "snapshot_ids": json.loads(row["snapshot_ids"]),
        "graph_node_id": row["graph_node_id"],
    }


# ── Tactical Regional Entity Extraction ───────────────────────────────────────
TACTICAL_PATTERNS = {
    "cedula": r'\b[VEJGPvejgp]-?\d{5,9}\b',
    "rif": r'\b[JGPCEVjgpcev]-\d{7,9}-\d\b',
    "telefono_ve": r'\b(?:0(?:412|414|416|424|426|212|241|243|251|261|271|281|285|286|288|291|293|295)[\s\-]?\d{7})\b',
    "monto_bs": r'(?:Bs\.?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\b\d{1,7}(?:[.,]\d{3})*(?:[.,]\d{2})?\s*Bs\.?)',
    "monto_usd": r'(?:\$\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\b\d{1,7}(?:[.,]\d{3})*(?:[.,]\d{2})?\s*(?:USD|\$))',
    "placa_ve": r'\b[A-Z]{2,3}\d{1,3}[A-Z]{0,2}\b',
}


def extract_tactical_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract tactical regional OSINT entities (Cédulas, RIF, Telefonía VE, Montos, Placas)
    using zero-overhead microsecond regex patterns.
    """
    extracted = {}
    if not text:
        return extracted

    for label, pattern in TACTICAL_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Deduplicate preserving order
            seen = set()
            unique_matches = [m for m in matches if not (m in seen or seen.add(m))]
            extracted[label] = unique_matches

    return extracted

