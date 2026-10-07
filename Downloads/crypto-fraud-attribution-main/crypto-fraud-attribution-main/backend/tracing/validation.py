"""Address validation and chain auto-detection for new investigations."""

import os
import re
from typing import Optional

SUPPORTED_CHAINS = ("bitcoin", "ethereum", "tron", "bsc")

_CHAIN_ALIASES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "trx": "tron",
    "bnb": "bsc",
    "binance-smart-chain": "bsc",
}

_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_BTC_RE = re.compile(r"^(bc1[ac-hj-np-z02-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")


def demo_enabled() -> bool:
    return os.getenv("ENABLE_DEMO_CASES", "true").lower() in ("true", "1", "yes")


def is_demo_address(address: str) -> bool:
    return demo_enabled() and address.lower().startswith("0xmock_")


def normalize_chain(chain: str) -> str:
    c = (chain or "").strip().lower()
    return _CHAIN_ALIASES.get(c, c)


def detect_chain(address: str) -> Optional[str]:
    """Best-effort chain detection. A 0x address could be ETH or BSC; ETH is assumed."""
    a = address.strip()
    if is_demo_address(a) or _EVM_RE.match(a):
        return "ethereum"
    if _TRON_RE.match(a):
        return "tron"
    if _BTC_RE.match(a):
        return "bitcoin"
    return None


def is_valid_address(chain: str, address: str) -> bool:
    a = address.strip()
    if is_demo_address(a):
        return True
    if chain in ("ethereum", "bsc"):
        return bool(_EVM_RE.match(a))
    if chain == "tron":
        return bool(_TRON_RE.match(a))
    if chain == "bitcoin":
        return bool(_BTC_RE.match(a))
    return False


def resolve_chain_and_address(chain: str, address: str) -> tuple[str, str]:
    """Return (chain, address) or raise ValueError with a clear message."""
    address = (address or "").strip()
    if not address:
        raise ValueError("Wallet address is required.")
    c = normalize_chain(chain)
    if c == "auto":
        detected = detect_chain(address)
        if detected is None:
            raise ValueError("Could not detect the chain from this address. Check it or pick a chain.")
        c = detected
    if c not in SUPPORTED_CHAINS:
        raise ValueError(f"Unsupported chain '{chain}'. Supported: {', '.join(SUPPORTED_CHAINS)}, or 'auto'.")
    if not is_valid_address(c, address):
        raise ValueError(f"'{address}' is not a valid {c} address.")
    return c, address
