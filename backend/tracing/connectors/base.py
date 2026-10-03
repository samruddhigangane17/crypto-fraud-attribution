from abc import ABC, abstractmethod
from typing import List, Optional

from backend.schemas.transaction import NormalizedTransaction


class BaseConnector(ABC):
    """Abstract base connector for blockchain data providers."""

    @abstractmethod
    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
    ) -> List[NormalizedTransaction]:
        """Fetch and return normalized transactions involving the given wallet address.
        
        Args:
            address: The blockchain wallet address to query.
            start_block: Optional start block number for filtering.
            end_block: Optional end block number for filtering.
            
        Returns:
            A list of NormalizedTransaction objects.
        """
        pass
