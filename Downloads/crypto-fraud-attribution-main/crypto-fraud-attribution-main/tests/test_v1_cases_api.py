"""Tests for V1 Cases API, NCRP / SAHYOG Contract, Bulk CSV, and WebSockets."""

from datetime import datetime, timezone
from decimal import Decimal
import io
import pytest
from fastapi.testclient import TestClient

import backend.api.investigations as inv
from backend.main import app
from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.mock import MockConnector

client = TestClient(app)

A = "0x" + "a" * 40
B = "0x" + "b" * 40
C = "0x" + "c" * 40


def make_tx(h, frm, to, amt="1.0"):
    return NormalizedTransaction(
        chain="ethereum",
        tx_hash=h,
        from_address=frm.lower(),
        to_address=to.lower(),
        amount=Decimal(amt),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
        block_number=100,
    )


@pytest.fixture(autouse=True)
def _reset():
    inv.set_test_connector(None)
    inv._INVESTIGATIONS.clear()
    yield
    inv.set_test_connector(None)
    inv._INVESTIGATIONS.clear()


# --- Appendix A: POST /api/v1/cases and GET /api/v1/cases/{case_id} ---
def test_appendix_a_post_and_get_case():
    inv.set_test_connector(MockConnector([make_tx("0x1", A, B, "5.0"), make_tx("0x2", B, C, "4.8")]))

    payload = {
        "complaint_ref": "NCRP-2026-9988",
        "wallet_address": A,
        "chain": "ethereum",
        "reported_amount": 5.0,
        "asset": "USDT",
        "options": {"max_hops": 3, "min_taint_share": 0.05},
        "complaint_category": "Investment task fraud",
    }
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert "id" in data
    assert data["complaint_ref"] == "NCRP-2026-9988"
    assert data["status"] == "completed"
    assert "risk" in data
    assert "score" in data["risk"]
    assert "attribution" in data
    assert "report_url" in data

    cid = data["id"]
    # Retrieve case via GET /api/v1/cases/{cid}
    resp_get = client.get(f"/api/v1/cases/{cid}")
    assert resp_get.status_code == 200
    get_data = resp_get.json()
    assert get_data["id"] == cid
    assert get_data["complaint_ref"] == "NCRP-2026-9988"


# --- Bulk CSV Processing ---
def test_bulk_csv_upload():
    csv_content = """complaint_ref,wallet_address,chain,amount,asset
NCRP-001,0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,ethereum,10.5,ETH
NCRP-002,bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq,auto,0.5,BTC
NCRP-003,TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t,auto,1000,USDT
"""
    resp = client.post("/api/v1/cases/bulk", params={"csv_text": csv_content})
    assert resp.status_code == 200
    res = resp.json()
    assert res["successfully_ingested"] == 3
    assert res["failed_count"] == 0
    assert len(res["cases"]) == 3
    assert res["cases"][0]["chain"] == "ethereum"
    assert res["cases"][1]["chain"] == "bitcoin"
    assert res["cases"][2]["chain"] == "tron"


# --- Recovery Layer V1 Endpoints ---
def test_v1_recovery_layer_endpoints():
    inv.set_test_connector(MockConnector([make_tx("0x10", A, B, "2.0")]))
    create_resp = client.post(
        "/api/v1/cases",
        json={"wallet_address": A, "chain": "ethereum", "reported_amount": 2.0},
    )
    cid = create_resp.json()["id"]

    # 1. Ranking
    r_ranking = client.get(f"/api/v1/cases/{cid}/ranking")
    assert r_ranking.status_code == 200
    assert "destinations_ranked" in r_ranking.json()

    # 2. Clock
    r_clock = client.get(f"/api/v1/cases/{cid}/clock")
    assert r_clock.status_code == 200
    assert len(r_clock.json()["timeline_steps"]) == 5

    # 3. Patch Clock Step
    r_patch = client.patch(
        f"/api/v1/cases/{cid}/clock/STEP-1",
        json={"status": "done"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["status"] == "done"

    # 4. Summary
    r_sum = client.get(f"/api/v1/cases/{cid}/summary")
    assert r_sum.status_code == 200
    assert "sentences" in r_sum.json()

    # 5. Related
    r_rel = client.get(f"/api/v1/cases/{cid}/related")
    assert r_rel.status_code == 200

    # 6. Report JSON Export
    r_rep = client.get(f"/api/v1/cases/{cid}/report?format=json")
    assert r_rep.status_code == 200
    assert r_rep.json()["format"] == "json"
    assert r_rep.json()["report_hash"] is not None

    # 7. Audit logs
    r_audit = client.get("/api/v1/audit/logs")
    assert r_audit.status_code == 200
    assert len(r_audit.json()) > 0


# --- Admin Timing Rules Table ---
def test_v1_admin_rules():
    r_rules = client.get("/api/v1/admin/rules")
    assert r_rules.status_code == 200
    assert len(r_rules.json()) >= 5

    r_put = client.put(
        "/api/v1/admin/rules",
        json={"step_type": "preservation_notice_sent", "due_hours": 4.5},
    )
    assert r_put.status_code == 200
    assert r_put.json()["due_hours"] == 4.5


# --- Live WebSocket ---
def test_v1_case_websocket():
    with client.websocket_connect("/api/v1/cases/WS-TEST-CASE/ws") as ws:
        init_data = ws.receive_json()
        assert init_data["event"] == "connection_established"
        assert init_data["case_id"] == "WS-TEST-CASE"

        ws.send_text("ping")
        hb = ws.receive_json()
        assert hb["event"] == "heartbeat"
