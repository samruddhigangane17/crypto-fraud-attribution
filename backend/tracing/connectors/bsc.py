"""Binance Smart Chain (BSC) Connector.

Section 8.1 / Feature 2 / TC-01:
Retrieves BEP-20 and native BNB transactions for BSC addresses (0x...)
using Etherscan API V2 (chain_id=56) or BscScan API.
Normalizes all transfers into unified NormalizedTransaction records.
"""

from decimal import Decimal
import os
from typing import Any, Dict, List, Optional
import httpx

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.etherscan import EtherscanConnector, RequestPacer
from backend.tracing.normalizer import EthereumNormalizer


class BscConnector(BaseConnector):
    """Connector for querying Binance Smart Chain (BSC) via Etherscan V2 / BscScan."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[httpx.Client] = None,
        pacer: Optional[RequestPacer] = None,
    ):
        # Prefer BSCSCAN_API_KEY, fallback to ETHERSCAN_API_KEY
        key = (api_key or os.getenv("BSCSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY", "")).strip()
        url = base_url or os.getenv("BSCSCAN_BASE_URL", "https://api.etherscan.io/v2/api")

        self.api_key = key
        # Under Etherscan V2, chainid=56 is Binance Smart Chain
        self.underlying = EtherscanConnector(
            api_key=key,
            base_url=url,
            chain_id=56,
            client=client,
            pacer=pacer,
        )
        self.normalizer = EthereumNormalizer()

    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        include_token_transfers: bool = True,
    ) -> List[NormalizedTransaction]:
        """Fetch transactions from BSC and normalize with chain='bsc'."""
        txs = self.underlying.get_transactions(
            address=address,
            start_block=start_block,
            end_block=end_block,
            include_token_transfers=include_token_transfers,
        )
        # Ensure chain field is explicitly 'bsc' and native asset is 'BNB'
        for tx in txs:
            tx.chain = "bsc"
            if tx.asset_symbol == "ETH":
                tx.asset_symbol = "BNB"
        return txs
