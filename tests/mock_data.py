"""Shared mock test data for team integration tests.

Complies with the agreed schema:
- Decimal token amounts
- datetime timestamps
- flat transactions list in TracePath
"""

from datetime import datetime, timezone
from decimal import Decimal

from backend.schemas.attribution import AddressLabel, EntityCategory, VerificationStatus
from backend.schemas.transaction import NormalizedTransaction, TracePath

SAMPLE_TRANSACTION_DICT = {
    "chain": "ethereum",
    "tx_hash": "0x1111222233334444555566667777888899990000111122223333444455556666",
    "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount": "12.3456",
    "asset_symbol": "ETH",
    "timestamp": "2026-10-02T10:30:00Z",
    "block_number": 21000000,
    "source": "etherscan_api",
}

SAMPLE_NORMALIZED_TX = NormalizedTransaction(
    chain="ethereum",
    tx_hash="0x1111222233334444555566667777888899990000111122223333444455556666",
    from_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    to_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    amount=Decimal("12.3456"),
    asset_symbol="ETH",
    timestamp=datetime(2026, 10, 2, 10, 30, 0, tzinfo=timezone.utc),
    block_number=21000000,
    source="etherscan_api",
)

SAMPLE_TRACE_PATH = TracePath(
    investigation_id="TEST-CASE-001",
    chain="ethereum",
    start_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    end_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    hop_count=1,
    transactions=[SAMPLE_NORMALIZED_TX],
    total_volume=Decimal("12.3456"),
    is_terminal_endpoint=True,
)

SAMPLE_LABEL = AddressLabel(
    id="lbl-test-01",
    chain="ethereum",
    address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    entity_name="Test Exchange",
    entity_category=EntityCategory.EXCHANGE_VASP,
    source="Verified Test Source",
    source_url="https://example.com",
    confidence=0.99,
    verified_at="2026-01-01T00:00:00Z",
    verification_status=VerificationStatus.VERIFIED,
)
