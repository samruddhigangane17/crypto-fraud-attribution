"""Tests for shared transaction, trace path, and attribution schemas."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from backend.schemas.transaction import NormalizedTransaction, TracePath
from tests.mock_data import SAMPLE_NORMALIZED_TX, SAMPLE_TRACE_PATH, SAMPLE_TRANSACTION_DICT


def test_normalized_transaction_decimal_and_datetime():
    """Verify NormalizedTransaction enforces Decimal amounts and datetime timestamps."""
    tx = NormalizedTransaction.model_validate(SAMPLE_TRANSACTION_DICT)

    assert isinstance(tx.amount, Decimal)
    assert tx.amount == Decimal("12.3456")
    assert isinstance(tx.timestamp, datetime)
    assert tx.timestamp.year == 2026
    assert tx.timestamp.month == 10
    assert tx.timestamp.day == 2
    assert tx.amount_decimal() == Decimal("12.3456")


def test_decimal_precision_preservation():
    """Verify precision is preserved without floating point distortion."""
    precise_amount = "123456789.123456789012345678"
    tx_data = dict(SAMPLE_TRANSACTION_DICT)
    tx_data["amount"] = precise_amount

    tx = NormalizedTransaction.model_validate(tx_data)
    assert isinstance(tx.amount, Decimal)
    assert str(tx.amount) == precise_amount


def test_trace_path_flat_transactions_list():
    """Verify TracePath uses a flat list of NormalizedTransaction objects."""
    path = SAMPLE_TRACE_PATH
    assert isinstance(path.transactions, list)
    assert len(path.transactions) == 1
    assert isinstance(path.transactions[0], NormalizedTransaction)
    assert isinstance(path.total_volume, Decimal)
    assert path.total_volume == Decimal("12.3456")


def test_trace_path_backward_compatible_hops_property():
    """Verify TracePath provides .hops property accessing hop_number and transaction."""
    path = SAMPLE_TRACE_PATH
    assert hasattr(path, "hops")
    hops = path.hops
    assert len(hops) == 1
    assert hops[0].hop_number == 1
    assert hops[0].transaction.tx_hash == SAMPLE_NORMALIZED_TX.tx_hash
