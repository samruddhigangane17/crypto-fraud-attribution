"""Chain -> connector selection shared by the API and the monitoring worker."""

import os

from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.bitcoin import BitcoinConnector
from backend.tracing.connectors.bsc import BscConnector
from backend.tracing.connectors.etherscan import EtherscanConnector
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.throttle import ThrottledConnector
from backend.tracing.connectors.tron import TronConnector
from backend.tracing.validation import is_demo_address


class ConnectorUnavailableError(Exception):
    """No usable live data source for this chain/configuration."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason  # "unsupported_chain" | "missing_api_key"


def build_connector(chain: str, address: str) -> BaseConnector:
    """Pick the connector for ETH, BSC, BTC, or TRON. Never silently falls back to mock data for a real address."""
    c = chain.strip().lower()

    if is_demo_address(address):
        return MockConnector()

    if c == "ethereum":
        api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()
        if not api_key:
            raise ConnectorUnavailableError(
                "ETHERSCAN_API_KEY is not set on the server. Set it in .env, or use a 0xmock_ demo address.",
                "missing_api_key",
            )
        return ThrottledConnector(EtherscanConnector(api_key=api_key))

    if c == "bsc":
        api_key = (os.getenv("BSCSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY", "")).strip()
        return ThrottledConnector(BscConnector(api_key=api_key))

    if c == "bitcoin":
        return ThrottledConnector(BitcoinConnector())

    if c == "tron":
        api_key = os.getenv("TRON_API_KEY", "").strip()
        return ThrottledConnector(TronConnector(api_key=api_key))

    raise ConnectorUnavailableError(
        f"Unsupported chain '{chain}'. Supported chains: ethereum, bsc, bitcoin, tron.",
        "unsupported_chain",
    )
