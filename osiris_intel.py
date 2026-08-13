"""
osiris_intel.py — OSIRIS Intelligence Layer ported to Python
OFAC SDN Sanctions Lookup + Wikidata SPARQL Entity Resolution
"""
import asyncio
import csv
import json
import logging
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

# ── OpenSanctions OFAC SDN Index ──
SANCTIONS_URL = "https://data.opensanctions.org/datasets/latest/us_ofac_sdn/targets.simple.csv"
SANCTIONS_CACHE_FILE = Path("data/osiris_sanctions_cache.json")
SANCTIONS_REFRESH_HOURS = 24

_sanctions_index: dict[str, list[dict]] = {}
_sanctions_last_refresh: float = 0
_sanctions_lock = asyncio.Lock()


async def _download_sanctions_csv() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(SANCTIONS_URL, timeout=60) as resp:
            if resp.status == 200:
                return await resp.text()
            raise RuntimeError(f"OpenSanctions HTTP {resp.status}")


def _parse_sanctions_csv(csv_text: str) -> dict[str, list[dict]]:
    """Parse OpenSanctions CSV into a normalized- name -> [entries] index."""
    index: dict[str, list[dict]] = {}
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        name = (row.get("name") or "").strip()
        aliases = (row.get("aliases") or "")
        schema = (row.get("schema") or "").strip()
        entity = {
            "id": row.get("id", "").strip(),
            "schema": schema,
            "name": name,
            "aliases": aliases,
            "country": (row.get("country") or "").strip(),
            "program": (row.get("program") or "").strip(),
            "listing_date": (row.get("listing_date") or "").strip(),
            "source": "OpenSanctions / US OFAC SDN",
        }
        # Index by name
        normalized = _normalize_name(name)
        if normalized:
            index.setdefault(normalized, []).append(entity)
        # Index by each alias
        if aliases:
            for alias in aliases.split(";"):
                alias = alias.strip()
                if alias:
                    an = _normalize_name(alias)
                    if an and an != normalized:
                        index.setdefault(an, []).append(entity)
    return index


def _normalize_name(name: str) -> str:
    """Normalize a name for fuzzy matching."""
    n = re.sub(r"[^a-z0-9\s]", "", name.lower().strip())
    n = re.sub(r"\s+", " ", n)
    return n


async def ensure_sanctions_index() -> dict[str, list[dict]]:
    global _sanctions_index, _sanctions_last_refresh
    now = time.time()
    async with _sanctions_lock:
        if _sanctions_index and (now - _sanctions_last_refresh) < (SANCTIONS_REFRESH_HOURS * 3600):
            return _sanctions_index
        # Try loading from cache file first
        if SANCTIONS_CACHE_FILE.exists():
            age_hours = (now - SANCTIONS_CACHE_FILE.stat().st_mtime) / 3600
            if age_hours < SANCTIONS_REFRESH_HOURS:
                try:
                    with open(SANCTIONS_CACHE_FILE, "r", encoding="utf-8") as f:
                        _sanctions_index = json.load(f)
                    _sanctions_last_refresh = SANCTIONS_CACHE_FILE.stat().st_mtime
                    logger.info(f"[OSIRIS-INTEL] Sanctions index loaded from cache: {len(_sanctions_index)} entries")
                    return _sanctions_index
                except Exception as e:
                    logger.warning(f"[OSIRIS-INTEL] Cache load failed: {e}")
        # Download fresh
        try:
            csv_text = await _download_sanctions_csv()
            _sanctions_index = _parse_sanctions_csv(csv_text)
            _sanctions_last_refresh = time.time()
            # Write cache
            SANCTIONS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SANCTIONS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_sanctions_index, f, ensure_ascii=False)
            logger.info(f"[OSIRIS-INTEL] Sanctions index refreshed: {len(_sanctions_index)} normalized entries")
        except Exception as e:
            logger.error(f"[OSIRIS-INTEL] Failed to download sanctions: {e}")
            if _sanctions_index:
                logger.info("[OSIRIS-INTEL] Using stale sanctions index")
            else:
                _sanctions_index = {}
        return _sanctions_index


