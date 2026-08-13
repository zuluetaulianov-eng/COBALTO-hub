"""
finint_entity_linker.py — Links FININT artifacts (wallets, onion addresses)
to the entity registry and OFAC sanctions database.
"""
import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)


async def link_wallet_to_entity(address: str, chain: str = "bitcoin", entity_name: str = "") -> Dict:
    """Register a crypto wallet in the entity registry linked to an entity."""
    from entity_registry import register, search

    wallet_id = f"{chain}:{address}"
    canonical = entity_name or f"Wallet {address[:12]}..."

    # Check if wallet already registered
    existing = search(wallet_id, limit=1)
    if existing:
        return {"status": "exists", "entity_id": existing[0]["id"], "wallet_id": wallet_id}

    # Try to find matching entity by name if provided
    linked_entity_id = ""
    if entity_name:
        matches = search(entity_name, limit=5)
        for m in matches:
            if m["canonical_name"].lower() == entity_name.lower():
                linked_entity_id = m["id"]
                break

    eid = register(
        canonical_name=canonical,
        entity_type=f"crypto_wallet:{chain}",
        source="finint",
        source_id=wallet_id,
        properties={
            "address": address,
            "chain": chain,
            "linked_entity_id": linked_entity_id,
            "linked_entity_name": entity_name,
        },
    )

    return {"status": "created", "entity_id": eid, "wallet_id": wallet_id, "linked_to": linked_entity_id or None}


async def link_onion_to_entity(onion_url: str, entity_name: str = "") -> Dict:
    """Register a .onion address in the entity registry."""
    from entity_registry import register, search

    canonical = entity_name or onion_url[:40]

    existing = search(onion_url, limit=1)
    if existing:
        return {"status": "exists", "entity_id": existing[0]["id"]}

    linked_entity_id = ""
    if entity_name:
        matches = search(entity_name, limit=5)
        for m in matches:
            if m["canonical_name"].lower() == entity_name.lower():
                linked_entity_id = m["id"]
                break

    eid = register(
        canonical_name=canonical,
        entity_type="darkweb:onion",
        source="finint",
        source_id=onion_url,
        properties={
            "onion_url": onion_url,
            "linked_entity_id": linked_entity_id,
        },
    )

    return {"status": "created", "entity_id": eid}


async def check_wallet_against_entities(address: str, chain: str = "bitcoin") -> Dict:
    """Cross-reference a wallet against all known entities for matches."""
    from entity_registry import list_all

    result = {
        "address": address,
        "chain": chain,
        "matches": [],
        "total_entities_checked": 0,
    }

    entities = list_all(limit=500)
    result["total_entities_checked"] = len(entities)

    norm_addr = address.lower()
    for ent in entities:
        props = ent.get("properties", {})
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except Exception:
                props = {}
        ent_addr = props.get("address", "").lower()
        if ent_addr == norm_addr:
            result["matches"].append({
                "entity_id": ent["id"],
                "entity_name": ent["canonical_name"],
                "entity_type": ent["entity_type"],
                "match_type": "direct_wallet_match",
            })

    return result


async def run_finint_link_cycle():
    """Full link cycle: scan all known sanctioned wallets against entity registry."""
    from finint_blockchain import get_known_sanctioned_wallets

    logger.info("[FININT LINK] Running link cycle...")
    wallets = get_known_sanctioned_wallets()
    linked = 0

    for w in wallets:
        result = await link_wallet_to_entity(
            address=w["address"],
            chain="bitcoin",
            entity_name=w.get("entity", ""),
        )
        if result["status"] == "created":
            linked += 1

    logger.info(f"[FININT LINK] Linked {linked}/{len(wallets)} sanctioned wallets")
    return {"linked": linked, "total": len(wallets)}
