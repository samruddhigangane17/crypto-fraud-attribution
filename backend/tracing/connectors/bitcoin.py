"""Bitcoin (BTC) UTXO Connector.

Section 8.1 / Feature 2 / TC-01:
Retrieves Bitcoin UTXO transactions for addresses (1..., 3..., bc1...)
using open Esplora/Mempool REST endpoints (or configured node API).
Normalizes multi-input, multi-output UTXO transactions into unified NormalizedTransaction edges.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector

logger = logging.getLogger("crypto_attribution.connectors.bitcoin")

# 1 BTC = 100,000,000 Satoshis
SATOSHI = Decimal("100000000")


class BitcoinConnector(BaseConnector):
    """Connector for querying Bitcoin UTXO transactions."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url or os.getenv("BITCOIN_EXPLORER_URL", "https://mempool.space/api")
        self.timeout = timeout
        self._external_client = client

    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        include_token_transfers: bool = False,
    ) -> List[NormalizedTransaction]:
        """Fetch transactions for a Bitcoin address and normalize into transfer records."""
        clean_addr = address.strip()
        url = f"{self.base_url.rstrip('/')}/address/{clean_addr}/txs"

        txs_data: List[Dict[str, Any]] = []
        try:
            if self._external_client:
                resp = self._external_client.get(url, timeout=self.timeout)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url)

            if resp.status_code == 200:
                txs_data = resp.json()
            else:
                logger.warning(f"Bitcoin API returned status {resp.status_code} for {clean_addr}")
        except Exception as e:
            logger.warning(f"Bitcoin network query failed for {clean_addr}: {e}")
            return []

        normalized: List[NormalizedTransaction] = []
        for raw_tx in txs_data:
            tx_hash = raw_tx.get("txid", "")
            status = raw_tx.get("status", {})
            block_height = status.get("block_height")
            block_time_unix = status.get("block_time") or 0

            ts = (
                datetime.fromtimestamp(block_time_unix, tz=timezone.utc)
                if block_time_unix > 0
                else datetime.now(timezone.utc)
            )

            # Extract inputs (senders) and outputs (recipients)
            inputs = raw_tx.get("vin", [])
            outputs = raw_tx.get("vout", [])

            input_addrs = [
                inp.get("prevout", {}).get("scriptpubkey_address")
                for inp in inputs
                if inp.get("prevout", {}).get("scriptpubkey_address")
            ]

            # Primary sender (or first input)
            sender = input_addrs[0] if input_addrs else clean_addr

            # Case A: Queried address was a sender -> track all outgoing recipient outputs
            if clean_addr in input_addrs:
                for out in outputs:
                    recip = out.get("scriptpubkey_address")
                    val_sats = Decimal(str(out.get("value", 0)))
                    val_btc = val_sats / SATOSHI

                    # Skip change output going back to sender unless alone
                    if recip and recip != clean_addr and val_btc > Decimal("0"):
                        normalized.append(
                            NormalizedTransaction(
                                chain="bitcoin",
                                tx_hash=tx_hash,
                                from_address=clean_addr,
                                to_address=recip,
                                amount=val_btc,
                                asset_symbol="BTC",
                                timestamp=ts,
                                block_number=block_height,
                                source="mempool.space",
                            )
                        )
            else:
                # Case B: Queried address was a recipient -> track inbound transfer
                for out in outputs:
                    recip = out.get("scriptpubkey_address")
                    if recip == clean_addr:
                        val_sats = Decimal(str(out.get("value", 0)))
                        val_btc = val_sats / SATOSHI
                        if val_btc > Decimal("0"):
                            normalized.append(
                                NormalizedTransaction(
                                chain="bitcoin",
                                tx_hash=tx_hash,
                                from_address=sender,
                                to_address=clean_addr,
                                amount=val_btc,
                                asset_symbol="BTC",
                                timestamp=ts,
                                block_number=block_height,
                                source="mempool.space",
                            )
                        )

        return normalized
