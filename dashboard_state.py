from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


def _fresh_heavy_track_cache():
    return {
        "onion_and_dorks": {"sources": {}, "count": 0, "timestamp": ""},
        "global_briefing": "<i>⏳ Análisis táctico profundo (IA, Dorks, Onion) en curso...</i>",
        "ai_geopoints": [],
        "reliability_score": 100,
        "reliability_color": "#00ffaa",
        "briefing_history": [],
        "heavy_started_at": datetime.now().isoformat(),
    }


@dataclass
class AppState:
    heavy_track_cache: Dict[str, Any] = field(default_factory=_fresh_heavy_track_cache)
    last_entries_cache: List[Dict[str, Any]] = field(default_factory=list)
    progress_state: Dict[str, Any] = field(default_factory=lambda: {"step": "Inactivo", "details": "", "percentage": 0})
    cycle_id: int = 0
    cycle_start_ts: str = ""

    def clear_cycle(self):
        self.cycle_id += 1
        self.cycle_start_ts = datetime.now().isoformat()
        self.progress_state.update({"step": "Nuevo ciclo", "details": "", "percentage": 0})
        new_cache = _fresh_heavy_track_cache()
        self.heavy_track_cache.clear()
        self.heavy_track_cache.update(new_cache)


state = AppState()
