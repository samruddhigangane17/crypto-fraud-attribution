"""Regression tests for the handoff list, part A (A1-A7)."""

from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.api.investigations as inv
from backend.api.routes import _get_or_404
from backend.database.case_store import CaseStore
from backend.database.supabase_client import SupabaseClient
from backend.main import app
from backend.monitoring.provider import ConnectorTransactionProvider
from backend.monitoring.service import MonitoringService
from backend.schemas.monitoring import MonitoringConfig
from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.etherscan import EtherscanConnector, RequestPacer
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.tracer import MultiHopTracer

A, B, C = "0x" + "a" * 40, "0x" + "b" * 40, "0x" + "c" * 40
AUTH = {"Authorization": "Bearer dev-token-12345"}
client = TestClient(app)


def tx(h, frm, to, amount, asset="ETH", contract=None, minute=0, block=1):
    return NormalizedTransaction(
        chain="ethereum", tx_hash=h, from_address=frm, to_address=to, amount=Decimal(amount),
        asset_symbol=asset, contract_address=contract,
        timestamp=datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc), block_number=block,
    )


@pytest.fixture(autouse=True)
def _reset():
    inv.set_test_connector(None)
    inv._INVESTIGATIONS.clear()
    yield
    inv.set_test_connector(None)
    inv._INVESTIGATIONS.clear()


# ---- A2: zero paths gives a clear notice ----------------------------------------------
def test_zero_paths_returns_notice():
    inv.set_test_connector(MockConnector([]))
    cid = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": A}).json()["id"]
    body = client.post(f"/api/investigations/{cid}/trace", json={"max_hops": 3}).json()
    assert body["paths_count"] == 0
    assert "No outgoing transfers" in body["notice"]
    assert client.get(f"/api/investigations/{cid}").json()["notice"] == body["notice"]


# ---- A3: ERC-20 requested, and flows stay within one asset ----------------------------
class TokenAwareConnector(BaseConnector):
    def __init__(self, txs):
        self.txs, self.asked_for_tokens = txs, []

    def get_transactions(self, address, start_block=None, end_block=None, include_token_transfers=False):
        self.asked_for_tokens.append(include_token_transfers)
        return [t for t in self.txs if address.lower() in (t.from_address.lower(), t.to_address.lower())]


def test_tracer_requests_token_transfers_and_follows_usdt():
    usdt = "0x" + "d" * 40
    conn = TokenAwareConnector([tx("0x1", A, B, "1000", "USDT", usdt, 1), tx("0x2", B, C, "900", "USDT", usdt, 2)])
    paths = MultiHopTracer(connector=conn, max_hops=3, investigation_id="t").trace(A)
    assert all(conn.asked_for_tokens)
    assert [p.hop_count for p in paths] == [2]


def test_path_does_not_jump_between_assets():
    usdt = "0x" + "d" * 40
    conn = TokenAwareConnector([tx("0x1", A, B, "1", "ETH", None, 1), tx("0x2", B, C, "5000", "USDT", usdt, 2)])
    paths = MultiHopTracer(connector=conn, max_hops=3, investigation_id="t").trace(A)
    assert [p.hop_count for p in paths] == [1]  # the USDT transfer is a different flow


# ---- A4: pacing and backoff -----------------------------------------------------------
def test_pacer_spaces_requests(monkeypatch):
    sleeps = []
    monkeypatch.setattr("backend.tracing.connectors.etherscan.time.sleep", sleeps.append)
    pacer = RequestPacer(0.25)
    for _ in range(3):
        pacer.wait()
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0] >= 0


def test_retry_delay_default_is_not_tiny(monkeypatch):
    monkeypatch.delenv("ETHERSCAN_RETRY_DELAY", raising=False)
    assert EtherscanConnector(api_key="k").retry_delay >= 1.0


# ---- A5: monitoring sees new activity -------------------------------------------------
def test_monitoring_provider_feeds_new_transactions_and_skips_old_history():
    old = tx("0xold", A, B, "1", minute=0, block=1)
    conn = TokenAwareConnector([old])
    provider = ConnectorTransactionProvider(lambda chain, addr: conn)
    service = MonitoringService()
    cfg = MonitoringConfig(investigation_id="m1", chain="ethereum", watched_addresses=[A],
                           started_at="2026-01-01T00:30:00+00:00")
    service.register_case(cfg)
    assert service.poll_all_active(provider) == {}  # history before monitoring started is ignored

    conn.txs.append(NormalizedTransaction(
        chain="ethereum", tx_hash="0xnew", from_address=A, to_address=C, amount=Decimal("2"), asset_symbol="ETH",
        timestamp=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), block_number=2))
    alerts = service.poll_all_active(provider)
    assert alerts and any(a.tx_hash == "0xnew" for a in alerts["m1"])
    assert service.poll_all_active(provider) == {}  # nothing new, and no duplicate alerts


