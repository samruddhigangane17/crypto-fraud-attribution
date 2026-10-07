"""TRON (TRX) Connector.

Section 8.1 / Feature 2 / TC-01:
Retrieves TRON native TRX and TRC-20 token (USDT-TRON) transactions
for TRON Base58 addresses (T...) using TronGrid / TronScan REST endpoints.
Normalizes transactions into unified NormalizedTransaction edges.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector

logger = logging.getLogger("crypto_attribution.connectors.tron")

# 1 TRX = 1,000,000 SUN
SUN = Decimal("1000000")
# USDT on TRON has 6 decimals
USDT_DECIMALS = Decimal("1000000")


class TronConnector(BaseConnector):
    """Connector for querying TRON blockchain transactions and TRC-20 transfers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
    ):
        self.api_key = (api_key or os.getenv("TRON_API_KEY", "")).strip()
        self.base_url = base_url or os.getenv("TRONGRID_BASE_URL", "https://api.trongrid.io")
        self.timeout = timeout
        self._external_client = client

    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        include_token_transfers: bool = True,
    ) -> List[NormalizedTransaction]:
        """Fetch TRX native and TRC-20 token transfers for a TRON address."""
        clean_addr = address.strip()
        headers = {}
        if self.api_key:
            headers["TRON-PRO-API-KEY"] = self.api_key

        normalized: List[NormalizedTransaction] = []

        # 1. Fetch TRC-20 transfers (USDT on TRON is dominant in fraud)
        if include_token_transfers:
            trc20_url = f"{self.base_url.rstrip('/')}/v1/accounts/{clean_addr}/transactions/trc20?limit=50"
            try:
                if self._external_client:
                    resp = self._external_client.get(trc20_url, headers=headers, timeout=self.timeout)
                else:
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.get(trc20_url, headers=headers)

                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for item in data:
                        tx_id = item.get("transaction_id", "")
                        frm = item.get("from", "")
                        to = item.get("to", "")
                        val_raw = Decimal(str(item.get("value", 0)))
                        token_info = item.get("token_info", {})
                        sym = token_info.get("symbol", "USDT")
                        dec = Decimal(str(10 ** token_info.get("decimals", 6)))
                        val = val_raw / dec
                        block_ts = item.get("block_timestamp", 0) / 1000.0

                        ts = (
                            datetime.fromtimestamp(block_ts, tz=timezone.utc)
                            if block_ts > 0
                            else datetime.now(timezone.utc)
                        )

                        normalized.append(
                            NormalizedTransaction(
                                chain="tron",
                                tx_hash=tx_id,
                                from_address=frm,
                                to_address=to,
                                amount=val,
                                asset_symbol=sym,
                                contract_address=token_info.get("address"),
                                timestamp=ts,
                                source="trongrid",
                            )
                        )
            except Exception as e:
                logger.warning(f"TronGrid TRC-20 query failed for {clean_addr}: {e}")

        # 2. Fetch Native TRX transfers
        native_url = f"{self.base_url.rstrip('/')}/v1/accounts/{clean_addr}/transactions?limit=50"
        try:
            if self._external_client:
                resp = self._external_client.get(native_url, headers=headers, timeout=self.timeout)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(native_url, headers=headers)

            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    tx_id = item.get("txID", "")
                    raw_data = item.get("raw_data", {})
                    contract_list = raw_data.get("contract", [])
                    block_ts = raw_data.get("timestamp", 0) / 1000.0
                    ts = (
                        datetime.fromtimestamp(block_ts, tz=timezone.utc)
                        if block_ts > 0
                        else datetime.now(timezone.utc)
                    )

                    for c in contract_list:
                        c_type = c.get("type")
                        if c_type == "TransferContract":
                            param = c.get("parameter", {}).get("value", {})
                            owner = param.get("owner_address", "")
                            to_addr = param.get("to_address", "")
                            amt_sun = Decimal(str(param.get("amount", 0)))
                            val_trx = amt_sun / SUN

                            if val_trx > Decimal("0"):
                                normalized.append(
                                    NormalizedTransaction(
                                        chain="tron",
                                        tx_hash=tx_id,
                                        from_address=owner,
                                        to_address=to_addr,
                                        amount=val_trx,
                                        asset_symbol="TRX",
                                        timestamp=ts,
                                        source="trongrid",
                                    )
                                )
        except Exception as e:
            logger.warning(f"TronGrid native query failed for {clean_addr}: {e}")

        return normalized
