"""
entity_resolver.py — Fuzzy entity resolution engine.
Builds on osiris_intel's OFAC SDN index and adds Levenshtein,
token-set ratio, and optional embedding-based matching.
"""
import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_LEVENSHTEIN_RATIO = 0.15
_TOKEN_SET_MIN_RATIO = 60


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0.0 = identical, 1.0 =完全不同)."""
    if not s1 and not s2:
        return 0.0
    if not s1 or not s2:
        return 1.0
    # Optimize: use SequenceMatcher which is O(n) in practice
    return 1.0 - SequenceMatcher(None, s1, s2).ratio()


def token_set_ratio(s1: str, s2: str) -> int:
    """Token-set ratio: intersection over union of tokens (0-100)."""
    t1 = set(s1.split())
    t2 = set(s2.split())
    if not t1 or not t2:
        return 0
    intersection = t1 & t2
    union = t1 | t2
    return int(len(intersection) / len(union) * 100)


def fuzzy_match_name(query: str, candidate: str) -> Tuple[float, str]:
    """Returns (score, method) where score 0.0 = perfect match, higher = worse."""
    nq = _norm(query)
    nc = _norm(candidate)
    if not nq or not nc:
        return 1.0, "empty"

    # 1. Exact match
    if nq == nc:
        return 0.0, "exact"

    # 2. Substring / prefix
    if nq in nc or nc in nq:
        return 0.05, "substr"

    # 3. Token-set ratio
    tsr = token_set_ratio(nq, nc)
    if tsr >= 80:
        return round(0.1 + (100 - tsr) / 500, 4), f"token_set_{tsr}"

    # 4. Levenshtein
    lr = levenshtein_ratio(nq, nc)
    if lr < _MAX_LEVENSHTEIN_RATIO:
        return round(lr, 4), f"lev_{lr:.3f}"

    # 5. Token-set fallback (broader)
    if tsr >= _TOKEN_SET_MIN_RATIO:
        return round(0.3 + (100 - tsr) / 200, 4), f"token_set_fallback_{tsr}"

    return 1.0, "no_match"


def resolve_against_index(
    query: str,
    index: Dict[str, List[dict]],
    schema: Optional[str] = None,
    limit: int = 10,
    min_score: float = 0.5,
) -> List[dict]:
    """
    Fuzzy-resolve a name against the OFAC SDN index.
    Returns sorted list of matches with scores.
    score = 0.0 means perfect match, lower is better.
    """
    results = []
    seen_ids = set()
    nq = _norm(query)
    if not nq or len(nq) < 2:
        return []

    for name_key, entries in index.items():
        score, method = fuzzy_match_name(query, name_key)
        if score > min_score:
            continue
        for e in entries:
            if schema and e.get("schema", "").lower() != schema.lower():
                continue
            if e["id"] not in seen_ids:
                seen_ids.add(e["id"])
                results.append({**e, "_match_score": score, "_match_method": method})

    results.sort(key=lambda x: x["_match_score"])
    return results[:limit]


def batch_resolve(
    names: List[str],
    index: Dict[str, List[dict]],
    schema: Optional[str] = None,
    threshold: float = 0.3,
) -> Dict[str, List[dict]]:
    """Resolve multiple names in batch."""
    return {name: resolve_against_index(name, index, schema, limit=5, min_score=threshold) for name in names}


def _norm(name: str) -> str:
    """Aggressive normalization: lowercase, remove non-alphanum, collapse spaces."""
    n = re.sub(r"[^a-z0-9\s]", "", name.lower().strip())
    n = re.sub(r"\s+", " ", n).strip()
    return n
