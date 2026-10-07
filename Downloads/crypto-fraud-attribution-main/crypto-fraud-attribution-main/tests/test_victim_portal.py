"""USP 3 victim portal: each test maps to a safety/test requirement in the build plan."""
import hashlib
import io
import json

import jwt
import pytest
from fastapi.testclient import TestClient

import backend.api.investigations as inv
from backend.main import app
from backend.monitoring.alerts import global_alert_engine
from backend.victim import evidence as ev
from backend.victim import ratelimit, service
from backend.victim.otp import global_otp_service
from backend.victim.safety import check_text
from backend.victim.store import global_victim_store as store

WALLET = "0xmock_wallet_a"          # demo wallet; mock connector, no network
OTHER_WALLET = "0x" + "ab" * 20
FORBIDDEN_KEYS = {"risk", "risk_assessment", "score", "cluster", "clusters", "clustering_findings",
                  "attribution", "endpoints", "investigator_notes", "typology", "ranking", "convergence",
                  "case_id", "paths", "graph", "alerts", "recovery_clock", "notes", "verified_by"}
SEED = ("abandon ability able about above absent absorb abstract absurd abuse access accident "
        "account accuse achieve acid")


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("VICTIM_DEV_MODE", "true")
    monkeypatch.setenv("VICTIM_JWT_SECRET", "test-victim-secret-" + "x" * 20)
    monkeypatch.setenv("VICTIM_PHONE_PEPPER", "test-pepper-" + "y" * 20)
    monkeypatch.setattr(ev.global_blob_store, "base", tmp_path / "evidence")
    ratelimit.reset_all()
    global_otp_service.reset()
    store.reset()
    inv._INVESTIGATIONS.clear()
    global_alert_engine._alerts_by_case.clear()
    global_alert_engine._seen_event_keys.clear()
    inv.set_test_connector(inv.MockConnector())
    yield
    inv.set_test_connector(None)


@pytest.fixture
def client():
    return TestClient(app)


def login(client, phone="9876543210"):
    code = client.post("/api/victim/auth/otp", json={"phone": phone}).json()["dev_otp"]
    r = client.post("/api/victim/auth/verify", json={"phone": phone, "otp": code, "consent_accepted": True})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


FULL = {"fraud_type": "investment", "incident_time": "2026-10-01T09:00:00Z", "amount_lost": "1500.50",
        "asset": "USDT", "payment_method": "crypto_wallet", "scammer_wallet": WALLET, "platform": "telegram",
        "story": "A person on Telegram promised high returns and then stopped replying."}


def file_complaint(client, h, **over):
    cid = client.post("/api/victim/complaints", json={**FULL, **over}, headers=h).json()["complaint_id"]
    r = client.post(f"/api/victim/complaints/{cid}/submit", json={"declaration_true": True}, headers=h)
    return cid, r


