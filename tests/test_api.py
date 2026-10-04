from fastapi.testclient import TestClient
import pytest

from backend.main import app
try:
    import api.investigations as api_inv
except ModuleNotFoundError:
    api_inv = None
import backend.api.investigations as backend_api_inv
from backend.tracing.connectors.base import BaseConnector


def _set_connector(connector):
    if api_inv is not None:
        api_inv.set_test_connector(connector)
    backend_api_inv.set_test_connector(connector)



@pytest.fixture(autouse=True)
def reset_test_connector():
    """Ensure test connector is reset after each test."""
    yield
    _set_connector(None)



def test_create_investigation():
    client = TestClient(app)
    payload = {
        "chain": "ethereum",
        "reported_address": "0xmock_wallet_a",
    }
    resp = client.post("/api/investigations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["chain"] == "ethereum"
    assert data["reported_address"] == "0xmock_wallet_a"
    assert data["status"] == "Reported"


def test_get_investigation():
    client = TestClient(app)
    # Create first
    resp_create = client.post(
        "/api/investigations",
        json={"chain": "ethereum", "reported_address": "0xmock_wallet_a"},
    )
    case_id = resp_create.json()["id"]

    # Retrieve existing
    resp_get = client.get(f"/api/investigations/{case_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == case_id
    assert resp_get.json()["reported_address"] == "0xmock_wallet_a"

    # Retrieve non-existent
    resp_404 = client.get("/api/investigations/00000000-0000-0000-0000-000000000000")
    assert resp_404.status_code == 404
    assert "not found" in resp_404.json()["detail"].lower()


def test_trace_and_get_graph_end_to_end():
    client = TestClient(app)
    # 1. Create case with mock wallet
    resp_create = client.post(
        "/api/investigations",
        json={"chain": "ethereum", "reported_address": "0xmock_wallet_a"},
    )
    case_id = resp_create.json()["id"]

    # 2. Before trace, graph should return 400
    resp_pre = client.get(f"/api/investigations/{case_id}/graph")
    assert resp_pre.status_code == 400
    assert "not been executed" in resp_pre.json()["detail"]

    # 3. Start trace
    resp_trace = client.post(
        f"/api/investigations/{case_id}/trace",
        json={"max_hops": 5, "min_taint_share": 0.05},
    )
    assert resp_trace.status_code == 200
    trace_data = resp_trace.json()
    assert trace_data["message"] == "Tracing started"
    assert "job_id" in trace_data
    assert trace_data["status"] == "completed"
    assert trace_data["paths_count"] == 3
    assert trace_data["intermediate_addresses"] == [
        "0xmock_wallet_b",
        "0xmock_wallet_c",
        "0xmock_wallet_d",
        "0xmock_wallet_e",
    ]

    # 4. Fetch computed graph
    resp_graph = client.get(f"/api/investigations/{case_id}/graph")
    assert resp_graph.status_code == 200
    graph_data = resp_graph.json()
    assert "nodes" in graph_data and "edges" in graph_data
    # 8 nodes and 7 edges from mock dataset
    assert len(graph_data["nodes"]) == 8
    assert len(graph_data["edges"]) == 7

    # Verify root node is classified as victim and exchange node as exchange
    nodes_by_id = {n["data"]["id"]: n["data"] for n in graph_data["nodes"]}
    assert nodes_by_id["0xmock_wallet_a"]["type"] == "victim"
    assert nodes_by_id["0xmock_exchange_hot"]["type"] == "exchange"
    assert nodes_by_id["0xmock_wallet_b"]["type"] == "intermediary"


def test_trace_max_hops_1_api():
    client = TestClient(app)
    resp_create = client.post(
        "/api/investigations",
        json={"chain": "ethereum", "reported_address": "0xmock_wallet_a"},
    )
    case_id = resp_create.json()["id"]

    # Trace with max_hops=1
    resp_trace = client.post(
        f"/api/investigations/{case_id}/trace",
        json={"max_hops": 1},
    )
    assert resp_trace.status_code == 200
    trace_data = resp_trace.json()
    assert trace_data["status"] == "completed"
    # Exactly 2 immediate outgoing paths from root A (A->B, A->E)
    assert trace_data["paths_count"] == 2
    # 1-hop paths have at most 1 edge and no intermediate addresses
    assert trace_data["intermediate_addresses"] == []

    # Verify graph contains only 1-hop edges (max 1 edge per path)
    resp_graph = client.get(f"/api/investigations/{case_id}/graph")
    assert resp_graph.status_code == 200
    graph_data = resp_graph.json()
    # 3 nodes: root A, recipient B, recipient E
    assert len(graph_data["nodes"]) == 3
    # Exactly 2 outgoing edges from root A
    assert len(graph_data["edges"]) == 2
    for edge in graph_data["edges"]:
        assert edge["data"]["source"] == "0xmock_wallet_a"
        assert edge["data"]["target"] in {"0xmock_wallet_b", "0xmock_wallet_e"}

    # Also verify GET /api/investigations/{id} returns the empty intermediate_addresses list
    resp_case = client.get(f"/api/investigations/{case_id}")
    assert resp_case.status_code == 200
    assert resp_case.json()["intermediate_addresses"] == []



def test_get_graph_unknown_case_returns_404():
    client = TestClient(app)
    resp = client.get("/api/investigations/non-existent-case/graph")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_start_trace_unknown_case_returns_404():
    client = TestClient(app)
    resp = client.post(
        "/api/investigations/non-existent-case/trace",
        json={"max_hops": 5},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_start_trace_connector_error_returns_502():
    class FailingConnector(BaseConnector):
        def get_transactions(self, address, start_block=None, end_block=None):
            raise ConnectionError("Simulated remote provider failure")

    _set_connector(FailingConnector())
    client = TestClient(app)

    resp_create = client.post(
        "/api/investigations",
        json={"chain": "ethereum", "reported_address": "0xmock_wallet_a"},
    )
    case_id = resp_create.json()["id"]

    resp_trace = client.post(
        f"/api/investigations/{case_id}/trace",
        json={"max_hops": 5},
    )
    assert resp_trace.status_code == 502
    assert "provider failed" in resp_trace.json()["detail"].lower()


def test_member2_routes_remain_intact():
    client = TestClient(app)
    auth = {"Authorization": "Bearer dev-token-12345"}
    case_id = "DEMO-TEST"  # only DEMO- ids return demo data

    r_risk = client.get(f"/api/investigations/{case_id}/risk")
    assert r_risk.status_code == 200
    assert "risk_assessment" in r_risk.json()

    r_alerts = client.get(f"/api/investigations/{case_id}/alerts")
    assert r_alerts.status_code == 200
    assert isinstance(r_alerts.json(), list)

    r_rep_post = client.post(f"/api/investigations/{case_id}/report", headers=auth)
    assert r_rep_post.status_code == 201
    r_rep_get = client.get(f"/api/investigations/{case_id}/report", headers=auth)
    assert r_rep_get.status_code == 200


def test_unknown_case_risk_is_404_not_fake_data():
    client = TestClient(app)
    assert client.get("/api/investigations/does-not-exist/risk").status_code == 404
