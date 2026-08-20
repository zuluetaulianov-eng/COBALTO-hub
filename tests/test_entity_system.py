"""Tests for entity system: entity_resolver, entity_registry, entity_linker."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_entity_resolver_imports():
    from entity_resolver import (
        batch_resolve,
        fuzzy_match_name,
        levenshtein_ratio,
        resolve_against_index,
        token_set_ratio,
    )
    assert callable(fuzzy_match_name)
    assert callable(levenshtein_ratio)
    assert callable(token_set_ratio)
    assert callable(resolve_against_index)
    assert callable(batch_resolve)


def test_levenshtein_ratio():
    from entity_resolver import levenshtein_ratio
    # 0.0 = identical
    assert levenshtein_ratio("test", "test") == 0.0
    # completely different
    assert levenshtein_ratio("abc", "xyz") > 0.5
    # both empty
    assert levenshtein_ratio("", "") == 0.0


def test_token_set_ratio():
    from entity_resolver import token_set_ratio
    assert token_set_ratio("foo bar", "foo bar") == 100
    assert token_set_ratio("hello world", "world hello") >= 90
    assert token_set_ratio("abc", "xyz") == 0


def test_fuzzy_match_name():
    from entity_resolver import fuzzy_match_name
    score, method = fuzzy_match_name("Juan Perez", "Juan Pérez")
    assert isinstance(score, float)
    assert isinstance(method, str)
    # Lower score = better match, should be < 0.5
    assert score < 0.5


def test_fuzzy_match_no_match():
    from entity_resolver import fuzzy_match_name
    score, method = fuzzy_match_name("AAA", "ZZZ")
    assert score >= 0.9
    assert method == "no_match"


def test_resolve_against_index():
    from entity_resolver import resolve_against_index

    index = {
        "Juan Perez": [{"id": "1", "name": "Juan Perez", "schema": "Person"}],
        "Maria Lopez": [{"id": "2", "name": "Maria Lopez", "schema": "Person"}],
    }
    results = resolve_against_index("Juan Perez", index, min_score=0.3)
    assert len(results) >= 1
    assert results[0]["id"] == "1"

    no_results = resolve_against_index("Nonexistent XYZ", index, min_score=0.3)
    assert len(no_results) == 0


def test_batch_resolve():
    from entity_resolver import batch_resolve
    index = {
        "Alpha Corp": [{"id": "a1", "name": "Alpha Corp", "schema": "Organization"}],
        "Beta LLC": [{"id": "b1", "name": "Beta LLC", "schema": "Organization"}],
    }
    names = ["Alpha Corp", "Beta LLC", "Gamma Inc"]
    results = batch_resolve(names, index, threshold=0.4)
    assert len(results) == 3
    assert results["Alpha Corp"][0]["id"] == "a1"
    assert results["Beta LLC"][0]["id"] == "b1"
    assert len(results["Gamma Inc"]) == 0


def test_entity_registry_imports():
    from entity_registry import get_by_id, get_ofac_matched, get_stats, list_all, register, search
    assert callable(register)
    assert callable(search)
    assert callable(get_by_id)
    assert callable(get_ofac_matched)
    assert callable(get_stats)
    assert callable(list_all)


def test_entity_registry_register_and_search():
    from entity_registry import get_by_id, register, search

    eid = register("Test Person", entity_type="person", source="test", properties={"country": "VE"})
    assert eid is not None
    assert len(eid) > 0

    results = search("Test Person")
    assert len(results) >= 1
    assert any(r["id"] == eid for r in results)

    by_id = get_by_id(eid)
    assert by_id is not None
    assert by_id["canonical_name"] == "Test Person"
    assert by_id["entity_type"] == "person"


def test_entity_registry_ofac_flag():
    from entity_registry import get_ofac_matched, register, search

    eid = register("OFAC Listed", entity_type="person", source="ofac", ofac_match=True)
    matched = get_ofac_matched()
    assert any(r["id"] == eid for r in matched)

    results = search("OFAC")
    assert any(r.get("ofac_match") for r in results)


def test_entity_registry_stats():
    from entity_registry import get_stats
    stats = get_stats()
    assert "total_entities" in stats
    assert "by_type" in stats
    assert "ofac_matches" in stats
    assert isinstance(stats["total_entities"], int)


def test_entity_registry_list_all():
    from entity_registry import list_all
    entities = list_all(limit=10)
    assert isinstance(entities, list)
    assert len(entities) <= 10


def test_entity_linker_imports():
    from entity_linker import link_sanctions_entries, link_social_graph_nodes, run_full_link_cycle
    assert callable(link_social_graph_nodes)
    assert callable(link_sanctions_entries)
    assert callable(run_full_link_cycle)


def test_extract_tactical_entities():
    from entity_registry import extract_tactical_entities
    sample_text = "El ciudadano V-12345678 con RIF J-12345678-9 solicitó 5000 Bs. y $120. Contactar al 0412-1234567 o vehículo placa AA123BB."
    res = extract_tactical_entities(sample_text)
    assert "cedula" in res
    assert "V-12345678" in res["cedula"]
    assert "rif" in res
    assert "J-12345678-9" in res["rif"]
    assert "telefono_ve" in res
    assert "monto_bs" in res
    assert "monto_usd" in res
    assert "placa_ve" in res

