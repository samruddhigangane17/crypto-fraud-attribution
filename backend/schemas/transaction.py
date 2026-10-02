from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

Chain = Literal["bitcoin", "ethereum", "tron", "bsc"]

# Chains whose addresses are case-insensitive hex -> store lowercase.
# Bitcoin and TRON addresses are case-sensitive -> keep as given.
LOWERCASE_CHAINS = {"ethereum", "bsc"}


class NormalizedTransaction(BaseModel):
    """Shared transaction format used by ALL modules.

    Changes to this file need approval from all three team members.
    """

    chain: Chain
    tx_hash: str
    from_address: str
    to_address: str
    amount: Decimal  # never float
    asset_symbol: str  # "ETH", "USDT", "BTC", ...
    timestamp: datetime  # UTC
    block_number: int | None = None
    contract_address: str | None = None  # set for token transfers
    source: str = "blockchain_api"
    raw_ref: str | None = None  # info needed to re-fetch the original record

    @field_validator("amount", mode="before")
    @classmethod
    def _amount_not_float(cls, v):
        if isinstance(v, float):
            raise ValueError("amount must be str, int or Decimal - not float")
        return v

    @model_validator(mode="after")
    def _normalize_addresses(self):
        if self.chain in LOWERCASE_CHAINS:
            self.from_address = self.from_address.lower()
            self.to_address = self.to_address.lower()
            if self.contract_address:
                self.contract_address = self.contract_address.lower()
        return self
