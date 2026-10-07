from typing import List, Optional

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector


class MockConnector(BaseConnector):
    """Deterministic offline connector for testing and local development.
    
    Uses static mock transactions and avoids external network calls.
    """

    def __init__(self, transactions: Optional[List[NormalizedTransaction]] = None):
        if transactions is None:
            from tests.mock_data import MOCK_TRANSACTIONS
            self._transactions = list(MOCK_TRANSACTIONS)
        else:
            self._transactions = list(transactions)

    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        include_token_transfers: bool = False,
    ) -> List[NormalizedTransaction]:
        """Return transactions where address is sender or receiver."""
        addr_lower = address.lower()
        results: List[NormalizedTransaction] = []

        for tx in self._transactions:
            if tx.from_address.lower() == addr_lower or tx.to_address.lower() == addr_lower:
                if start_block is not None and tx.block_number is not None and tx.block_number < start_block:
                    continue
                if end_block is not None and tx.block_number is not None and tx.block_number > end_block:
                    continue
                results.append(tx)

        return results

    def add_transaction(self, tx: NormalizedTransaction) -> None:
        """Allow test suites to inject custom test transactions into the mock."""
        self._transactions.append(tx)
