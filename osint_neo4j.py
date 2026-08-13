"""
COBALTO HUB — Neo4j Integration
Proyección de grafos sociales (botnets, vínculos, influencia) hacia Neo4j.
Permite consultas nativas con Cypher para atribución compleja.
Fallback silencioso si Neo4j no está configurado o activo.
"""
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

_DRIVER = None

if NEO4J_URI:
    try:
        from neo4j import GraphDatabase
        _DRIVER = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        _DRIVER.verify_connectivity()
        logger.info("[NEO4J] Conectado exitosamente al motor de grafos.")

        # Configurar restricciones de unicidad
        with _DRIVER.session() as session:
            try:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")
            except Exception as e:
                logger.debug(f"[NEO4J] Error creando constraint (puede existir en versiones antiguas): {e}")

    except Exception as e:
        logger.error(f"[NEO4J] Error conectando o configurando: {e}")
        _DRIVER = None


def sync_graph(graph_data: dict, extraction_method: str = "regex"):
    """
    Proyecta nodos y relaciones (aristas) a Neo4j usando comandos Cypher MERGE.
    Si el motor no está activo, se salta la ejecución (Fallback).
    """
    if not _DRIVER or not graph_data:
        return

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    metrics = graph_data.get("metrics", {})

    if not nodes and not edges:
        return

    try:
        with _DRIVER.session() as session:
            now_ts = datetime.now(timezone.utc).isoformat()

            # 1. Sincronizar Nodos
            for node in nodes:
                node_id = str(node.get("id"))
                label = str(node.get("label", node_id))
                group = str(node.get("group", "Unknown"))

                # Métricas de centralidad
                nm = metrics.get(node_id, {})
                degree = float(nm.get("degree_centrality", 0.0))
                betweenness = float(nm.get("betweenness_centrality", 0.0))
                pagerank = float(nm.get("pagerank", 0.0))

                query = """
                MERGE (n:Entity {id: $node_id})
                SET n.label = $label,
                    n.group = $group,
                    n.degree = $degree,
                    n.betweenness = $betweenness,
                    n.pagerank = $pagerank,
                    n.last_seen = $now
                """
                session.run(query, node_id=node_id, label=label, group=group,
                            degree=degree, betweenness=betweenness, pagerank=pagerank, now=now_ts)

            # 2. Sincronizar Relaciones (Aristas)
            for edge in edges:
                source = str(edge.get("from"))
                target = str(edge.get("to"))
                rel_title = str(edge.get("title", "RELATES_TO"))
                weight = float(edge.get("value", 1.0))

                # Determinar semántica de la relación
                rel_type = "RELATES_TO"
                if "retweet" in rel_title.lower() or "rt" in rel_title.lower():
                    rel_type = "RETWEETED"
                elif "mención" in rel_title.lower() or "mention" in rel_title.lower():
                    rel_type = "MENTIONED"
                elif "hashtag" in rel_title.lower():
                    rel_type = "USED_HASHTAG"

                query = f"""
                MATCH (a:Entity {{id: $source}})
                MATCH (b:Entity {{id: $target}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.weight = $weight, r.last_seen = $now
                """
                session.run(query, source=source, target=target, weight=weight, now=now_ts)

        logger.info(f"[NEO4J] Sincronización completa: {len(nodes)} nodos, {len(edges)} aristas proyectados.")
    except Exception as e:
        logger.error(f"[NEO4J] Error sincronizando grafo: {e}")

def get_graph_data(limit: int = 500) -> dict:
    """Extrae el grafo actual para visualización en UI usando Force-Graph."""
    if not _DRIVER:
        return {"nodes": [], "edges": []}

    try:
        with _DRIVER.session() as session:
            # Consultamos los nodos y sus relaciones
            query = """
            MATCH (n:Entity)-[r]->(m:Entity)
            RETURN n.id as source, n.label as source_label, n.group as source_group, n.degree as source_degree,
                   type(r) as rel_type, r.weight as weight,
                   m.id as target, m.label as target_label, m.group as target_group, m.degree as target_degree
            LIMIT $limit
            """
            result = session.run(query, limit=limit)

            nodes = {}
            edges = []

            for record in result:
                s_id = record["source"]
                t_id = record["target"]

                if s_id not in nodes:
                    nodes[s_id] = {
                        "id": s_id,
                        "name": record["source_label"],
                        "group": record["source_group"],
                        "val": record["source_degree"] or 1
                    }
                if t_id not in nodes:
                    nodes[t_id] = {
                        "id": t_id,
                        "name": record["target_label"],
                        "group": record["target_group"],
                        "val": record["target_degree"] or 1
                    }

                edges.append({
                    "source": s_id,
                    "target": t_id,
                    "type": record["rel_type"],
                    "weight": record["weight"] or 1
                })

            # Retornamos en el formato que Force-Graph y 3d-Force-Graph esperan
            return {
                "nodes": list(nodes.values()),
                "links": edges
            }
    except Exception as e:
        logger.error(f"[NEO4J] Error extrayendo datos para visualización: {e}")
        return {"nodes": [], "links": []}
