"""Tests for predictive_scorer and early_warning modules."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_predictive_scorer_imports():
    from predictive_scorer import compute_entity_threat, compute_region_threat
    assert callable(compute_entity_threat)
    assert callable(compute_region_threat)


def test_early_warning_imports():
    from early_warning import EarlyWarningEngine
    assert callable(EarlyWarningEngine)


def test_entity_threat_scoring():
    from predictive_scorer import compute_entity_threat
    from datetime import datetime

    entity = {
        "id": "test_ent_001",
        "canonical_name": "Test Entity",
        "entity_type": "person",
        "source": "social",
        "ofac_match": True,
        "aliases": '["alias1", "alias2"]',
        "properties": "{}",
        "last_seen": datetime.now().isoformat(),
    }
    agent_findings = []
    composite_events = []
    all_entries = [
        {"title": "Test Entity involved in incident", "summary": "Critical alert", "category": "alert", "severity": "critical"}
    ]

    result = compute_entity_threat(entity, agent_findings, composite_events, all_entries, datetime.now())
    assert "entity_id" in result
    assert "threat_score" in result
    assert 0 <= result["threat_score"] <= 100
    assert result["entity_name"] == "Test Entity"
    assert result["ofac_match"] is True
    assert "signals" in result


def test_entity_threat_score_bounds():
    from predictive_scorer import compute_entity_threat
    from datetime import datetime

    # Minimum score entity
    entity = {
        "id": "min",
        "canonical_name": "Minimal",
        "entity_type": "unknown",
        "ofac_match": False,
        "aliases": "[]",
        "properties": "{}",
        "last_seen": "2020-01-01T00:00:00",
    }
    result = compute_entity_threat(entity, [], [], [], datetime.now())
    assert result["threat_score"] >= 0
    assert result["threat_score"] <= 100


def test_early_warning_classify():
    from early_warning import EarlyWarningEngine
    ew = EarlyWarningEngine()
    assert ew._classify(80) == "critical"
    assert ew._classify(60) == "high"
    assert ew._classify(30) == "medium"
    assert ew._classify(10) is None


def test_early_warning_evaluate():
    from early_warning import EarlyWarningEngine
    ew = EarlyWarningEngine()

    scores = [
        {"entity_id": "e1", "entity_name": "OFAC Person", "entity_type": "person", "threat_score": 85, "ofac_match": True, "signals": {"composite": 0, "agent": 0, "exposure": 0, "recency": 0, "severity": 0}},
        {"entity_id": "e2", "entity_name": "Normal Entity", "entity_type": "organization", "threat_score": 20, "ofac_match": False, "signals": {"composite": 0, "agent": 0, "exposure": 0, "recency": 0, "severity": 0}},
    ]

    warnings = ew.evaluate(scores)
    assert len(warnings) == 1
    assert warnings[0]["entity_id"] == "e1"
    assert warnings[0]["level"] == "critical"
    assert "ofac_high_threat" in warnings[0]["rules_triggered"]

    # Dedup: same entity should not generate another warning
    warnings2 = ew.evaluate(scores)
    assert len(warnings2) == 0


def test_early_warning_resolve_and_suppress():
    from early_warning import EarlyWarningEngine
    ew = EarlyWarningEngine()

    scores = [{"entity_id": "e3", "entity_name": "Test", "entity_type": "person", "threat_score": 80, "ofac_match": True, "signals": {"composite": 0, "agent": 0, "exposure": 0, "recency": 0, "severity": 0}}]
    ew.evaluate(scores)

    assert len(ew.get_active()) == 1
    ew.resolve("e3")
    assert len(ew.get_active()) == 0

    ew.evaluate(scores)  # Should not re-add (DEDUP_WINDOW)
    assert len(ew.get_active()) == 0


def test_early_warning_stats():
    from early_warning import EarlyWarningEngine
    ew = EarlyWarningEngine()

    scores = [
        {"entity_id": "s1", "entity_name": "A", "entity_type": "person", "threat_score": 85, "ofac_match": True, "signals": {"composite": 0, "agent": 0, "exposure": 0, "recency": 0, "severity": 0}},
        {"entity_id": "s2", "entity_name": "B", "entity_type": "organization", "threat_score": 60, "ofac_match": False, "signals": {"composite": 0, "agent": 0, "exposure": 0, "recency": 0, "severity": 0}},
    ]
    ew.evaluate(scores)
    stats = ew.get_stats()
    assert stats["active_count"] == 2
    assert stats["by_level"]["critical"] == 1
    assert stats["by_level"]["high"] == 1
    assert stats["by_type"]["person"] == 1
    assert stats["by_type"]["organization"] == 1


def test_region_threat_scoring():
    from predictive_scorer import compute_region_threat
    result = compute_region_threat(10.0, -70.0, [], [])
    assert "threat_score" in result
    assert "centroid_lat" in result
    assert result["centroid_lat"] == 10.0
