"""Input validation, honest data-source handling, and taint-share pruning."""

from fastapi.testclient import TestClient

from backend.api import investigations as inv
from backend.main import app
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.tracer import MultiHopTracer
from backend.tracing.validation import detect_chain, resolve_chain_and_address

client = TestClient(app)

ETH = "0x28c6c06298d514db089934071355e5743bf21d60"
TRON = "TNUC9Qb1rRpS5CbWLmNMxXBjyFoydXjWFR"
BTC = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"


def setup_function():
    inv.set_test_connector(None)


def test_detect_chain():
    assert detect_chain(ETH) == "ethereum"
    assert detect_chain(TRON) == "tron"
    assert detect_chain(BTC) == "bitcoin"
    assert detect_chain("not-an-address") is None


def test_resolve_auto_and_aliases():
    assert resolve_chain_and_address("auto", TRON)[0] == "tron"
    assert resolve_chain_and_address("ETH", ETH)[0] == "ethereum"
    assert resolve_chain_and_address("bsc", ETH)[0] == "bsc"


def test_invalid_address_rejected():
    r = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": "not-an-address"})
    assert r.status_code == 422
    assert "valid ethereum address" in r.json()["detail"]


def test_wrong_chain_for_address_rejected():
    r = client.post("/api/investigations", json={"chain": "tron", "reported_address": ETH})
    assert r.status_code == 422


def test_unsupported_chain_rejected():
    r = client.post("/api/investigations", json={"chain": "dogecoin", "reported_address": "x"})
    assert r.status_code == 422
    assert "Unsupported chain" in r.json()["detail"]


def test_auto_chain_creates_case():
    r = client.post("/api/investigations", json={"chain": "auto", "reported_address": TRON})
    assert r.status_code == 200
    assert r.json()["chain"] == "tron"


def test_real_address_without_api_key_is_503_not_silent_mock(monkeypatch):
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    case_id = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": ETH}).json()["id"]
    r = client.post(f"/api/investigations/{case_id}/trace", json={})
    assert r.status_code == 503
    assert "ETHERSCAN_API_KEY" in r.json()["detail"]


def test_non_ethereum_trace_is_501():
    case_id = client.post("/api/investigations", json={"chain": "tron", "reported_address": TRON}).json()["id"]
    r = client.post(f"/api/investigations/{case_id}/trace", json={})
    assert r.status_code == 501


def test_demo_trace_reports_mock_data_source():
    case_id = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": "0xmock_wallet_a"}).json()["id"]
    r = client.post(f"/api/investigations/{case_id}/trace", json={})
    assert r.status_code == 200
    assert r.json()["data_source"] == "mock"
    assert client.get(f"/api/investigations/{case_id}").json()["data_source"] == "mock"


def test_taint_share_out_of_range_rejected():
    case_id = client.post("/api/investigations", json={"chain": "ethereum", "reported_address": "0xmock_wallet_a"}).json()["id"]
    r = client.post(f"/api/investigations/{case_id}/trace", json={"min_taint_share": 2})
    assert r.status_code == 422


def test_min_taint_share_prunes_weak_branches():
    # mock graph: A->B 10.0, B->G 0.5 (5% of the first transfer), A->E 2.5 -> F 2.4
    no_prune = MultiHopTracer(MockConnector(), max_hops=5, min_taint_share=0.0)
    paths_all = no_prune.trace("0xmock_wallet_a")
    assert any(p.end_address == "0xmock_wallet_g" for p in paths_all)

    pruned = MultiHopTracer(MockConnector(), max_hops=5, min_taint_share=0.10)
    paths = pruned.trace("0xmock_wallet_a")
    assert not any(p.end_address == "0xmock_wallet_g" for p in paths)
    assert pruned.pruned_low_taint >= 1
    # the main path to the exchange survives (97% of the first transfer)
    assert any(p.end_address == "0xmock_exchange_hot" for p in paths)


def test_default_tracer_has_no_pruning():
    t = MultiHopTracer(MockConnector(), max_hops=5)
    t.trace("0xmock_wallet_a")
    assert t.pruned_low_taint == 0