def search_sanctions(query: str, schema: str | None = None, limit: int = 25) -> list[dict]:
    """Search the OFAC SDN index by name (exact normalized match + prefix)."""
    if not _sanctions_index:
        return []
    nq = _normalize_name(query)
    if not nq or len(nq) < 2:
        return []
    results: list[dict] = []
    seen_ids: set[str] = set()
    # Exact match first
    for name_key, entries in _sanctions_index.items():
        if name_key == nq or name_key.startswith(nq) or nq in name_key:
            for e in entries:
                if schema and e.get("schema", "").lower() != schema.lower():
                    continue
                if e["id"] not in seen_ids:
                    seen_ids.add(e["id"])
                    results.append(e)
        if len(results) >= limit:
            break
    # If few results, try broader match
    if len(results) < 5:
        nq_parts = set(nq.split())
        if len(nq_parts) > 1:
            for name_key, entries in _sanctions_index.items():
                key_parts = set(name_key.split())
                if nq_parts & key_parts:
                    for e in entries:
                        if schema and e.get("schema", "").lower() != schema.lower():
                            continue
                        if e["id"] not in seen_ids:
                            seen_ids.add(e["id"])
                            results.append(e)
                if len(results) >= limit:
                    break
    return results[:limit]


def match_sanctions_exact(value: str) -> list[dict] | None:
    """Cross-check a value (name, domain, IP) against sanctions. Returns hits or None."""
    if not _sanctions_index:
        return None
    nv = _normalize_name(value)
    if not nv:
        return None
    hits: list[dict] = []
    seen_ids: set[str] = set()
    for name_key, entries in _sanctions_index.items():
        if nv == name_key or nv in name_key or name_key in nv:
            for e in entries:
                if e["id"] not in seen_ids:
                    seen_ids.add(e["id"])
                    hits.append(e)
    return hits if hits else None


# ── Wikidata SPARQL Resolver ──
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
_WIKIDATA_CACHE: OrderedDict[str, dict] = OrderedDict()
_WIKIDATA_CACHE_MAX = 10000
_WIKIDATA_CACHE_TTL = timedelta(hours=24)


async def wikidata_query(sparql: str) -> list[dict]:
    """Execute a SPARQL query against Wikidata with caching."""
    cache_key = hashlib_md5(sparql.encode())
    now = datetime.now()
    # Check cache
    if cache_key in _WIKIDATA_CACHE:
        entry = _WIKIDATA_CACHE[cache_key]
        if now - entry["ts"] < _WIKIDATA_CACHE_TTL:
            _WIKIDATA_CACHE.move_to_end(cache_key)
            return entry["data"]
    # Execute
    headers = {"Accept": "application/sparql-results+json", "User-Agent": "COBALTO-OSIRIS/1.0"}
    params = {"format": "json", "query": sparql}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WIKIDATA_SPARQL_URL, params=params, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for bind in data.get("results", {}).get("bindings", []):
                        row = {}
                        for k, v in bind.items():
                            row[k] = v.get("value", "")
                        results.append(row)
                    # Cache it
                    _WIKIDATA_CACHE[cache_key] = {"data": results, "ts": now}
                    if len(_WIKIDATA_CACHE) > _WIKIDATA_CACHE_MAX:
                        _WIKIDATA_CACHE.popitem(last=False)
                    return results
                logger.warning(f"[OSIRIS-INTEL] Wikidata SPARQL HTTP {resp.status}")
                return []
    except Exception as e:
        logger.error(f"[OSIRIS-INTEL] Wikidata SPARQL error: {e}")
        return []


def hashlib_md5(s: bytes) -> str:
    import hashlib
    return hashlib.md5(s).hexdigest()


