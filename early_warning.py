"""
early_warning.py — Rules engine for predictive early warning system.
Monitors threat scores, applies escalation rules, and emits early_warning events.
"""
import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Threshold configuration
THREAT_HIGH = 75.0
THREAT_MEDIUM = 50.0
THREAT_LOW = 25.0

# Dedup window in seconds
DEDUP_WINDOW = 3600


class EarlyWarningEngine:
    """Evaluates threat scores against rules and generates structured warnings."""

    def __init__(self):
        self._lock = threading.RLock()
        self._active_warnings: Dict[str, Dict] = {}
        self._suppressed: Set[str] = set()
        self._alert_history: List[Dict] = []
        self._history_max = 200

    def evaluate(self, scores: List[Dict], context: Optional[Dict] = None) -> List[Dict]:
        """Evaluate a batch of entity threat scores and return new warnings."""
        now = datetime.now().isoformat()
        new_warnings = []

        for sc in scores:
            sid = sc.get("entity_id", "")
            score = sc.get("threat_score", 0)

            # Skip suppressed entities
            if sid in self._suppressed:
                continue

            # Dedup: skip if same entity warned recently
            if sid in self._active_warnings:
                existing = self._active_warnings[sid]
                if (datetime.fromisoformat(now) - datetime.fromisoformat(existing["created_at"])).total_seconds() < DEDUP_WINDOW:
                    continue

            level = self._classify(score)
            if level is None:
                continue

            rules_triggered = self._match_rules(sc, context)
            warning = {
                "id": f"ew-{sid}-{int(datetime.now().timestamp())}",
                "entity_id": sid,
                "entity_name": sc.get("entity_name", "Unknown"),
                "entity_type": sc.get("entity_type", "unknown"),
                "threat_score": score,
                "level": level,
                "rules_triggered": rules_triggered,
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "resolved_at": "",
            }

            with self._lock:
                self._active_warnings[sid] = warning
                self._alert_history.append(warning)
                if len(self._alert_history) > self._history_max:
                    self._alert_history = self._alert_history[-self._history_max // 2 :]

            new_warnings.append(warning)
            logger.info(f"[EARLY WARNING] {level.upper()}: {sc.get('entity_name', '?')} (score={score})")

        return new_warnings

    def resolve(self, entity_id: str) -> bool:
        """Mark a warning as resolved."""
        with self._lock:
            if entity_id in self._active_warnings:
                self._active_warnings[entity_id]["status"] = "resolved"
                self._active_warnings[entity_id]["resolved_at"] = datetime.now().isoformat()
                return True
        return False

    def suppress(self, entity_id: str):
        """Suppress future warnings for this entity."""
        with self._lock:
            self._suppressed.add(entity_id)
            if entity_id in self._active_warnings:
                del self._active_warnings[entity_id]

    def get_active(self) -> List[Dict]:
        with self._lock:
            return [w for w in self._active_warnings.values() if w["status"] == "active"]

    def get_history(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return list(self._alert_history)[-limit:]

    def get_stats(self) -> Dict:
        with self._lock:
            active = [w for w in self._active_warnings.values() if w["status"] == "active"]
            by_level = defaultdict(int)
            for w in self._alert_history:
                by_level[w["level"]] += 1
            return {
                "active_count": len(active),
                "total_generated": len(self._alert_history),
                "by_level": dict(by_level),
                "by_type": self._count_by_type(active),
            }

    def _classify(self, score: float) -> Optional[str]:
        if score >= THREAT_HIGH:
            return "critical"
        if score >= THREAT_MEDIUM:
            return "high"
        if score >= THREAT_LOW:
            return "medium"
        return None

    def _match_rules(self, score_data: Dict, context: Optional[Dict] = None) -> List[str]:
        rules = []
        score = score_data.get("threat_score", 0)
        etype = score_data.get("entity_type", "")
        ofac = score_data.get("ofac_match", False)

        if score >= THREAT_HIGH and ofac:
            rules.append("ofac_high_threat")
        if score >= THREAT_HIGH and etype in ("infrastructure:domain", "infrastructure:ip"):
            rules.append("infrastructure_critical")
        if score >= THREAT_MEDIUM and ofac:
            rules.append("ofac_elevated")
        if score >= THREAT_MEDIUM and etype.startswith("infrastructure"):
            rules.append("infrastructure_elevated")
        if score >= THREAT_MEDIUM and etype == "person":
            rules.append("person_elevated")
        if score >= THREAT_LOW and etype == "organization":
            rules.append("organization_monitor")

        # Composite event proximity
        if context and score_data.get("signals", {}).get("composite", 0) > 50:
            rules.append("composite_event_proximity")

        # Agent findings
        if context and score_data.get("signals", {}).get("agent", 0) > 60:
            rules.append("agent_corroboration")

        # Recent activity
        signals = score_data.get("signals", {})
        if signals.get("recency", 0) > 80 and signals.get("severity", 0) > 60:
            rules.append("recent_high_severity_activity")

        return rules

    def _count_by_type(self, warnings: List[Dict]) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for w in warnings:
            counts[w.get("entity_type", "unknown")] += 1
        return dict(counts)


# Global singleton
early_warning = EarlyWarningEngine()