def keys_in(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k.lower()
            yield from keys_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys_in(v)


# ---- auth realm -----------------------------------------------------------------------------
def test_login_requires_valid_otp_and_consent(client):
    client.post("/api/victim/auth/otp", json={"phone": "9876543210"})
    assert client.post("/api/victim/auth/verify",
                       json={"phone": "9876543210", "otp": "000000", "consent_accepted": True}).status_code == 401
    code = client.post("/api/victim/auth/otp", json={"phone": "9876543210"}).json()["dev_otp"]
    r = client.post("/api/victim/auth/verify", json={"phone": "9876543210", "otp": code, "consent_accepted": False})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_otp_is_single_use_and_phone_not_stored(client):
    code = client.post("/api/victim/auth/otp", json={"phone": "9876543210"}).json()["dev_otp"]
    body = {"phone": "9876543210", "otp": code, "consent_accepted": True}
    assert client.post("/api/victim/auth/verify", json=body).status_code == 200
    assert client.post("/api/victim/auth/verify", json=body).status_code == 401
    assert "9876543210" not in json.dumps(list(store.victims.values()))


def test_otp_requests_are_rate_limited(client):
    codes = [client.post("/api/victim/auth/otp", json={"phone": "9876543210"}).status_code for _ in range(4)]
    assert codes[:3] == [202, 202, 202] and codes[3] == 429


def test_otp_not_exposed_outside_dev_mode(client, monkeypatch):
    monkeypatch.setenv("VICTIM_DEV_MODE", "")
    assert "dev_otp" not in client.post("/api/victim/auth/otp", json={"phone": "9876543210"}).json()


def test_realms_are_separate(client, monkeypatch):
    h = login(client)
    # victim token is useless on investigator endpoints (real signature check, no dev stub)
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "investigator-secret-" + "z" * 20)
    assert client.get("/api/v1/intake-queue", headers=h).status_code == 403
    # an investigator-style Supabase token is useless on victim endpoints
    sup = jwt.encode({"sub": "u1", "aud": "authenticated", "role": "authenticated"},
                     "investigator-secret-" + "z" * 20, algorithm="HS256")
    assert client.get("/api/victim/complaints", headers={"Authorization": f"Bearer {sup}"}).status_code == 401
    assert client.get("/api/victim/complaints").status_code == 401


