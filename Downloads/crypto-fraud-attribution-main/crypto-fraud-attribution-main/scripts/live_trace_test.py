"""Step 5: live Etherscan test for the tracing pipeline.

Run from the repo root (D:\\crypto-fraud-attribution):

    python scripts/live_trace_test.py 0xWALLET_A
    python scripts/live_trace_test.py 0xWALLET_A --hops 3 --full
    python scripts/live_trace_test.py 0xmock_wallet_a --mock --full     # offline dry run

Stages:
  1. Fetch wallet history from Etherscan (connector check)
  2. Multi-hop trace, stopping at exchanges in the registry (tracer + attribution check)
  3. --full: run create -> trace -> risk -> alerts -> graph through the FastAPI app

The API key is read from .env and never printed.
"""

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

from backend.attribution.matcher import EndpointMatcher  # noqa: E402
from backend.attribution.registry import global_registry  # noqa: E402
from backend.schemas.attribution import EntityCategory  # noqa: E402
from backend.tracing.connectors.base import BaseConnector  # noqa: E402
from backend.tracing.connectors.etherscan import EtherscanConnector  # noqa: E402
from backend.tracing.connectors.mock import MockConnector  # noqa: E402
from backend.tracing.connectors.throttle import ThrottledConnector  # noqa: E402
from backend.tracing.tracer import MultiHopTracer  # noqa: E402
from backend.tracing.validation import resolve_chain_and_address  # noqa: E402


def short(addr: str) -> str:
    return addr if len(addr) <= 14 else f"{addr[:8]}...{addr[-6:]}"


def header(text: str) -> None:
    print(f"\n=== {text} ===")


def stage1(connector: BaseConnector, address: str) -> bool:
    header("Stage 1: fetch wallet history")
    txs = connector.get_transactions(address)
    print(f"transactions returned: {len(txs)}")
    if not txs:
        print("FAIL: no transactions returned. Check the address, API key, and network.")
        return False
    outgoing = [t for t in txs if t.from_address.lower() == address.lower()]
    print(f"outgoing: {len(outgoing)}  incoming: {len(txs) - len(outgoing)}")
    print(f"first: {txs[0].timestamp}  last: {txs[-1].timestamp}")
    sample = txs[0]
    print(f"sample tx: {sample.tx_hash}  {sample.amount} {sample.asset_symbol}")
    if not outgoing:
        print("WARN: wallet has no outgoing transfers, so there is nothing to trace forward.")
    return True


def stage2(connector: BaseConnector, address: str, hops: int) -> list:
    header("Stage 2: multi-hop trace")
    exchanges = {
        l.address.lower(): l.entity_name
        for l in global_registry.get_all()
        if l.chain.lower() == "ethereum" and l.entity_category == EntityCategory.EXCHANGE_VASP
    }
    print(f"exchange addresses in registry (trace stops at these): {len(exchanges)}")

    tracer = MultiHopTracer(
        connector=connector,
        max_hops=hops,
        min_taint_share=0.0,
        target_addresses=set(exchanges),
        max_paths=25,
    )
    paths = tracer.trace(address)
    print(f"paths found: {len(paths)}   addresses discovered: {len(tracer.discovered_addresses)}")
    if tracer.connector_errors:
        print(f"connector errors ({len(tracer.connector_errors)}):")
        for err in tracer.connector_errors[:5]:
            print(f"  - {err[:200]}")

    matcher = EndpointMatcher(global_registry)
    hit_exchange = False
    for i, p in enumerate(paths[:10], 1):
        match = matcher.match_address("ethereum", p.end_address, hop_distance=p.hop_count)
        label = match.label.entity_name if match.is_matched and match.label else "unknown"
        print(f"\npath {i}: {p.hop_count} hop(s), ends at {short(p.end_address)} -> {label}")
        for n, tx in enumerate(p.transactions, 1):
            print(
                f"  hop {n}: {short(tx.from_address)} -> {short(tx.to_address)}  "
                f"{tx.amount} {tx.asset_symbol}  {tx.timestamp:%Y-%m-%d %H:%M}  {tx.tx_hash}"
            )
        if match.is_matched:
            hit_exchange = True

    print()
    if not paths:
        print("RESULT: 0 paths. Wallet may have no outgoing transfers, or the API call failed.")
    elif hit_exchange:
        print("RESULT: PASS - at least one path ends at a labeled exchange.")
    else:
        print("RESULT: paths found but none end at a registry exchange. "
              "Add the exchange address to backend/attribution/seed_data.py to test attribution.")
    return paths


def stage3(address: str, hops: int) -> None:
    header("Stage 3: full API pipeline")
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)  # no 'with': does not start the monitoring scheduler

    r = client.post("/api/investigations", json={"chain": "auto", "reported_address": address})
    print(f"create: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:300])
        return
    case_id = r.json()["id"]

    r = client.post(f"/api/investigations/{case_id}/trace", json={"max_hops": hops})
    print(f"trace:  {r.status_code}  {r.json() if r.status_code == 200 else r.text[:300]}")
    if r.status_code != 200:
        return

    risk = client.get(f"/api/investigations/{case_id}/risk")
    print(f"risk:   {risk.status_code}")
    if risk.status_code == 200:
        body = risk.json()
        ra = body["risk_assessment"]
        print(f"  overall_score: {ra.get('overall_score')}  level: {ra.get('risk_level') or ra.get('level')}")
        print(f"  attribution_confidence: {body['attribution_confidence']}")

    alerts = client.get(f"/api/investigations/{case_id}/alerts")
    print(f"alerts: {alerts.status_code}  count: {len(alerts.json()) if alerts.status_code == 200 else '-'}")

    graph = client.get(f"/api/investigations/{case_id}/graph")
    if graph.status_code == 200:
        g = graph.json()
        nodes = g.get("nodes", [])
        edges = g.get("edges", [])
        types = sorted({n["data"].get("type") for n in nodes})
        print(f"graph:  {len(nodes)} nodes, {len(edges)} edges, node types: {types}")
    else:
        print(f"graph:  {graph.status_code} {graph.text[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Live Etherscan trace test")
    ap.add_argument("address", help="Reported wallet (Wallet A)")
    ap.add_argument("--hops", type=int, default=4)
    ap.add_argument("--full", action="store_true", help="Also run the full API pipeline")
    ap.add_argument("--mock", action="store_true", help="Offline dry run with mock data")
    args = ap.parse_args()

    try:
        _, address = resolve_chain_and_address("ethereum", args.address)
    except ValueError as err:
        print(f"Invalid address: {err}")
        return 1

    if args.mock:
        connector: BaseConnector = MockConnector()
        print("MODE: mock data (no network)")
    else:
        key = os.getenv("ETHERSCAN_API_KEY", "").strip()
        if not key or key == "your-etherscan-api-key":
            print("ETHERSCAN_API_KEY is not set. Add it to .env, e.g. ETHERSCAN_API_KEY=abc123")
            return 1
        connector = ThrottledConnector(EtherscanConnector(api_key=key))
        print(f"MODE: live Etherscan (key loaded, {len(key)} chars)")

    if not stage1(connector, address):
        return 2
    stage2(connector, address, args.hops)
    if args.full:
        stage3(address, args.hops)
    return 0


if __name__ == "__main__":
    sys.exit(main())
