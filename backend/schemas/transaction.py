"""Normalized transaction and trace path schema agreed across team members.

Data precision: Token amounts use Python Decimal, timestamps use datetime,
and TracePath maintains a flat ordered transactions list.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator


class NormalizedTransaction(BaseModel):
    chain: str = Field(..., description="Blockchain identifier, e.g. ethereum, bitcoin, tron, bsc")
    tx_hash: str = Field(..., description="Unique transaction hash or identifier on chain")
    from_address: str = Field(..., description="Sender wallet or contract address")
    to_address: str = Field(..., description="Recipient wallet or contract address")
    amount: Decimal = Field(..., description="Precise decimal amount transferred")
    asset_symbol: str = Field(..., description="Symbol of transferred asset, e.g. ETH, BTC, USDT")
    timestamp: datetime = Field(..., description="UTC timestamp of the transaction")
    block_number: Optional[int] = Field(None, description="Block number or height")
    source: str = Field(default="blockchain_api", description="Data source provider name")

    def amount_decimal(self) -> Decimal:
        """Returns the transfer amount as a Python Decimal."""
        return self.amount


class TraceHop(BaseModel):
    """Optional hop wrapper for components that annotate individual hops."""
    hop_number: int
    transaction: NormalizedTransaction
    sender_label: Optional[str] = None
    receiver_label: Optional[str] = None


class TracePath(BaseModel):
    investigation_id: str
    chain: str
    start_address: str
    end_address: str
    hop_count: int
    transactions: List[NormalizedTransaction] = Field(
        default_factory=list,
        description="Flat ordered list of transactions traversing this path",
    )
    total_volume: Decimal = Field(default=Decimal("0"), description="Total path volume as Decimal")
    is_terminal_endpoint: bool = False
    path_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_transactions_from_hops(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If hops list provided, populate flat transactions list
            if "hops" in data and not data.get("transactions"):
                extracted = []
                for h in data["hops"]:
                    if isinstance(h, dict) and "transaction" in h:
                        extracted.append(h["transaction"])
                    elif hasattr(h, "transaction"):
                        extracted.append(h.transaction)
                data["transactions"] = extracted
            # If total_volume is string, convert
            if isinstance(data.get("total_volume"), str):
                try:
                    data["total_volume"] = Decimal(data["total_volume"])
                except Exception:
                    data["total_volume"] = Decimal("0")
        return data

    @property
    def hops(self) -> List[TraceHop]:
        """Provides backward-compatible hop access over the flat transactions list."""
        return [
            TraceHop(hop_number=i + 1, transaction=tx)
            for i, tx in enumerate(self.transactions)
        ]