# ---- A6: write-through persistence and reload -----------------------------------------
class FakeSupabase(SupabaseClient):
    def __init__(self):
        super().__init__(base_url="https://x.supabase.co", api_key="k")
        self.tables = {}

    def upsert_sync(self, table, records, on_conflict="id"):
        for r in (records if isinstance(records, list) else [records]):
            rows = self.tables.setdefault(table, [])
            rows[:] = [x for x in rows if x.get(on_conflict) != r.get(on_conflict)] + [r]
        return True

    def insert_sync(self, table, records):
        self.tables.setdefault(table, []).extend(records if isinstance(records, list) else [records])
        return True

    def delete_sync(self, table, filters):
        (col, val), = filters.items()
        self.tables[table] = [r for r in self.tables.get(table, []) if f"eq.{r.get(col)}" != val]
        return True

    def select_sync(self, table, filters):
        (col, val), = filters.items()
        return [r for r in self.tables.get(table, []) if f"eq.{r.get(col)}" == val]


def test_case_survives_restart_via_supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(inv, "_store", CaseStore(inv._INVESTIGATIONS, fake))
    from backend.database.repository import global_repository
    monkeypatch.setattr(global_repository, "supabase", fake)

    inv.set_test_connector(MockConnector([tx("0x1", A, B, "1", minute=1), tx("0x2", B, C, "1", minute=2)]))
    cid = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": A}).json()["id"]
    body = client.post(f"/api/investigations/{cid}/trace", json={"max_hops": 3}).json()
    assert body["persisted"] is True
    assert fake.tables["trace_paths"] and fake.tables["investigations"][0]["graph_data"]

    # "restart": wipe all in-memory state
    inv._INVESTIGATIONS.clear()
    global_repository._investigations.clear()
    assert client.get(f"/api/investigations/{cid}/graph").json()["nodes"]
    assert client.get(f"/api/investigations/{cid}/risk").status_code == 200
    assert client.get(f"/api/investigations/{cid}/alerts").status_code == 200


# ---- A1: untraced case is 409 (explains itself), unknown is 404 ------------------------
def test_untraced_case_is_409_not_404():
    cid = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": A}).json()["id"]
    r = client.get(f"/api/investigations/{cid}/risk")
    assert r.status_code == 409 and "no completed trace" in r.json()["detail"]
    assert client.get("/api/investigations/does-not-exist/risk").status_code == 404


# ---- A7: auth fails closed; JWT audience enforced --------------------------------------
def test_auth_fails_closed_without_secret_or_explicit_stub(monkeypatch):
    monkeypatch.delenv("ALLOW_DEV_AUTH_STUB", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    assert client.post("/api/investigations/x/monitor", headers=AUTH,
                       json={"investigation_id": "x", "chain": "ethereum", "watched_addresses": [A]}).status_code == 503


def test_jwt_signature_and_audience_checked(monkeypatch):
    import jwt as pyjwt
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "s" * 40)
    body = {"investigation_id": "x", "chain": "ethereum", "watched_addresses": [A]}
    good = pyjwt.encode({"sub": "u1", "aud": "authenticated"}, "s" * 40, algorithm="HS256")
    wrong_aud = pyjwt.encode({"sub": "u1", "aud": "other"}, "s" * 40, algorithm="HS256")
    forged = pyjwt.encode({"sub": "u1", "aud": "authenticated"}, "z" * 40, algorithm="HS256")
    url = "/api/investigations/x/monitor"
    assert client.post(url, headers={"Authorization": f"Bearer {good}"}, json=body).status_code == 200
    assert client.post(url, headers={"Authorization": f"Bearer {wrong_aud}"}, json=body).status_code == 403
    assert client.post(url, headers={"Authorization": f"Bearer {forged}"}, json=body).status_code == 403
    assert client.post(url, headers=AUTH, json=body).status_code == 403  # stub token no longer works with a secret set