async def resolve_aircraft(ident: str) -> dict:
    """Resolve aircraft info via Wikidata."""
    sparql = f"""
    SELECT ?item ?itemLabel ?countryLabel ?operatorLabel ?manufacturerLabel ?modelLabel WHERE {{
      {{
        ?item wdt:P31 wd:Q11436 .
        ?item rdfs:label "{ident}"@en .
      }} UNION {{
        ?item wdt:P31 wd:Q11436 .
        ?item wdt:P1448 ?callsign .
        FILTER(CONTAINS(LCASE(?callsign), "{ident.lower()}"))
      }}
      OPTIONAL {{ ?item wdt:P17 ?country . }}
      OPTIONAL {{ ?item wdt:P137 ?operator . }}
      OPTIONAL {{ ?item wdt:P176 ?manufacturer . }}
      OPTIONAL {{ ?item wdt:P2047 ?model . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """
    results = await wikidata_query(sparql)
    nodes = []
    links = []
    for r in results:
        item_id = r.get("item", "").split("/")[-1]
        nodes.append({"id": item_id, "label": r.get("itemLabel", ident), "type": "aircraft", "properties": r})
    # Cross-check sanctions
    sanctions = match_sanctions_exact(ident)
    if sanctions:
        for s in sanctions:
            nodes.append({"id": s["id"], "label": s["name"], "type": "sanction", "properties": s})
            links.append({"source": ident, "target": s["id"], "label": "SANCTIONS_MATCH"})
    return {"nodes": nodes, "links": links, "entity": {"type": "aircraft", "id": ident}}


async def resolve_vessel(ident: str) -> dict:
    """Resolve vessel info."""
    sparql = f"""
    SELECT ?item ?itemLabel ?flagLabel ?ownerLabel ?operatorLabel WHERE {{
      ?item wdt:P31 wd:Q11446 .
      {{ ?item rdfs:label "{ident}"@en . }} UNION
      {{ ?item wdt:P1448 ?name . FILTER(CONTAINS(LCASE(?name), "{ident.lower()}")) }}
      OPTIONAL {{ ?item wdt:P17 ?flag . }}
      OPTIONAL {{ ?item wdt:P127 ?owner . }}
      OPTIONAL {{ ?item wdt:P137 ?operator . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """
    results = await wikidata_query(sparql)
    nodes = []
    links = []
    for r in results:
        item_id = r.get("item", "").split("/")[-1]
        nodes.append({"id": item_id, "label": r.get("itemLabel", ident), "type": "vessel", "properties": r})
    sanctions = match_sanctions_exact(ident)
    if sanctions:
        for s in sanctions:
            nodes.append({"id": s["id"], "label": s["name"], "type": "sanction", "properties": s})
            links.append({"source": ident, "target": s["id"], "label": "SANCTIONS_MATCH"})
    return {"nodes": nodes, "links": links, "entity": {"type": "vessel", "id": ident}}


async def resolve_country(country_name: str) -> dict:
    """Resolve country intelligence."""
    sparql = f"""
    SELECT ?country ?countryLabel ?capitalLabel ?population ?area ?headLabel ?currencyLabel ?tld ?callingCode ?memberOfLabel WHERE {{
      ?country wdt:P31 wd:Q6256 .
      {{ ?country rdfs:label "{country_name}"@en . }} UNION
      {{ ?country wdt:P1448 ?official . FILTER(CONTAINS(LCASE(?official), "{country_name.lower()}")) }}
      OPTIONAL {{ ?country wdt:P36 ?capital . }}
      OPTIONAL {{ ?country wdt:P1082 ?population . }}
      OPTIONAL {{ ?country wdt:P2046 ?area . }}
      OPTIONAL {{ ?country wdt:P35 ?head . }}
      OPTIONAL {{ ?country wdt:P38 ?currency . }}
      OPTIONAL {{ ?country wdt:P78 ?tld . }}
      OPTIONAL {{ ?country wdt:P474 ?callingCode . }}
      OPTIONAL {{ ?country wdt:P463 ?memberOf . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 1
    """
    results = await wikidata_query(sparql)
    if not results:
        return {}
    r = results[0]
    return {
        "name": r.get("countryLabel", country_name),
        "capital": r.get("capitalLabel", ""),
        "population": r.get("population", ""),
        "area": r.get("area", ""),
        "head_of_state": r.get("headLabel", ""),
        "currency": r.get("currencyLabel", ""),
        "tld": r.get("tld", ""),
        "calling_code": r.get("callingCode", ""),
        "memberships": [v for k, v in r.items() if k.startswith("memberOfLabel") and v],
    }
