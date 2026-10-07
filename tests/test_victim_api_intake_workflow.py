"""Verification tests for Victim Portal API & Investigator Intake Workflow."""
import pytest
from fastapi.testclient import TestClient

import backend.api.investigations as inv
from backend.main import app
from backend.victim import evidence as ev
from backend.victim import ratelimit
from backend.victim.store import global_victim_store as store


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VICTIM_DEV_MODE", "true")
    monkeypatch.setenv("VICTIM_JWT_SECRET", "test-victim-jwt-secret-" + "x" * 20)
    monkeypatch.setenv("VICTIM_PHONE_PEPPER", "test-pepper-" + "y" * 20)
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    monkeypatch.setattr(ev.global_blob_store, "base", tmp_path / "evidence")
    ratelimit.reset_all()
    store.reset()
    inv._INVESTIGATIONS.clear()
    inv.set_test_connector(inv.MockConnector())
    yield
    inv.set_test_connector(None)


@pytest.fixture
def client():
    return TestClient(app)


def test_victim_email_password_login_success(client):
    """Requirement 1: POST /victim/auth/login authenticates victim and returns session token."""
    res = client.post(
        "/victim/auth/login",
        json={
            "email": "citizen.victim@example.com",
            "password": "SecurePassword123",
            "display_name": "Citizen Alex",
            "consent_accepted": True,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["victim"]["email"] == "citizen.victim@example.com"
    assert data["victim"]["display_name"] == "Citizen Alex"

    # Token can be used to query /api/victim/me
    token = data["access_token"]
    me_res = client.get("/api/victim/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["display_name"] == "Citizen Alex"


def test_victim_email_password_login_validation(client):
    """Rejects invalid email, short password, or sensitive text."""
    # Bad email
    r1 = client.post("/victim/auth/login", json={"email": "bademail", "password": "pass"})
    assert r1.status_code == 422

    # Short password
    r2 = client.post("/victim/auth/login", json={"email": "good@example.com", "password": "12"})
    assert r2.status_code == 422

    # Seed phrase in display name
    seed = "abandon ability able about above absent absorb abstract absurd abuse access accident account accuse achieve acid"
    r3 = client.post("/victim/auth/login", json={"email": "user@test.com", "password": "password", "display_name": seed})
    assert r3.status_code == 422


def test_victim_complaints_wizard_intake(client):
    """Requirement 2: POST /victim/complaints accepts 5-step wizard payload and generates ack_id."""
    wizard_payload = {
        "typology": "Investment Scam",
        "asset": "USDT",
        "amount": 14200,
        "suspect_wallet": "0x71C8451737e6015b706d910bF000E08077D3cf62",
        "chain": "ethereum",
        "contact_method": "telegram",
        "story": "I was deceived by an investment broker and transferred 14200 USDT to their pool.",
    }

    res = client.post("/victim/complaints", json=wizard_payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert "ack_id" in data
    assert data["status"] == "Complaint Received"
    assert data["source"] == "victim_portal"
    assert data["reported_address"] == "0x71C8451737e6015b706d910bF000E08077D3cf62"
    assert "14200" in str(data["amount"])


def test_investigator_intake_queue_and_status_progression(client):
    """Requirements 3, 4, 5: Intake queue lists submissions, investigator updates status, victim tracker reads safe stage."""
    # 1. Citizen registers complaint
    wizard_payload = {
        "typology": "Task Based Fraud",
        "asset": "USDT",
        "amount": 5000,
        "suspect_wallet": "0x71C8451737e6015b706d910bF000E08077D3cf62",
        "chain": "ethereum",
        "contact_method": "whatsapp",
        "story": "Paid tasks on Telegram requiring initial deposits to unlock rewards.",
    }
    intake_res = client.post("/victim/complaints", json=wizard_payload)
    assert intake_res.status_code == 201
    complaint_data = intake_res.json()
    ack_id = complaint_data["ack_id"]
    complaint_id = complaint_data["complaint_id"]

    officer_headers = {"Authorization": "Bearer test-officer-token"}

    # 2. Investigator queries GET /api/v1/intake-queue
    queue_res = client.get("/api/v1/intake-queue", headers=officer_headers)
    assert queue_res.status_code == 200
    queue_items = queue_res.json()
    matching = [q for q in queue_items if q.get("ack_id") == ack_id or q.get("complaint_id") == complaint_id]
    assert len(matching) == 1
    item = matching[0]
    assert item["source"] == "victim_portal"
    assert "5000" in str(item["amount"])
    assert item["scammer_wallet"] == "0x71C8451737e6015b706d910bF000E08077D3cf62"

    # 3. Citizen checks initial status: GET /victim/cases/{ack_id}/status
    st_res = client.get(f"/victim/cases/{ack_id}/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["current_stage"] == "Complaint Received"
    # Ensure no internal intelligence is leaked to the victim
    forbidden = {"risk", "risk_assessment", "score", "cluster", "clustering_findings", "attribution", "case_id", "paths", "graph"}
    assert not (set(st_data.keys()) & forbidden)

    # 4. Investigator updates status to 'Under Verification'
    patch1 = client.patch(
        f"/api/v1/intake/{ack_id}/status",
        json={"stage": "under_verification"},
        headers=officer_headers,
    )
    assert patch1.status_code == 200
    assert patch1.json()["current_stage"] == "Under Verification"

    st_res = client.get(f"/victim/cases/{ack_id}/status")
    assert st_res.json()["current_stage"] == "Under Verification"

    # 5. Investigator updates status to 'Investigation in Progress'
    patch2 = client.patch(
        f"/api/v1/intake/{ack_id}/status",
        json={"stage": "in_progress"},
        headers=officer_headers,
    )
    assert patch2.status_code == 200
    assert patch2.json()["current_stage"] == "Investigation in Progress"

    st_res = client.get(f"/victim/cases/{ack_id}/status")
    assert st_res.json()["current_stage"] == "Investigation in Progress"

    # 6. Investigator updates status to 'Action Taken'
    patch3 = client.patch(
        f"/api/v1/intake/{ack_id}/status",
        json={"stage": "action_taken"},
        headers=officer_headers,
    )
    assert patch3.status_code == 200
    assert patch3.json()["current_stage"] == "Action Taken"

    st_res = client.get(f"/victim/cases/{ack_id}/status")
    assert st_res.json()["current_stage"] == "Action Taken"

    # 7. Investigator marks status as 'Closed'
    patch4 = client.patch(
        f"/api/v1/intake/{ack_id}/status",
        json={"stage": "closed"},
        headers=officer_headers,
    )
    assert patch4.status_code == 200
    assert patch4.json()["current_stage"] == "Closed"

    st_res = client.get(f"/victim/cases/{ack_id}/status")
    assert st_res.json()["current_stage"] == "Closed"
