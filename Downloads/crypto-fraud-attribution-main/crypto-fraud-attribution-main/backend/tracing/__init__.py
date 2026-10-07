"""Blockchain tracing and graph analysis module (Member 1)."""

from backend.tracing.analysis import WalletMetrics, WalletRelationshipAnalyzer
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.etherscan import (
    EtherscanAPIError,
    EtherscanConnector,
    EtherscanConnectorError,
    EtherscanHTTPError,
    EtherscanRateLimitError,
    EtherscanTimeoutError,
)
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.graph import FlowGraphBuilder, build_transaction_graph, truncate_address
from backend.tracing.normalizer import (
    EthereumNormalizer,
    NormalizationError,
    is_valid_eth_address,
    parse_token_amount,
    parse_unix_timestamp,
    parse_wei_to_eth,
)
from backend.tracing.tracer import MultiHopTracer, TracingError

__all__ = [
    "BaseConnector",
    "MockConnector",
    "EtherscanConnector",
    "EtherscanConnectorError",
    "EtherscanRateLimitError",
    "EtherscanAPIError",
    "EtherscanHTTPError",
    "EtherscanTimeoutError",
    "FlowGraphBuilder",
    "build_transaction_graph",
    "truncate_address",
    "EthereumNormalizer",
    "NormalizationError",
    "is_valid_eth_address",
    "parse_wei_to_eth",
    "parse_token_amount",
    "parse_unix_timestamp",
    "MultiHopTracer",
    "TracingError",
    "WalletMetrics",
    "WalletRelationshipAnalyzer",
]
