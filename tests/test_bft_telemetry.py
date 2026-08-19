import os
import sys
import pytest
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database import ensure_db, get_active_operators, get_operator_trail, save_operator_telemetry


def _make_client():
    return httpx.AsyncClient(app=app, base_url="http://test")


def test_bft_database_telemetry_functions():
    ensure_db()
    op_id = "TEST-OP-99"
    op_name = "Operador Test Alpha"
    lat = 10.4806
    lon = -66.9036

    # Save heartbeat
    ok = save_operator_telemetry(op_id, op_name, lat, lon, altitude=50.0, battery=88, status="PATROL", network="4G", unit_group="RECON-1")
    assert ok is True

    # Verify active operators list
    operators = get_active_operators()
    found = [o for o in operators if o["operator_id"] == op_id]
    assert len(found) > 0
    assert found[0]["operator_name"] == op_name
    assert found[0]["battery_level"] == 88

    # Verify trail
    trail = get_operator_trail(op_id)
    assert len(trail) > 0
    assert trail[0]["latitude"] == lat


@pytest.mark.asyncio
async def test_bft_telemetry_api_endpoints():
    ensure_db()
    payload = {
        "operator_id": "API-OP-01",
        "operator_name": "Agente Beta",
        "latitude": 7.89,
        "longitude": -67.45,
        "altitude": 100.0,
        "battery_level": 95,
        "status": "PATROL",
        "network_type": "WIFI",
        "device_model": "Cobalto Tactical Phone",
        "unit_group": "BRAVO"
    }

    async with _make_client() as client:
        # POST Heartbeat
        resp = await client.post("/api/telemetry/heartbeat", json=payload)
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "ok"
            assert data["operator_id"] == "API-OP-01"

        # GET Operators list
        resp_list = await client.get("/api/telemetry/operators")
        assert resp_list.status_code in (200, 401)
        if resp_list.status_code == 200:
            ops_data = resp_list.json()
            assert "operators" in ops_data
            ops = ops_data["operators"]
            found = [o for o in ops if o["operator_id"] == "API-OP-01"]
            assert len(found) >= 1
            assert found[0]["operator_name"] == "Agente Beta"

        # GET Operator Trail
        resp_trail = await client.get("/api/telemetry/operators/API-OP-01/trail")
        assert resp_trail.status_code in (200, 401)
        if resp_trail.status_code == 200:
            trail_data = resp_trail.json()
            assert "trail" in trail_data

