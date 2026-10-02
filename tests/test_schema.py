from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.schemas.transaction import NormalizedTransaction
from tests.mock_data import MOCK_TRANSACTIONS


def _tx(**kw):
    base = dict(
        chain="ethereum", tx_hash="0xmock1",
        from_address="0xMOCK_A", to_address="0xMOCK_B",
        amount="1.25", asset_symbol="ETH",
        timestamp="2026-10-02T10:30:00Z",
    )
    base.update(kw)
    return NormalizedTransaction(**base)


def test_amount_is_decimal():
    assert _tx().amount == Decimal("1.25")


def test_float_amount_rejected():
    with pytest.raises(ValidationError):
        _tx(amount=1.25)


def test_ethereum_addresses_lowercased():
    assert _tx().from_address == "0xmock_a"


def test_tron_addresses_keep_case():
    assert _tx(chain="tron", from_address="TMockAbC").from_address == "TMockAbC"


def test_unknown_chain_rejected():
    with pytest.raises(ValidationError):
        _tx(chain="dogecoin")


def test_mock_data_loads():
    assert len(MOCK_TRANSACTIONS) == 7
