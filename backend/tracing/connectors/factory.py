"""Chain -> connector selection shared by the API and the monitoring worker."""

import os

from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.etherscan import EtherscanConnector
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.throttle import ThrottledConnector
from backend.tracing.validation import is_demo_address


class ConnectorUnavailableError(Exception):
    """No usable live data source for this chain/configuration."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason  # "unsupported_chain" | "missing_api_key"


def build_connector(chain: str, address: str) -> BaseConnector:
    """Pick the connector. Never silently falls back to mock data for a real address."""
    if is_demo_address(address):
        return MockConnector()

    if chain != "ethereum":
        raise ConnectorUnavailableError(
            f"No live data connector for '{chain}' yet. Only Ethereum is implemented.",
            "unsupported_chain",
        )

    api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    if not api_key:
        raise ConnectorUnavailableError(
            "ETHERSCAN_API_KEY is not set on the server. Set it in .env, or use a 0xmock_ demo address.",
            "missing_api_key",
        )
    # Request-level pacing lives in EtherscanConnector; the wrapper spaces whole address lookups.
    return ThrottledConnector(EtherscanConnector(api_key=api_key))
