"""
entity_linker.py — Cross-source entity linker.
Runs each Heavy cycle: resolves social graph nodes + OFAC entities + Wikidata
against the canonical entity registry. Merges aliases, updates last_seen.
"""
import logging
from typing import Dict, List, Optional

import entity_registry
import entity_resolver

logger = logging.getLogger(__name__)


def link_social_graph_nodes(
    graph_data: Dict,
    sanctions_index: Dict[str, List[dict]],
    snapshot_id: Optional[int] = None,
    threshold: float = 0.3,
) -> int:
    """
    Process social graph nodes and link them to the entity registry.
    Returns count of linked nodes.
    """
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return 0

    linked = 0
    for node in nodes:
        node_id = node.get("id", "")
        label = node.get("label", "")
        node_type = _infer_type(node)
        if not label:
            continue

        entity_registry.register(
            canonical_name=label,
            entity_type=node_type,
            source="social_graph",
            source_id=node_id,
            properties=_extract_properties(node),
            snapshot_id=snapshot_id,
            graph_node_id=node_id,
        )

        # Fuzzy-resolve against OFAC
        if sanctions_index:
            ofac_hits = entity_resolver.resolve_against_index(
                label, sanctions_index, limit=3, min_score=threshold
            )
            if ofac_hits:
                ofac_ids = [h["id"] for h in ofac_hits]
                best = ofac_hits[0]
                entity_registry.register(
                    canonical_name=label,
                    entity_type=node_type,
                    source="social_graph",
                    source_id=node_id,
                    ofac_match=True,
                    ofac_ids=ofac_ids,
                    properties={"_ofac_match_score": best.get("_match_score"),
                                "_ofac_match_method": best.get("_match_method"),
                                "_ofac_name": best.get("name")},
                    snapshot_id=snapshot_id,
                    graph_node_id=node_id,
                )
                linked += 1

    logger.info(f"[ENTITY LINKER] Linked {linked}/{len(nodes)} nodes to registry")
    return linked


def link_sanctions_entries(
    sanctions_index: Dict[str, List[dict]],
    snapshot_id: Optional[int] = None,
) -> int:
    """Register all OFAC SDN entries as entities in the registry."""
    registered = 0
    for name_key, entries in sanctions_index.items():
        for entry in entries:
            schema = entry.get("schema", "unknown")
            etype = _sanctions_schema_to_type(schema)
            entity_registry.register(
                canonical_name=entry.get("name", name_key),
                entity_type=etype,
                source="ofac_sdn",
                source_id=entry.get("id", ""),
                aliases=entry.get("aliases", "").split(";") if entry.get("aliases") else [],
                properties={
                    "schema": schema,
                    "country": entry.get("country", ""),
                    "program": entry.get("program", ""),
                    "listing_date": entry.get("listing_date", ""),
                },
                ofac_match=True,
                ofac_ids=[entry.get("id", "")],
                snapshot_id=snapshot_id,
            )
            registered += 1
    if registered:
        logger.info(f"[ENTITY LINKER] Registered {registered} sanctions entries")
    return registered


def link_wikidata_entity(
    qid: str,
    label: str,
    entity_type: str = "unknown",
    properties: Optional[Dict] = None,
    snapshot_id: Optional[int] = None,
) -> str:
    """Register a Wikidata entity in the registry."""
    eid = entity_registry.register(
        canonical_name=label,
        entity_type=entity_type,
        source="wikidata",
        source_id=qid,
        wikidata_qid=qid,
        properties=properties or {},
        snapshot_id=snapshot_id,
    )
    return eid


def run_full_link_cycle(
    graph_data: Dict,
    sanctions_index: Dict[str, List[dict]],
    snapshot_id: Optional[int] = None,
) -> Dict:
    """Run the full linking pipeline. Called from Heavy cycle."""
    stats = {"social_linked": 0, "sanctions_registered": 0, "total": 0}

    # 1. Link social graph nodes
    stats["social_linked"] = link_social_graph_nodes(graph_data, sanctions_index, snapshot_id)

    # 2. Register sanctions
    stats["sanctions_registered"] = link_sanctions_entries(sanctions_index, snapshot_id)

    # 3. Aggregate
    reg_stats = entity_registry.get_stats()
    stats["total"] = reg_stats.get("total_entities", 0)

    logger.info(f"[ENTITY LINKER] Full cycle complete: {stats}")
    return stats


def _infer_type(node: Dict) -> str:
    """Infer entity type from graph node group."""
    group = (node.get("group") or "").lower()
    mapping = {
        "persons": "person",
        "person": "person",
        "people": "person",
        "organizations": "organization",
        "organization": "organization",
        "org": "organization",
        "locations": "location",
        "location": "location",
        "place": "location",
        "events": "event",
        "event": "event",
        "infrastructure": "infrastructure",
        "infra": "infrastructure",
        "ip": "infrastructure",
        "domain": "infrastructure",
    }
    return mapping.get(group, "unknown")


def _sanctions_schema_to_type(schema: str) -> str:
    mapping = {
        "Person": "person",
        "LegalEntity": "organization",
        "Vessel": "vessel",
        "Aircraft": "aircraft",
    }
    return mapping.get(schema, "unknown")


def _extract_properties(node: Dict) -> Dict:
    props = {}
    for key in ("sentiment", "pagerank", "degree", "betweenness", "community", "is_botnet"):
        if key in node:
            props[key] = node[key]
    return props
