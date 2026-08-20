"""Tests for infrastructure modules: event_bus, historical_store."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_event_bus_imports():
    from event_bus import EventBus, bus
    assert isinstance(bus, EventBus)
    assert callable(bus.on)
    assert callable(bus.off)
    assert callable(bus.emit)
    assert callable(bus.emit_async)
    assert callable(bus.get_history)


def test_event_bus_emit_and_receive():
    from event_bus import EventBus
    eb = EventBus()
    received = []

    def handler(event):
        received.append(event)

    eb.on("test_event", handler, "test_handler")
    eb.emit("test_event", source="pytest", data={"key": "value"})

    assert len(received) == 1
    assert received[0]["type"] == "test_event"
    assert received[0]["source"] == "pytest"
    assert received[0]["data"]["key"] == "value"


def test_event_bus_wildcard():
    from event_bus import EventBus
    eb = EventBus()
    received = []

    def handler(event):
        received.append(event["type"])

    eb.on("*", handler, "wildcard")
    eb.emit("event_a")
    eb.emit("event_b")

    assert len(received) == 2
    assert "event_a" in received
    assert "event_b" in received


def test_event_bus_off():
    from event_bus import EventBus
    eb = EventBus()
    received = []

    def handler(event):
        received.append(event)

    eb.on("test", handler, "removable")
    eb.emit("test")
    assert len(received) == 1

    eb.off("test", name="removable")
    eb.emit("test")
    assert len(received) == 1


def test_event_bus_history():
    from event_bus import EventBus
    eb = EventBus()
    eb.emit("type_a", data={"i": 1})
    eb.emit("type_a", data={"i": 2})
    eb.emit("type_b", data={"i": 3})

    all_h = eb.get_history(limit=10)
    assert len(all_h) == 3

    filtered = eb.get_history(event_type="type_a", limit=10)
    assert len(filtered) == 2
    assert all(e["type"] == "type_a" for e in filtered)


def test_event_bus_async():
    import asyncio

    from event_bus import EventBus
    eb = EventBus()
    received = []

    async def async_handler(event):
        received.append(event["type"])

    eb.on("async_event", async_handler, "async_test")
    asyncio.run(eb.emit_async("async_event"))
    assert len(received) == 1
    assert received[0] == "async_event"


def test_event_bus_handler_count():
    from event_bus import EventBus
    eb = EventBus()
    assert eb.handler_count() == 0

    eb.on("x", lambda e: None, "h1")
    eb.on("y", lambda e: None, "h2")
    assert eb.handler_count() == 2


def test_historical_store_imports():
    from historical_store import delete_older_than, get_stats, query_range, store_entries
    assert callable(store_entries)
    assert callable(query_range)
    assert callable(get_stats)
    assert callable(delete_older_than)


def test_historical_store_store_and_query():
    from datetime import datetime, timedelta

    from historical_store import query_range, store_entries

    now = datetime.now()
    entries = [
        {"id": "h1", "title": "Test Entry 1", "source": "test", "category": "info", "published": now.isoformat(), "summary": "A test entry", "link": "https://example.com/1"},
        {"id": "h2", "title": "Test Entry 2", "source": "test", "category": "alert", "severity": "critical", "published": now.isoformat(), "summary": "Critical alert", "link": "https://example.com/2"},
    ]
    store_entries(entries)

    from_dt = now - timedelta(hours=1)
    to_dt = now + timedelta(hours=1)
    results = query_range(from_dt, to_dt, limit=10)
    assert len(results["entries"]) >= 2

    alerts = query_range(from_dt, to_dt, category="alert", limit=10)
    assert len(alerts["entries"]) >= 1
    assert alerts["entries"][0]["category"] == "alert"

    critical = query_range(from_dt, to_dt, severity="critical", limit=10)
    assert len(critical["entries"]) >= 1

    searched = query_range(from_dt, to_dt, search="Critical", limit=10)
    assert len(searched["entries"]) >= 1


def test_historical_store_stats():
    from historical_store import get_stats
    stats = get_stats()
    assert "total_entries" in stats
    assert "db_path" in stats
    assert "retention_days" in stats
    assert isinstance(stats["total_entries"], int)


def test_historical_store_delete():
    from datetime import datetime, timedelta

    from historical_store import delete_older_than, query_range, store_entries

    old_dt = datetime.now() - timedelta(days=400)
    entries = [
        {"id": "old_entry_test", "title": "Old Entry", "source": "test", "category": "info", "published": old_dt.isoformat(), "summary": "Very old", "link": "https://example.com/old"},
    ]
    store_entries(entries)

    count = delete_older_than(days=365)
    assert isinstance(count, int)

    from_dt = datetime.now() - timedelta(days=500)
    to_dt = datetime.now() - timedelta(days=350)
    results = query_range(from_dt, to_dt, limit=10)
    for r in results["entries"]:
        assert r["id"] != "old_entry_test"
