"""
predictive_scorer.py — Probabilistic threat scoring engine.
Aggregates signals from knowledge graph, correlation engine, agent findings,
and historical patterns to compute threat scores (0-100) per entity and region.
"""
import json
import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Weights for score computation
W_COMPOSITE = 0.25
W_AGENT_FINDING = 0.20
W_ENTITY_EXPOSURE = 0.15
W_RECENCY = 0.10
W_SEVERITY = 0.30

DECAY_HOURS = 48


def _decay_weight(hours_ago: float) -> float:
    """Exponential decay: 1.0 at t=0, ~0.5 at t=DECAY_HOURS."""
    return math.exp(-hours_ago / DECAY_HOURS)


def compute_entity_threat(
    entity: Dict,
    agent_findings: List[Dict],
    composite_events: List[Dict],
    all_entries: List[Dict],
    now: Optional[datetime] = None,
) -> Dict:
    """Compute a threat score (0-100) for a single entity based on all available signals."""
    if now is None:
        now = datetime.now()

    signals = {"composite": 0.0, "agent": 0.0, "exposure": 0.0, "recency": 0.0, "severity": 0.0}

    # 1. Composite correlation signal
    for ce in composite_events:
        if _entity_in_composite(entity, ce):
            dist = ce.get("distance_km", 0)
            severity_bonus = 20 if ce.get("severity") == "critico" else 10
            signals["composite"] = max(signals["composite"], (100 - min(dist, 300)) * 0.2 + severity_bonus)

    # 2. Agent findings signal
    for af in agent_findings:
        if _entity_in_finding(entity, af):
            fs = af.get("severity_score", 50)
            signals["agent"] = max(signals["agent"], float(fs))

    # 3. Entity exposure (number of sources, aliases, OFAC match)
    ofac_bonus = 30 if entity.get("ofac_match") else 0
    alias_count = len(json.loads(entity.get("aliases", "[]")))
    source_diversity = min(len(_get_sources(entity)), 5) * 5
    signals["exposure"] = min(100, ofac_bonus + alias_count * 2 + source_diversity)

    # 4. Recency (last_seen decay)
    try:
        last_seen = datetime.fromisoformat(entity.get("last_seen", now.isoformat()))
        hours_ago = max(0, (now - last_seen).total_seconds() / 3600)
        signals["recency"] = _decay_weight(hours_ago) * 100
    except Exception:
        signals["recency"] = 20.0

    # 5. Severity from recent entries mentioning this entity
    entity_name = entity.get("canonical_name", "").lower()
    severity_scores = []
    for entry in all_entries:
        text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
        if entity_name in text:
            sev = _parse_severity(entry.get("category", ""), entry.get("severity", ""))
            severity_scores.append(sev)
    if severity_scores:
        signals["severity"] = sum(severity_scores) / len(severity_scores)

    total = (
        signals["composite"] * W_COMPOSITE
        + signals["agent"] * W_AGENT_FINDING
        + signals["exposure"] * W_ENTITY_EXPOSURE
        + signals["recency"] * W_RECENCY
        + signals["severity"] * W_SEVERITY
    )

    score = min(100, max(0, round(total, 1)))

    return {
        "entity_id": entity.get("id", ""),
        "entity_name": entity.get("canonical_name", "Unknown"),
        "entity_type": entity.get("entity_type", "unknown"),
        "threat_score": score,
        "signals": signals,
        "ofac_match": bool(entity.get("ofac_match")),
        "last_seen": entity.get("last_seen", ""),
        "updated_at": now.isoformat(),
    }


def compute_region_threat(
    lat: float,
    lon: float,
    entities: List[Dict],
    composite_events: List[Dict],
    radius_km: float = 300.0,
) -> Dict:
    """Aggregate threat for a geographic region based on proximity."""
    from correlation_engine import haversine_km

    total_score = 0.0
    nearby_entities = 0

    for ent in entities:
        props = _parse_properties(ent.get("properties", {}))
        elat = props.get("latitude") or props.get("lat")
        elon = props.get("longitude") or props.get("lon")
        if elat is None or elon is None:
            continue
        dist = haversine_km(lat, lon, float(elat), float(elon))
        if dist <= radius_km:
            nearby_entities += 1
            total_score += ent.get("_threat_score", 50) * (1 - dist / radius_km * 0.5)

    nearby_events = sum(1 for ce in composite_events if _event_nearby(ce, lat, lon, radius_km))
    composite_bonus = min(nearby_events * 10, 50)

    avg_entity = total_score / max(nearby_entities, 1)
    final_score = min(100, max(0, round(avg_entity * 0.7 + composite_bonus, 1)))

    return {
        "centroid_lat": lat,
        "centroid_lon": lon,
        "threat_score": final_score,
        "nearby_entities": nearby_entities,
        "nearby_composite_events": nearby_events,
        "radius_km": radius_km,
    }


def _entity_in_composite(entity: Dict, composite: Dict) -> bool:
    """Check if an entity is referenced in a composite event."""
    desc = composite.get("description", "").lower()
    name = entity.get("canonical_name", "").lower()
    return name in desc or entity.get("id", "") in [str(s) for s in composite.get("events", [])]


def _entity_in_finding(entity: Dict, finding: Dict) -> bool:
    """Check if an entity is mentioned in an agent finding."""
    text = json.dumps(finding.get("data", {})).lower()
    name = entity.get("canonical_name", "").lower()
    return name in text or entity.get("id", "") in str(finding.get("entity_ids", []))


def _get_sources(entity: Dict) -> List[str]:
    src = entity.get("source", "")
    return [s.strip() for s in src.split(",")] if src else []


def _parse_severity(category: str = "", severity: str = "") -> float:
    cat = (category or "").lower()
    sev = (severity or "").lower()
    if "critical" in cat or "critico" in sev or "alta" in sev:
        return 90.0
    if "urgent" in cat or "alta" in cat:
        return 70.0
    if "warning" in cat or "media" in sev:
        return 50.0
    if "info" in cat or "baja" in sev:
        return 20.0
    return 30.0


def _parse_properties(props) -> Dict:
    if isinstance(props, dict):
        return props
    if isinstance(props, str):
        try:
            return json.loads(props)
        except Exception:
            return {}
    return {}


def _event_nearby(event: Dict, lat: float, lon: float, radius_km: float) -> bool:
    from correlation_engine import haversine_km
    elat = event.get("centroid_lat")
    elon = event.get("centroid_lon")
    if elat is None or elon is None:
        return False
    return haversine_km(lat, lon, float(elat), float(elon)) <= radius_km