# ---- seed phrase / sensitive input -----------------------------------------------------------
def test_seed_phrase_text_is_blocked_everywhere(client):
    h = login(client)
    cid = client.post("/api/victim/complaints", json={}, headers=h).json()["complaint_id"]
    r = client.patch(f"/api/victim/complaints/{cid}", json={"story": f"my wallet words are {SEED}"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SENSITIVE_DATA"
    assert SEED not in r.text                               # never echoed back
    assert store.get_complaint(cid).get("story") is None    # never stored


@pytest.mark.parametrize("text", [
    "OTP 482913", "my password is hunter22", "aadhaar 1234 5678 9012",
    "private key: 0x" + "ab" * 32, "1. " + " 2. ".join(SEED.split()),
])
def test_other_sensitive_values_are_blocked(text):
    assert check_text(text) is not None


@pytest.mark.parametrize("text", [
    "A person on Telegram promised high returns, then I sent the money to the wallet they gave me and they stopped replying.",
    "the scammer asked for my seed phrase but I refused",
    "I paid 500 USDT on 1 October and the transaction id was 123456789012",
])
def test_normal_stories_are_not_blocked(text):
    assert check_text(text) is None


# ---- complaint wizard ------------------------------------------------------------------------
def test_draft_autosave_and_submit(client):
    h = login(client)
    cid = client.post("/api/victim/complaints", json={"fraud_type": "phishing"}, headers=h).json()["complaint_id"]
    assert client.patch(f"/api/victim/complaints/{cid}", json={"amount_lost": "10"}, headers=h).status_code == 200
    r = client.post(f"/api/victim/complaints/{cid}/submit", json={"declaration_true": True}, headers=h)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "MISSING_FIELDS"
    cid2, r2 = file_complaint(client, h)
    assert r2.status_code == 201 and r2.json()["ack_id"].startswith("VC-")
    assert client.patch(f"/api/victim/complaints/{cid2}", json={"story": "x"}, headers=h).status_code == 409


def test_declaration_is_required(client):
    h = login(client)
    cid = client.post("/api/victim/complaints", json=FULL, headers=h).json()["complaint_id"]
    r = client.post(f"/api/victim/complaints/{cid}/submit", json={"declaration_true": False}, headers=h)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "DECLARATION_REQUIRED"


def test_address_format_check_and_chain_detection(client):
    assert client.get("/api/victim/validate-address", params={"address": OTHER_WALLET}).json() == \
        {"valid": True, "chain": "ethereum"}
    assert client.get("/api/victim/validate-address", params={"address": "nope"}).json()["valid"] is False


def test_bad_wallet_and_bad_tx_hash_rejected(client):
    h = login(client)
    _, r = file_complaint(client, h, scammer_wallet="not-a-wallet")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "BAD_WALLET"
    _, r = file_complaint(client, h, scammer_wallet=OTHER_WALLET, tx_hash="0x123")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "BAD_TX_HASH"


def test_filing_is_rate_limited(client):
    h = login(client)
    codes = [file_complaint(client, h, scammer_wallet="0x" + f"{i:02x}" * 20)[1].status_code for i in range(4)]
    assert codes == [201, 201, 201, 429]


def test_captcha_is_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(service.captcha_verifier, "verify", lambda token, ip: token == "good")
    h = login(client)
    cid = client.post("/api/victim/complaints", json=FULL, headers=h).json()["complaint_id"]
    bad = client.post(f"/api/victim/complaints/{cid}/submit", json={"declaration_true": True}, headers=h)
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "CAPTCHA_FAILED"
    ok = client.post(f"/api/victim/complaints/{cid}/submit",
                     json={"declaration_true": True, "captcha_token": "good"}, headers=h)
    assert ok.status_code == 201


# ---- isolation + what victims can see ---------------------------------------------------------
def test_victim_cannot_read_another_victims_complaint(client):
    a, b = login(client, "9876543210"), login(client, "9123456780")
    cid, _ = file_complaint(client, a)
    for path in ("", "/evidence"):
        assert client.get(f"/api/victim/complaints/{cid}{path}", headers=b).status_code == 404
    assert client.get(f"/api/victim/cases/{cid}/status", headers=b).status_code == 404
    assert client.get(f"/api/victim/cases/{cid}/requests", headers=b).status_code == 404
    assert client.patch(f"/api/victim/complaints/{cid}", json={"story": "x"}, headers=b).status_code == 404
    assert client.get("/api/victim/complaints", headers=b).json() == []


def test_victim_endpoints_never_return_internal_fields(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    h = login(client)
    cid, _ = file_complaint(client, h)
    officer = {"Authorization": "Bearer officer-token-123"}
    client.post(f"/api/v1/intake/{cid}/verify", headers=officer)          # full pipeline -> risk etc exist
    client.post(f"/api/v1/intake/{cid}/requests", json={"text": "Please add a receipt"}, headers=officer)
    for path in ("/complaints", f"/complaints/{cid}", f"/cases/{cid}/status", f"/cases/{cid}/requests",
                 "/notifications", "/privacy/access-log", "/support", "/me"):
        body = client.get(f"/api/victim{path}", headers=h).json()
        assert not (set(keys_in(body)) & FORBIDDEN_KEYS), (path, set(keys_in(body)) & FORBIDDEN_KEYS)


# ---- USP 3 flow: complaint -> preliminary trace -> officer queue ------------------------------
def test_submit_queues_unverified_preliminary_trace_with_no_alerts(client, monkeypatch):
    h = login(client)
    cid, r = file_complaint(client, h)
    assert r.status_code == 201
    c = store.get_complaint(cid)
    case = inv._INVESTIGATIONS[c["case_id"]]
    assert case["source"] == "victim_portal" and case["status"] == "Reported"
    assert case["preliminary"] is True and case["paths"]                       # trace ran, hop-limited
    assert max(p.hop_count for p in case["paths"]) <= service.PRELIMINARY_MAX_HOPS
    assert global_alert_engine.get_alerts_by_investigation(c["case_id"]) == []  # no alerts
    assert case.get("analysis") is not None and "risk" not in case             # no scoring

    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    q = client.get("/api/v1/intake-queue", headers={"Authorization": "Bearer officer-token-123"}).json()
    assert len(q) == 1 and q[0]["tag"] == "Victim-reported (unverified)" and q[0]["preliminary_trace"]["done"]
    assert client.get("/api/victim/cases/%s/status" % cid, headers=h).json()["stage"] == "Received"


def test_intake_requires_investigator_auth(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "investigator-secret-" + "z" * 20)
    assert client.get("/api/v1/intake-queue").status_code == 401


def test_unverified_victim_cases_hidden_from_open_v1_api(client, monkeypatch):
    h = login(client)
    cid, _ = file_complaint(client, h)
    case_id = store.get_complaint(cid)["case_id"]
    assert all(c["id"] != case_id for c in client.get("/api/v1/cases").json())
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    client.post(f"/api/v1/intake/{cid}/verify", headers={"Authorization": "Bearer officer-token-123"})
    assert any(c["id"] == case_id for c in client.get("/api/v1/cases").json())


def test_verify_starts_full_investigation_and_updates_tracker(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    h, officer = login(client), {"Authorization": "Bearer officer-token-123"}
    cid, _ = file_complaint(client, h)
    r = client.post(f"/api/v1/intake/{cid}/verify", headers=officer)
    assert r.status_code == 202
    st = client.get(f"/api/victim/cases/{cid}/status", headers=h).json()
    assert st["stage"] == "Investigation in progress"
    assert [t["reached"] for t in st["timeline"]][:3] == [True, True, True]
    assert inv._INVESTIGATIONS[store.get_complaint(cid)["case_id"]]["status"] == "completed"
    assert client.post(f"/api/v1/intake/{cid}/verify", headers=officer).json()["status"] == "already_verified"
    assert client.get("/api/victim/notifications", headers=h).json()[0]["message"] == "Your case has an update"


def test_false_complaint_creates_no_alert_or_notice(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    h, officer = login(client), {"Authorization": "Bearer officer-token-123"}
    cid, _ = file_complaint(client, h)
    case_id = store.get_complaint(cid)["case_id"]
    assert client.post(f"/api/v1/intake/{cid}/reject", json={"reason": "not credible"}, headers=officer).status_code == 200
    assert global_alert_engine.get_alerts_by_investigation(case_id) == []
    assert inv._INVESTIGATIONS[case_id]["status"] == "Reported"
    assert client.get(f"/api/victim/cases/{cid}/status", headers=h).json()["stage"] == "Closed"
    assert client.post(f"/api/v1/intake/{cid}/verify", headers=officer).status_code == 409


def test_duplicate_wallet_does_not_create_duplicate_trace(client, monkeypatch):
    a, b = login(client, "9876543210"), login(client, "9123456780")
    cid_a, _ = file_complaint(client, a)
    cid_b, _ = file_complaint(client, b)
    assert store.get_complaint(cid_a)["case_id"] == store.get_complaint(cid_b)["case_id"]
    assert len(inv._INVESTIGATIONS) == 1
    # same victim filing the same wallet again returns the original acknowledgement
    cid_a2, r = file_complaint(client, a)
    assert r.json()["ack_id"] == store.get_complaint(cid_a)["ack_id"]
    # only the investigator sees that several victims reported the wallet
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    q = client.get("/api/v1/intake-queue", headers={"Authorization": "Bearer officer-token-123"}).json()
    assert {row["reports_for_wallet"] for row in q} == {2}


# ---- evidence vault ------------------------------------------------------------------------
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def upload(client, h, cid, data=PNG, name="shot.png", **form):
    return client.post(f"/api/victim/complaints/{cid}/evidence", headers=h,
                       files={"file": (name, io.BytesIO(data), "application/octet-stream")}, data=form)


def test_evidence_hash_versioning_and_custody(client):
    h = login(client)
    cid, _ = file_complaint(client, h)
    sha = hashlib.sha256(PNG).hexdigest()
    r = upload(client, h, cid, client_sha256=sha)
    assert r.status_code == 201 and r.json()["sha256"] == sha and r.json()["version"] == 1
    fid = r.json()["file_id"]
    v2 = b"\x89PNG\r\n\x1a\n" + b"\x01" * 64
    r2 = upload(client, h, cid, data=v2, replaces_file_id=fid)
    assert r2.json()["version"] == 2 and r2.json()["file_id"] == fid
    assert len(client.get(f"/api/victim/complaints/{cid}/evidence", headers=h).json()) == 2   # v1 kept
    assert client.get(f"/api/victim/complaints/{cid}/evidence/{fid}/download?version=1", headers=h).content == PNG
    log = client.get(f"/api/victim/complaints/{cid}/evidence/{fid}/verify", headers=h).json()["custody_log"]
    assert [e["event"] for e in log] == ["uploaded", "version_added"]
    assert store.custody_chain_intact()


def test_tampered_file_fails_hash_verification(client):
    h = login(client)
    cid, _ = file_complaint(client, h)
    fid = upload(client, h, cid).json()["file_id"]
    assert client.get(f"/api/victim/complaints/{cid}/evidence/{fid}/verify", headers=h).json()["intact"] is True
    blob = next(e for e in store.evidence.values() if e["file_id"] == fid)["blob_path"]
    open(blob, "ab").write(b"tampered")
    assert client.get(f"/api/victim/complaints/{cid}/evidence/{fid}/verify", headers=h).json()["intact"] is False


def test_upload_corrupted_in_transit_is_rejected(client):
    h = login(client)
    cid, _ = file_complaint(client, h)
    r = upload(client, h, cid, client_sha256="0" * 64)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "HASH_MISMATCH"


@pytest.mark.parametrize("name,data,code", [
    ("virus.exe", b"MZ" + b"\x00" * 50, "TYPE_NOT_ALLOWED"),
    ("fake.png", b"MZ" + b"\x00" * 50, "CONTENT_MISMATCH"),
    ("empty.txt", b"", "EMPTY_FILE"),
    ("evil.pdf", b"%PDF-1.4 /JavaScript (app.alert(1))", "UNSAFE_FILE"),
    ("eicar.txt", ev.EICAR, "UNSAFE_FILE"),
])
def test_unsafe_files_are_blocked(client, name, data, code):
    h = login(client)
    cid, _ = file_complaint(client, h)
    r = upload(client, h, cid, data=data, name=name)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code


def test_oversized_file_rejected(client):
    h = login(client)
    cid, _ = file_complaint(client, h)
    assert upload(client, h, cid, data=b"a" * (ev.MAX_BYTES + 1), name="big.txt").status_code == 413


def test_restricted_files_are_marked_no_preview(client):
    h = login(client)
    cid, _ = file_complaint(client, h)
    r = upload(client, h, cid, restricted="true").json()
    assert r["restricted"] is True and r["preview_allowed"] is False


def test_officer_request_answered_by_upload(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    h, officer = login(client), {"Authorization": "Bearer officer-token-123"}
    cid, _ = file_complaint(client, h)
    rid = client.post(f"/api/v1/intake/{cid}/requests", json={"text": "Please add the payment receipt"},
                      headers=officer).json()["request_id"]
    assert client.get(f"/api/victim/cases/{cid}/status", headers=h).json()["open_requests"] == 1
    upload(client, h, cid, request_id=rid)
    assert client.get(f"/api/victim/cases/{cid}/status", headers=h).json()["open_requests"] == 0


# ---- transparency + support ---------------------------------------------------------------------
def test_every_officer_access_is_logged_and_shown_to_victim(client, monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTH_STUB", "true")
    h, officer = login(client), {"Authorization": "Bearer officer-token-123"}
    cid, _ = file_complaint(client, h)
    client.get(f"/api/v1/intake/{cid}", headers=officer)
    log = client.get("/api/victim/privacy/access-log", headers=h).json()
    assert log and all(e["who"] == "An authorised investigator" for e in log)
    assert "officer-token" not in json.dumps(log)


def test_support_center_is_public_and_complete(client):
    s = client.get("/api/victim/support").json()
    assert "14416" in s["sextortion"]["mental_health_helpline"]
    for key in ("safe_handling_banner", "recovery_scam_warning", "secure_accounts", "bank_upi_steps",
                "what_happens_next", "glossary"):
        assert s[key]
    assert client.get("/api/victim/consent-notice").json()["never_share"]
