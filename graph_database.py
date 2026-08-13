# graph_database.py - Persistencia SQLite para grafos históricos
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import osint_neo4j

DB_PATH = Path(__file__).parent / "social_graph_cache.db"
db_lock = threading.RLock()


def _get_connection():
    """Retorna una conexión configurada para concurrencia y velocidad con WAL, claves foráneas y timeout ampliado."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    # Habilitar claves foráneas (desactivadas por defecto en SQLite)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Habilitar modo WAL (Write-Ahead Logging) para permitir lecturas y escrituras concurrentes sin bloqueos.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _init_db():
    """Inicializa la base de datos si no existe."""
    with db_lock:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS graph_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    graph_data TEXT NOT NULL,
                    node_count INTEGER,
                    edge_count INTEGER,
                    extraction_method TEXT,
                    metrics_summary TEXT,
                    entity_ids TEXT DEFAULT '[]'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    degree_centrality REAL,
                    betweenness_centrality REAL,
                    pagerank REAL,
                    snapshot_id INTEGER,
                    FOREIGN KEY (snapshot_id) REFERENCES graph_snapshots (id) ON DELETE CASCADE
                )
            """)
            # Migración: agregar entity_ids si no existe (bases existentes)
            try:
                cursor.execute("ALTER TABLE graph_snapshots ADD COLUMN entity_ids TEXT DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass  # ya existe

            conn.commit()


def save_graph_snapshot(graph_data: Dict, extraction_method: str = "regex", entity_ids: Optional[List[str]] = None) -> int:
    """Guarda un snapshot del grafo en la base de datos de manera thread-safe."""
    with db_lock:
        _init_db()
        timestamp = datetime.now().isoformat()
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        metrics = graph_data.get("metrics", {})

        with _get_connection() as conn:
            cursor = conn.cursor()
            entity_ids_json = json.dumps(entity_ids or [])
            cursor.execute(
                """
                INSERT INTO graph_snapshots
                (timestamp, graph_data, node_count, edge_count, extraction_method, metrics_summary, entity_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (timestamp, json.dumps(graph_data), len(nodes), len(edges), extraction_method, json.dumps(metrics), entity_ids_json),
            )
            snapshot_id = cursor.lastrowid

            history_data = []
            for node in nodes:
                node_id = node.get("id")
                if node_id and node_id in metrics:
                    nm = metrics[node_id]
                    history_data.append(
                        (
                            node_id,
                            timestamp,
                            nm.get("degree_centrality", 0.0),
                            nm.get("betweenness_centrality", 0.0),
                            nm.get("pagerank", 0.0),
                            snapshot_id,
                        )
                    )

            if history_data:
                cursor.executemany(
                    """
                    INSERT INTO node_history
                    (node_id, timestamp, degree_centrality, betweenness_centrality, pagerank, snapshot_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    history_data,
                )
            conn.commit()

        _cleanup_old_snapshots()

        # Fase 4: Proyección dual asíncrona hacia Neo4j
        try:
            threading.Thread(target=osint_neo4j.sync_graph, args=(graph_data, extraction_method), daemon=True).start()
        except Exception:
            pass

        return snapshot_id


def get_recent_snapshots(hours: int = 24) -> List[Dict]:
    """Obtiene snapshots de las últimas N horas."""
    _init_db()
    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, graph_data, node_count, edge_count, extraction_method, metrics_summary, entity_ids
            FROM graph_snapshots WHERE timestamp >= ? ORDER BY timestamp DESC
        """,
            (cutoff_time,),
        )
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "graph_data": json.loads(r[2]),
                "node_count": r[3],
                "edge_count": r[4],
                "extraction_method": r[5],
                "metrics_summary": json.loads(r[6]),
                "entity_ids": json.loads(r[7]) if r[7] else [],
            }
            for r in cursor.fetchall()
        ]


def get_node_history(node_id: str, hours: int = 168) -> List[Dict]:
    """Obtiene el historial de métricas de un nodo específico."""
    _init_db()
    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, degree_centrality, betweenness_centrality, pagerank
            FROM node_history WHERE node_id = ? AND timestamp >= ? ORDER BY timestamp ASC
        """,
            (node_id, cutoff_time),
        )
        return [
            {"timestamp": r[0], "degree_centrality": r[1], "betweenness_centrality": r[2], "pagerank": r[3]}
            for r in cursor.fetchall()
        ]


def compare_snapshots(snapshot_id_1: int, snapshot_id_2: int) -> Dict[str, Any]:
    """Compara dos snapshots para detectar cambios significativos."""
    _init_db()

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT graph_data, node_count, edge_count, timestamp FROM graph_snapshots WHERE id = ?", (snapshot_id_1,)
        )
        row1 = cursor.fetchone()
        cursor.execute(
            "SELECT graph_data, node_count, edge_count, timestamp FROM graph_snapshots WHERE id = ?", (snapshot_id_2,)
        )
        row2 = cursor.fetchone()

    if not row1 or not row2:
        return {"error": "Uno o ambos snapshots no encontrados"}

    graph1, graph2 = json.loads(row1[0]), json.loads(row2[0])
    nodes1, nodes2 = {n["id"] for n in graph1.get("nodes", [])}, {n["id"] for n in graph2.get("nodes", [])}
    edges1 = {(e["from"], e["to"]) for e in graph1.get("edges", [])}
    edges2 = {(e["from"], e["to"]) for e in graph2.get("edges", [])}

    return {
        "snapshot_1": {"id": snapshot_id_1, "timestamp": row1[3], "nodes": row1[1], "edges": row1[2]},
        "snapshot_2": {"id": snapshot_id_2, "timestamp": row2[3], "nodes": row2[1], "edges": row2[2]},
        "changes": {
            "new_nodes": list(nodes2 - nodes1),
            "lost_nodes": list(nodes1 - nodes2),
            "new_edges": list(edges2 - edges1),
            "lost_edges": list(edges1 - edges2),
            "node_delta": len(nodes2) - len(nodes1),
            "edge_delta": len(edges2) - len(edges1),
        },
    }


def _cleanup_old_snapshots(days: int = 90):
    """Elimina snapshots más antiguos que N días de manera thread-safe (aprovecha CASCADE con fallback manual)."""
    with db_lock:
        cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
        with _get_connection() as conn:
            cursor = conn.cursor()
            # En bases de datos existentes sin CASCADE de esquema antiguo, borramos manualmente primero por seguridad
            cursor.execute("DELETE FROM node_history WHERE timestamp < ?", (cutoff_time,))
            cursor.execute("DELETE FROM graph_snapshots WHERE timestamp < ?", (cutoff_time,))
            conn.commit()


def get_latest_snapshot() -> Optional[Dict]:
    """Obtiene el snapshot más reciente."""
    _init_db()
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, graph_data, node_count, edge_count, extraction_method, metrics_summary, entity_ids
            FROM graph_snapshots ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "timestamp": row[1],
                "graph_data": json.loads(row[2]),
                "node_count": row[3],
                "edge_count": row[4],
                "extraction_method": row[5],
                "metrics_summary": json.loads(row[6]),
                "entity_ids": json.loads(row[7]) if row[7] else [],
            }
    return None
