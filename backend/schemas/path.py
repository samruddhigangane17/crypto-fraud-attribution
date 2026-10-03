from pydantic import BaseModel

from backend.schemas.transaction import NormalizedTransaction


class TracePath(BaseModel):
    """One ordered chain of transfers starting at the reported address.

    Output of Member 1's tracing module; input to Member 2's modules.
    """

    investigation_id: str
    hop_count: int
    transactions: list[NormalizedTransaction]  # ordered, first = closest to origin
    end_address: str

    @property
    def intermediate_addresses(self) -> list[str]:
        """Return all intermediate wallet addresses between origin and destination."""
        if len(self.transactions) <= 1:
            return []
        # Intermediate addresses are the recipients of all transfers except the last one
        return [tx.to_address for tx in self.transactions[:-1]]

    @property
    def all_addresses(self) -> list[str]:
        """Return the sequence of all wallet addresses along the path (origin to end)."""
        if not self.transactions:
            return [self.end_address] if self.end_address else []
        addrs = [self.transactions[0].from_address]
        for tx in self.transactions:
            addrs.append(tx.to_address)
        return addrs

