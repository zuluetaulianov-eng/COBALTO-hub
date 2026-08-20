"""Tests for FININT & Dark Web modules."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_finint_blockchain_imports():
    from finint_blockchain import check_wallet, check_wallet_batch, get_known_sanctioned_wallets
    assert callable(check_wallet)
    assert callable(get_known_sanctioned_wallets)
    assert callable(check_wallet_batch)


def test_finint_sanctioned_wallets():
    from finint_blockchain import get_known_sanctioned_wallets
    wallets = get_known_sanctioned_wallets()
    assert isinstance(wallets, list)
    assert len(wallets) >= 2
    for w in wallets:
        assert "address" in w
        assert "entity" in w


def test_finint_risk_scoring():
    import asyncio

    from finint_blockchain import check_wallet
    # Test with known sanctioned address (offline check)
    result = asyncio.run(check_wallet("1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX", chain="bitcoin"))
    assert result["sanctioned"] is True
    assert result["risk_score"] == 100
    assert "Tornado Cash" in result["sanctions_info"]["entity"]


def test_finint_non_sanctioned_wallet():
    import asyncio

    from finint_blockchain import check_wallet
    result = asyncio.run(check_wallet("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", chain="bitcoin"))
    assert result["sanctioned"] is False
    assert isinstance(result["risk_score"], (int, float))


def test_darkweb_imports():
    from finint_darkweb import analyze_text_for_finint, monitor_paste_sites, scrape_onion_site
    assert callable(analyze_text_for_finint)
    assert callable(monitor_paste_sites)
    assert callable(scrape_onion_site)


def test_darkweb_analyze_text():
    from finint_darkweb import analyze_text_for_finint
    text = "Send BTC to 1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX for payment, password: admin123"
    result = analyze_text_for_finint(text)
    assert "crypto_addresses" in result
    assert "has_sanction_keywords" in result
    assert "suspicious_patterns" in result
    # Should find the BTC address
    btc = result.get("crypto_addresses", {}).get("btc", [])
    assert len(btc) >= 1
    assert "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX" in btc


def test_darkweb_suspicious_patterns():
    from finint_darkweb import analyze_text_for_finint
    text = "I have cc dumps and fullz with cvv, contact for ransomware tools"
    result = analyze_text_for_finint(text)
    assert "financial_fraud" in result["suspicious_patterns"]
    assert "cyber_threat" in result["suspicious_patterns"]


def test_darkweb_empty_text():
    from finint_darkweb import analyze_text_for_finint
    result = analyze_text_for_finint("")
    assert result["crypto_addresses"] == {}
    assert result["has_sanction_keywords"] == []
    assert result["suspicious_patterns"] == []


def test_finint_entity_linker_imports():
    from finint_entity_linker import (
        check_wallet_against_entities,
        link_onion_to_entity,
        link_wallet_to_entity,
        run_finint_link_cycle,
    )
    assert callable(link_wallet_to_entity)
    assert callable(link_onion_to_entity)
    assert callable(check_wallet_against_entities)
    assert callable(run_finint_link_cycle)


def test_darkweb_tron_and_solana_extraction():
    from finint_darkweb import analyze_text_for_finint
    text = "TRON: TBs15M8yvVbB7f4T2N9Z7e32N9L4vQ1a1Z, ETH: 0x8589427373D6D84E98730D7795D8f6f8731FDA16"
    res = analyze_text_for_finint(text)
    assert "tron" in res["crypto_addresses"]
    assert "eth" in res["crypto_addresses"]
    assert "TBs15M8yvVbB7f4T2N9Z7e32N9L4vQ1a1Z" in res["crypto_addresses"]["tron"]


def test_finint_tron_sanctioned_check():
    import asyncio

    from finint_blockchain import check_wallet
    res = asyncio.run(check_wallet("TBs15M8yvVbB7f4T2N9Z7e32N9L4vQ1a1Z", chain="tron"))
    assert res["sanctioned"] is True
    assert res["risk_score"] == 100
    assert "Garantex" in res["sanctions_info"]["entity"]


def test_generar_informe_finint_deterministico():
    from intel_reports import generar_informe_finint_deterministico
    wallet_data = {
        "address": "TBs15M8yvVbB7f4T2N9Z7e32N9L4vQ1a1Z",
        "chain": "tron",
        "sanctioned": True,
        "risk_score": 100,
        "sanctions_info": {"entity": "Garantex TRON USDT Treasury", "program": "SDN / RUSSIA-EO14024"},
    }
    doc = generar_informe_finint_deterministico("TBs15M8yvVbB7f4T2N9Z7e32N9L4vQ1a1Z", "tron", wallet_data)
    assert doc.codigo.startswith("FININT-TRON-")
    assert doc.nivel_alerta == "ALERTA CRÍTICA"
    assert "INFORME DE INTELIGENCIA FINANCIERA" in doc.analisis_completo
    assert "Garantex" in doc.analisis_completo
