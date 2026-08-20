"""
backfill_entities.py — FASE 1.9: One-shot backfill script.
Populates the entity registry from historical OSINT entries (social graph,
news articles, sanctions index) to bootstrap the knowledge graph.
Run:  python backfill_entities.py
"""
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def backfill_from_sanctions():
    """Register all OFAC SDN entries as entities."""
    from entity_registry import register
    from osiris_intel import ensure_sanctions_index, search_sanctions

    logger.info("[BACKFILL] Loading sanctions index...")
    import asyncio
    asyncio.run(ensure_sanctions_index())

    # Fetch all sanctions by querying broad terms
    broad_queries = ["a", "e", "i", "o", "u", "san", "ban", "corp", "llc", "inc", "bank", "fund"]
    seen = set()
    count = 0

    for q in broad_queries:
        results = search_sanctions(q)
        for hit in results.get("hits", results if isinstance(results, list) else []):
            name = hit.get("name", "")
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            try:
                register(
                    canonical_name=name,
                    entity_type=_classify_sanctions_type(hit),
                    source="ofac",
                    source_id=hit.get("id", ""),
                    properties={
                        "schema": hit.get("schema", ""),
                        "program": hit.get("program", ""),
                        "country": hit.get("country", ""),
                        "remarks": hit.get("remarks", ""),
                    },
                    ofac_match=True,
                    ofac_ids=[hit.get("id", "")],
                )
                count += 1
                if count % 100 == 0:
                    logger.info(f"[BACKFILL] {count} sanctions entities registered...")
            except Exception as e:
                logger.debug(f"[BACKFILL] Skip sanction '{name}': {e}")

    logger.info(f"[BACKFILL] Registered {count} OFAC sanctions entities")
    return count


def backfill_from_historical_store():
    """Extract entity names from historical entries and register unknown ones."""
    import re
    from datetime import timedelta

    from entity_registry import register, search
    from historical_store import get_stats, query_range

    logger.info("[BACKFILL] Scanning historical entries for named entities...")
    stats = get_stats()
    total = stats.get("total_entries", 0)
    logger.info(f"[BACKFILL] Historical store has {total} entries")

    # Scan last 30 days in batches
    now = datetime.now()
    from_dt = now - timedelta(days=30)
    batch = query_range(from_dt, now, limit=5000)
    entries = batch.get("entries", [])

    # Simple entity extraction from titles
    # Looks for capitalized phrases that could be organization/person names
    pattern = re.compile(r"\b[A-Z][a-záéíóúñ]+(?:\s[A-Z][a-záéíóúñ]+){1,3}\b")
    seen_names = set()
    count = 0

    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        text = f"{title} {summary}"

        candidates = pattern.findall(text)
        for name in candidates[:10]:  # limit per entry
            name = name.strip()
            if len(name) < 6 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            # Skip if already registered
            existing = search(name, limit=1)
            if existing:
                continue

            try:
                register(
                    canonical_name=name,
                    entity_type="unknown",
                    source="historical",
                    properties={"extracted_from": entry.get("source", ""), "extracted_at": now.isoformat()},
                )
                count += 1
            except Exception:
                pass

    logger.info(f"[BACKFILL] Registered {count} new entities from historical data")
    return count


def _classify_sanctions_type(hit: dict) -> str:
    schema = (hit.get("schema", "") or "").lower()
    if "person" in schema:
        return "person"
    if "organization" in schema or "company" in schema:
        return "organization"
    if "vessel" in schema:
        return "vessel"
    if "aircraft" in schema:
        return "aircraft"
    return "sanctioned_entity"


def main():
    logger.info("=" * 60)
    logger.info("FASE 1.9 — Entity Registry Backfill")
    logger.info("=" * 60)

    start = time.time()
    sanc = backfill_from_sanctions()
    hist = backfill_from_historical_store()

    from entity_registry import get_stats
    stats = get_stats()
    elapsed = time.time() - start

    logger.info("=" * 60)
    logger.info(f"BACKFILL COMPLETE in {elapsed:.1f}s")
    logger.info(f"  Sanctions entities:  {sanc}")
    logger.info(f"  Historical entities: {hist}")
    logger.info(f"  Registry total:      {stats.get('total_entities', '?')}")
    logger.info(f"  OFAC matches:        {stats.get('ofac_matches', '?')}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
