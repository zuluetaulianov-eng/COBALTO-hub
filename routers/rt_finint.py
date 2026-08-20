"""
routers/rt_finint.py — FININT endpoints extracted from app.py
Rutas: /api/finint/*  (5 endpoints)
"""
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["finint"])


def _sanitize(obj):
    from security_utils import sanitize_for_json
    return sanitize_for_json(obj)


@router.get("/api/finint/wallet/{address}")
async def check_finint_wallet(address: str, chain: str = "bitcoin"):
    from finint_blockchain import check_wallet
    result = await check_wallet(address, chain)
    return _sanitize(result)


@router.get("/api/finint/sanctioned-wallets")
async def get_sanctioned_wallets():
    from finint_blockchain import get_known_sanctioned_wallets
    return {"wallets": get_known_sanctioned_wallets()}


@router.post("/api/finint/link-wallet")
async def link_finint_wallet(data: dict):
    from finint_entity_linker import link_wallet_to_entity
    address = data.get("address", "")
    chain = data.get("chain", "bitcoin")
    entity_name = data.get("entity_name", "")
    result = await link_wallet_to_entity(address, chain, entity_name)
    return result


@router.get("/api/finint/check-wallet-entities/{address}")
async def check_wallet_vs_entities(address: str, chain: str = "bitcoin"):
    from finint_entity_linker import check_wallet_against_entities
    result = await check_wallet_against_entities(address, chain)
    return _sanitize(result)


@router.get("/api/finint/darkweb/search")
async def search_darkweb(query: str = "", limit: int = 20):
    from finint_darkweb import monitor_paste_sites
    results = await monitor_paste_sites(query, limit)
    return {"results": results}


@router.post("/api/finint/darkweb/analyze")
async def analyze_finint_text(data: dict):
    from finint_darkweb import analyze_text_for_finint
    text = data.get("text", "")
    result = analyze_text_for_finint(text)
    return result


@router.post("/api/finint/generate-report")
async def generate_finint_report(data: dict):
    from finint_blockchain import check_wallet
    from intel_reports import generar_informe_finint_deterministico
    address = data.get("address", "")
    chain = data.get("chain", "bitcoin")
    wallet_data = await check_wallet(address, chain)
    doc_data = generar_informe_finint_deterministico(address, chain, wallet_data)
    return {
        "status": "ok",
        "codigo": doc_data.codigo,
        "resumen": doc_data.resumen_ejecutivo,
        "nivel_alerta": doc_data.nivel_alerta,
        "contenido": doc_data.analisis_completo,
    }
