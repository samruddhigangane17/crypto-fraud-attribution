"""Find real test wallets for the live trace test (no manual Etherscan browsing).

Run from the repo root (D:\\crypto-fraud-attribution):

    python scripts/find_test_wallets.py
    python scripts/find_test_wallets.py --exchange coinbase

It looks at the most recent incoming ETH transfers to an exchange wallet and finds:
  Wallet B = a small wallet that sent ETH directly to the exchange (1 hop)
  Wallet A = a small wallet that sent ETH to wallet B BEFORE B paid the exchange (2 hops)

Then run:  python scripts/live_trace_test.py <wallet A or B> --hops 3 --full

The API key is read from .env and never printed.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

BASE_URL = "https://api.etherscan.io/v2/api"

# Same addresses as the verified exchange labels in backend/attribution/seed_data.py
EXCHANGES = {
    "binance": ("Binance Hot Wallet 14", "0x28c6c06298d514db089934071355e5743bf21d60"),
    "coinbase": ("Coinbase 10", "0x503828976d22510aad0201ac7ec88293211d23da"),
    "kraken": ("Kraken Exchange 1", "0x2910543af39aba0cd09dbb2d50200b3e800a63d2"),
}


class Etherscan:
    def __init__(self, client: httpx.Client, key: str, delay: float = 0.3):
        self.client = client
        self.key = key
        self.delay = delay
        self.calls = 0

    def txlist(self, address: str, sort: str = "asc", offset: int = 100) -> list:
        params = {
            "chainid": 1,
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": offset,
            "sort": sort,
            "apikey": self.key,
        }
        for _ in range(3):
            time.sleep(self.delay)
            self.calls += 1
            resp = self.client.get(BASE_URL, params=params)
            data = resp.json()
            if str(data.get("status")) == "1":
                return data["result"]
            text = f"{data.get('message', '')} {data.get('result', '')}"
            if "no transactions found" in text.lower():
                return []
            if "rate limit" in text.lower():
                time.sleep(1.5)
                continue
            raise RuntimeError(text.replace(self.key, "[REDACTED]")[:200])
        raise RuntimeError("Etherscan rate limit hit repeatedly. Wait a minute and retry.")


def is_eth_transfer(tx: dict) -> bool:
    return tx.get("isError") == "0" and int(tx.get("value", "0") or 0) > 0


def eth_amount(tx: dict) -> Decimal:
    return Decimal(int(tx["value"])) / Decimal(10**18)


def when(tx: dict) -> str:
    return datetime.fromtimestamp(int(tx["timeStamp"]), timezone.utc).strftime("%Y-%m-%d %H:%M")


def find(api: Etherscan, exchange: str, want: int = 3, max_b: int = 25, max_a: int = 3, max_tx: int = 100) -> list:
    ex = exchange.lower()
    recent = api.txlist(ex, sort="desc", offset=1000)
    print(f"fetched {len(recent)} recent transactions of the exchange wallet")

    senders: dict = {}
    for tx in recent:
        if tx["to"].lower() == ex and tx["from"].lower() != ex and is_eth_transfer(tx):
            senders.setdefault(tx["from"].lower(), tx)
    print(f"distinct senders of direct ETH transfers into it: {len(senders)}")

    results = []
    checked = 0
    for b, _ in senders.items():
        if checked >= max_b or len(results) >= want:
            break
        checked += 1
        b_txs = api.txlist(b)
        if len(b_txs) >= max_tx:
            continue  # busy wallet (or history truncated): skip
        b_out = [t for t in b_txs if t["from"].lower() == b and t["to"].lower() == ex and is_eth_transfer(t)]
        b_in = [t for t in b_txs if t["to"].lower() == b and t["from"].lower() != b and is_eth_transfer(t)]
        if not b_out:
            continue

        a_candidates = []
        seen = set()
        for t_in in b_in:
            a = t_in["from"].lower()
            if a in seen or a == ex:
                continue
            seen.add(a)
            later = [o for o in b_out if int(o["timeStamp"]) >= int(t_in["timeStamp"])]
            if not later:
                continue  # B paid the exchange before A paid B: tracer would not follow it
            a_txs = api.txlist(a)
            if len(a_txs) >= max_tx:
                continue
            if not any(t["from"].lower() == a and is_eth_transfer(t) for t in a_txs):
                continue
            a_candidates.append({"address": a, "tx_count": len(a_txs), "to_b": t_in, "b_to_ex": later[0]})
            if len(a_candidates) >= max_a:
                break

        results.append({"b": b, "b_tx_count": len(b_txs), "b_to_ex": b_out[0], "a": a_candidates})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Find real wallet A / wallet B test candidates")
    ap.add_argument("--exchange", choices=sorted(EXCHANGES), default="binance")
    ap.add_argument("--want", type=int, default=3, help="stop after this many wallet B candidates")
    args = ap.parse_args()

    key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    if not key or key == "your-etherscan-api-key":
        print("ETHERSCAN_API_KEY is not set. Add it to .env, e.g. ETHERSCAN_API_KEY=abc123")
        return 1

    name, address = EXCHANGES[args.exchange]
    print(f"exchange: {name} ({address})")
    api = Etherscan(httpx.Client(timeout=20.0), key)
    try:
        results = find(api, address, want=args.want)
    except Exception as err:
        print(f"ERROR: {err}")
        return 2

    if not results:
        print("\nNo suitable wallets found in the latest transfers. Run again in a few minutes, "
              "or try --exchange coinbase / --exchange kraken.")
        return 3

    print(f"\nFound {len(results)} candidate(s) using {api.calls} API calls.\n")
    for i, r in enumerate(results, 1):
        tx = r["b_to_ex"]
        print(f"[{i}] WALLET B (1 hop to {name}): {r['b']}")
        print(f"    {r['b_tx_count']} txs total; paid the exchange {eth_amount(tx)} ETH on {when(tx)}")
        print(f"    test:  python scripts/live_trace_test.py {r['b']} --hops 2 --full")
        if not r["a"]:
            print("    (no suitable wallet A found behind this one)")
        for j, a in enumerate(r["a"], 1):
            t = a["to_b"]
            print(f"    WALLET A #{j} (2 hops): {a['address']}")
            print(f"        {a['tx_count']} txs total; sent B {eth_amount(t)} ETH on {when(t)}")
            print(f"        test:  python scripts/live_trace_test.py {a['address']} --hops 3 --full")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
