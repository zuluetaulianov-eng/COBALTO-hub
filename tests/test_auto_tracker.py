import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import auto_tracker


def test_load_and_save_auto_tracked_keywords():
    initial = auto_tracker.load_auto_tracked_keywords()
    assert isinstance(initial, list)
    kw_set = auto_tracker.get_active_auto_keywords_set()
    assert isinstance(kw_set, set)


def test_process_auto_ingestion():
    stats = auto_tracker.process_auto_ingestion(min_frequency=1)
    assert isinstance(stats, dict)
    assert "new_entities_registered" in stats
    assert "new_keywords_tracked" in stats
    assert "total_active_keywords" in stats
