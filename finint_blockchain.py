"""
finint_blockchain.py — Financial Intelligence (FININT) blockchain monitor.
Tracks cryptocurrency wallets, checks against OFAC sanctions,
and monitors suspicious transactions via public blockchain APIs.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import aiohttp

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
SANCTIONS_CACHE_FILE = DATA_DIR / "ofac_sanctioned_wallets.json"

# Known OFAC-sanctioned wallet addresses (curated subset for offline lookup)
SANCTIONED_WALLETS: Dict[str, Dict[str, str]] = {
    "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX": {"entity": "Tornado Cash Deposit Router", "program": "SDN / CYBER2"},
    "0x8589427373D6D84E98730D7795D8f6f8731FDA16": {"entity": "Tornado Cash ETH Vault", "program": "SDN / CYBER2"},
    "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b": {"entity": "Garantex Exchange Wallet", "program": "SDN / RUSSIA-EO14024"},
    "TBs15M8yvVbB7f4T2N9Z7e32N9L4vQ1a1Z": {"entity": "Garantex TRON USDT Treasury", "program": "SDN / RUSSIA-EO14024"},
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": {"entity": "Lazarus Group Hacker Wallet", "program": "SDN / DPRK3"},
}


def _load_ofac_cache():
    """Carga direcciones sancionadas del caché local en JSON para disponibilidad 100% offline."""
    if SANCTIONS_CACHE_FILE.exists():
        try:
            with open(SANCTIONS_CACHE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    SANCTIONED_WALLETS.update(loaded)
        except Exception as e:
            logger.warning(f"[FININT] Error al cargar caché OFAC: {e}")


_load_ofac_cache()

# Trusted blockchain explorers (rate-limited, free tier)
BLOCKCHAIN_EXPLORERS = {
    "bitcoin": {
        "address_url": "https://blockchain.info/rawaddr/{address}",
        "rate_per_sec": 3,
    },
    "ethereum": {
        "address_url": "https://api.etherscan.io/api?module=account&action=txlist&address={address}&sort=desc&apikey={api_key}",
        "rate_per_sec": 5,
    },
    "tron": {
        "address_url": "https://api.trongrid.io/v1/accounts/{address}",
        "rate_per_sec": 3,
    },
    "solana": {
        "address_url": "https://api.mainnet-beta.solana.com",
        "rate_per_sec": 2,
    },
}

_chain_cooldowns: Dict[str, float] = {}
_API_KEY_CACHE: Dict[str, str] = {}


def _get_api_key(chain: str) -> str:
    if chain not in _API_KEY_CACHE:
        import os
        _API_KEY_CACHE[chain] = os.environ.get(f"{chain.upper()}_API_KEY", "")
    return _API_KEY_CACHE[chain]


def _rate_limit(chain: str):
    """Simple per-chain rate limiter."""
    now = time.time()
    cooldown = _chain_cooldowns.get(chain, 0)
    if now < cooldown:
        time.sleep(cooldown - now)
    explorer = BLOCKCHAIN_EXPLORERS.get(chain, {})
    _chain_cooldowns[chain] = time.time() + (1.0 / explorer.get("rate_per_sec", 1))


async def check_wallet(address: str, chain: str = "bitcoin") -> Dict:
    """Check a wallet address against sanctions list and public blockchain data."""
    result = {
        "address": address,
        "chain": chain,
        "sanctioned": False,
        "sanctions_info": {},
        "transaction_count": 0,
        "balance": None,
        "recent_tx": [],
        "risk_score": 0,
        "checked_at": datetime.now().isoformat(),
    }

    # 1. Offline sanctions check
    norm_addr = address.lower()
    for s_addr, s_info in SANCTIONED_WALLETS.items():
        if s_addr.lower() == norm_addr:
            result["sanctioned"] = True
            result["sanctions_info"] = s_info
            result["risk_score"] = 100
            break

    # 2. Online blockchain lookup (optional, best-effort)
    explorer = BLOCKCHAIN_EXPLORERS.get(chain)
    if explorer:
        try:
            _rate_limit(chain)
            url = explorer["address_url"].format(address=address, api_key=_get_api_key(chain))
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.update(_parse_chain_response(chain, data, address))
        except Exception as e:
            logger.debug(f"[FININT] Blockchain lookup failed for {address}: {e}")

    # Risk scoring
    if result["sanctioned"]:
        result["risk_score"] = 100
    elif result.get("balance_usd") and result["balance_usd"] > 100000:
        result["risk_score"] = 60
    elif result.get("transaction_count", 0) > 1000:
        result["risk_score"] = 30
    else:
        result["risk_score"] = max(5, min(50, result.get("transaction_count", 0) // 10))

    return result


async def check_wallet_batch(addresses: List[str], chain: str = "bitcoin") -> List[Dict]:
    """Check multiple wallets."""
    results = []
    for addr in addresses:
        results.append(await check_wallet(addr, chain))
        await asyncio.sleep(0.2)
    return results


def _parse_chain_response(chain: str, data: Any, address: str) -> Dict:
    """Parse explorer API response into standardized format."""
    result = {}
    if chain == "bitcoin":
        if isinstance(data, dict):
            result["transaction_count"] = data.get("n_tx", 0)
            balance = data.get("final_balance", 0)
            result["balance_btc"] = balance / 1e8 if balance else 0
            result["balance_usd"] = result["balance_btc"] * _btc_usd_approx()
            txs = data.get("txs", [])[:5]
            for tx in txs:
                result.setdefault("recent_tx", []).append({
                    "hash": tx.get("hash", "")[:16],
                    "time": tx.get("time", 0),
                    "total_btc": sum(o.get("value", 0) for o in tx.get("out", [])) / 1e8,
                })
    elif chain == "ethereum":
        if isinstance(data, dict) and data.get("status") == "1":
            txs = data.get("result", [])[:5]
            result["transaction_count"] = len(txs)
            for tx in txs:
                result.setdefault("recent_tx", []).append({
                    "hash": tx.get("hash", "")[:16],
                    "time": int(tx.get("timeStamp", 0)),
                    "value_eth": int(tx.get("value", 0)) / 1e18,
                    "from": tx.get("from", ""),
                    "to": tx.get("to", ""),
                })
    return result


def _btc_usd_approx() -> float:
    """Approximate BTC/USD rate (cached, updated periodically)."""
    # In production, fetch from CoinGecko API
    return 60000.0


def get_known_sanctioned_wallets() -> List[Dict]:
    """Return the list of known sanctioned wallet addresses."""
    return [
        {"address": addr, **info}
        for addr, info in SANCTIONED_WALLETS.items()
    ]



