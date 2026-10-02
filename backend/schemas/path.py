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
