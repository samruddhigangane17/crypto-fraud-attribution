"""Integration tests for FastAPI endpoints (Member 2 intelligence APIs)."""

from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend.mock_data.mock_case import MOCK_PATHS, WALLET_A

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-investigator-jwt-token-12345"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Member 2" in data["role_member_2"]


def test_list_and_search_address_labels():
    response = client.get("/api/registry/labels")
    assert response.status_code == 200
    labels = response.json()
    assert len(labels) >= 8

    # Search by entity name
    search_res = client.get("/api/registry/labels?query=Binance")
    assert search_res.status_code == 200
    binance_labels = search_res.json()
    assert len(binance_labels) >= 1
    assert any("Binance" in item["entity_name"] for item in binance_labels)


def test_add_address_label_requires_auth():
    """Verify POST /registry/labels is protected by investigator auth."""
    payload = {
        "chain": "ethereum",
        "address": "0x1234567812345678123456781234567812345678",
        "entity_name": "Auth Guarded Label",
        "entity_category": "high_risk",
        "source": "Investigator Manual Entry",
        "confidence": 0.9,
    }
    # Unauthenticated -> 401
    unauth = client.post("/api/registry/labels", json=payload)
    assert unauth.status_code == 401

    # Authenticated -> 201
    auth_res = client.post("/api/registry/labels", json=payload, headers=AUTH_HEADERS)
    assert auth_res.status_code == 201


def test_match_single_address_endpoint():
    # Match Binance hot wallet
    res = client.get(
        "/api/attribution/match",
        params={"chain": "ethereum", "address": "0x28c6c06298d514db089934071355e5743bf21d60"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_matched"] is True
    assert data["match_type"] == "EXACT"
    assert data["label"]["entity_name"] == "Binance Hot Wallet 14"

    # Match unknown address -> marked UNKNOWN, not suspicious
    res_unk = client.get(
        "/api/attribution/match",
        params={"chain": "ethereum", "address": "0x000000000000000000000000000000000000dead"},
    )
    assert res_unk.status_code == 200
    data_unk = res_unk.json()
    assert data_unk["is_matched"] is False
    assert data_unk["match_type"] == "UNKNOWN"


def test_assess_real_case_and_retrieve_risk():
    """POST /api/investigations/{id}/assess computes risk & confidence on real paths."""
    case_id = "INV-LIVE-ASSESSMENT-001"
    assess_payload = {
        "chain": "ethereum",
        "reported_address": WALLET_A,
        "paths": [p.model_dump(mode="json") for p in MOCK_PATHS],
        "investigator_name": "Senior Detective Holmes",
        "data_completeness": 1.0,
    }

    # Unauthenticated assess -> 401
    unauth_assess = client.post(f"/api/investigations/{case_id}/assess", json=assess_payload)
    assert unauth_assess.status_code == 401

    # Authenticated assess -> 200
    assess_res = client.post(
        f"/api/investigations/{case_id}/assess",
        json=assess_payload,
        headers=AUTH_HEADERS,
    )
    assert assess_res.status_code == 200
    assess_data = assess_res.json()

    assert assess_data["investigation_id"] == case_id
    assert assess_data["risk_assessment"]["overall_score"] > 0
    assert len(assess_data["endpoints"]) >= 2
    assert len(assess_data["alerts_generated"]) >= 1

    # Verify subsequent GET /risk returns the calculated assessment
    risk_res = client.get(f"/api/investigations/{case_id}/risk")
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert risk_data["investigation_id"] == case_id
    assert risk_data["risk_assessment"]["overall_score"] == assess_data["risk_assessment"]["overall_score"]


def test_unknown_case_id_returns_404():
    """Mistyped or non-existent cases return 404 rather than fallback fake data."""
    unknown_id = "INV-DOES-NOT-EXIST-999"

    # /risk must return 404
    risk_res = client.get(f"/api/investigations/{unknown_id}/risk")
    assert risk_res.status_code == 404
    assert f"Investigation '{unknown_id}' not found" in risk_res.json()["detail"]

    # /alerts must return 404
    alerts_res = client.get(f"/api/investigations/{unknown_id}/alerts")
    assert alerts_res.status_code == 404

    # /report download must return 404
    report_res = client.get(
        f"/api/investigations/{unknown_id}/report/download",
        headers=AUTH_HEADERS,
    )
    assert report_res.status_code == 404


def test_explicit_demo_id_accessible():
    """Explicit demo case IDs with prefix DEMO- remain accessible for demonstration."""
    demo_res = client.get("/api/investigations/DEMO-INVESTIGATION-001/risk")
    assert demo_res.status_code == 200
    assert demo_res.json()["investigation_id"] == "DEMO-INVESTIGATION-001"

    # Real-style ID without assessment returns 404
    real_style_res = client.get("/api/investigations/INV-2026-9041/risk")
    assert real_style_res.status_code == 404


def test_monitoring_and_alerts_endpoints():
    demo_id = "DEMO-INVESTIGATION-001"
    # Unauthenticated monitor config -> 401
    mon_payload = {
        "investigation_id": demo_id,
        "chain": "ethereum",
        "watched_addresses": ["0x71c8564a59f0f9b6a1240173693e5077464d621e"],
        "is_active": True,
        "hop_limit": 3,
        "check_interval_seconds": 120,
    }
    unauth_mon = client.post(f"/api/investigations/{demo_id}/monitor", json=mon_payload)
    assert unauth_mon.status_code == 401

    # Authenticated monitor config -> 200
    mon_res = client.post(
        f"/api/investigations/{demo_id}/monitor",
        json=mon_payload,
        headers=AUTH_HEADERS,
    )
    assert mon_res.status_code == 200

    # Retrieve alerts for demo case
    alerts_res = client.get(f"/api/investigations/{demo_id}/alerts")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert isinstance(alerts, list)


def test_access_control_and_report_generation():
    demo_id = "DEMO-INVESTIGATION-001"

    # 1. Unauthenticated request to generate report -> 401
    unauth_post = client.post(f"/api/investigations/{demo_id}/report")
    assert unauth_post.status_code == 401

    # 2. Invalid bearer token -> 403
    forbidden_post = client.post(
        f"/api/investigations/{demo_id}/report",
        headers={"Authorization": "Bearer invalid"},
    )
    assert forbidden_post.status_code == 403

    # 3. Authenticated request -> 201 Created
    auth_post = client.post(
        f"/api/investigations/{demo_id}/report",
        headers=AUTH_HEADERS,
    )
    assert auth_post.status_code == 201
    meta = auth_post.json()
    assert meta["report_id"].startswith("REP-")
    assert meta["file_size_bytes"] > 1000

    # 4. Authenticated download -> 200 OK with PDF bytes
    dl_res = client.get(
        f"/api/investigations/{demo_id}/report/download",
        headers=AUTH_HEADERS,
    )
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert dl_res.content.startswith(b"%PDF-")
