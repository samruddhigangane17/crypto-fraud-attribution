from datetime import datetime, timezone
from decimal import Decimal
import pytest

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.normalizer import (
    EthereumNormalizer,
    NormalizationError,
    is_valid_eth_address,
    parse_unix_timestamp,
    parse_wei_to_eth,
)


def _sample_raw_tx(**overrides):
    base = {
        "blockNumber": "18000000",
        "timeStamp": "1696245000",
        "hash": "0x4a5b6c7d8e9f0123456789abcdef0123456789abcdef0123456789abcdef01",
        "nonce": "42",
        "from": "0x1111111111111111111111111111111111111111",
        "to": "0x2222222222222222222222222222222222222222",
        "value": "1500000000000000000",  # 1.5 ETH
        "gas": "21000",
        "gasPrice": "20000000000",
        "isError": "0",
        "txreceipt_status": "1",
        "input": "0x",
        "contractAddress": "",
    }
    if "from_" in overrides:
        base["from"] = overrides.pop("from_")
    base.update(overrides)
    return base



def test_normalize_valid_transaction():
    raw = _sample_raw_tx()
    tx = EthereumNormalizer.normalize_transaction(raw)

    assert isinstance(tx, NormalizedTransaction)
    assert tx.chain == "ethereum"
    assert tx.tx_hash == "0x4a5b6c7d8e9f0123456789abcdef0123456789abcdef0123456789abcdef01"
    assert tx.from_address == "0x1111111111111111111111111111111111111111"
    assert tx.to_address == "0x2222222222222222222222222222222222222222"
    assert tx.amount == Decimal("1.5")
    assert isinstance(tx.amount, Decimal)
    assert not isinstance(tx.amount, float)
    assert tx.asset_symbol == "ETH"
    assert tx.block_number == 18000000
    assert tx.source == "etherscan"
    assert tx.raw_ref == tx.tx_hash
    assert tx.timestamp.tzinfo == timezone.utc
    assert tx.timestamp == datetime(2023, 10, 2, 11, 10, 0, tzinfo=timezone.utc)


def test_address_lowercased():
    raw = _sample_raw_tx(
        from_="0xAAAAAAAA11111111111111111111111111111111",
        to="0xBBBBBBBB22222222222222222222222222222222",
    )
    tx = EthereumNormalizer.normalize_transaction(raw)
    assert tx.from_address == "0xaaaaaaaa11111111111111111111111111111111"
    assert tx.to_address == "0xbbbbbbbb22222222222222222222222222222222"


def test_wei_conversion_precision():
    # 1 Wei
    assert parse_wei_to_eth("1") == Decimal("0.000000000000000001")
    # 1 ETH
    assert parse_wei_to_eth("1000000000000000000") == Decimal("1")
    # 0 Wei
    assert parse_wei_to_eth("0") == Decimal("0")
    # Large arbitrary amount: 12.345678901234567890 ETH
    assert parse_wei_to_eth("12345678901234567890") == Decimal("12.34567890123456789")


def test_wei_conversion_invalid_inputs():
    with pytest.raises(NormalizationError, match="must not be a float"):
        parse_wei_to_eth(1.5)

    with pytest.raises(NormalizationError, match="Negative"):
        parse_wei_to_eth("-100")

    with pytest.raises(NormalizationError, match="Malformed"):
        parse_wei_to_eth("not-a-number")

    with pytest.raises(NormalizationError, match="Missing"):
        parse_wei_to_eth(None)

    with pytest.raises(NormalizationError, match="fractional"):
        parse_wei_to_eth("100.5")


def test_unix_timestamp_parsing():
    dt = parse_unix_timestamp("1696245000")
    assert dt == datetime(2023, 10, 2, 11, 10, 0, tzinfo=timezone.utc)
    assert dt.tzinfo is not None

    with pytest.raises(NormalizationError, match="must not be a float"):
        parse_unix_timestamp(1696245000.5)

    with pytest.raises(NormalizationError, match="Negative"):
        parse_unix_timestamp(-1)

    with pytest.raises(NormalizationError, match="Malformed"):
        parse_unix_timestamp("invalid_ts")

    with pytest.raises(NormalizationError, match="Missing"):
        parse_unix_timestamp(None)


def test_failed_transactions_rejected():
    with pytest.raises(NormalizationError, match="failed or was reverted"):
        EthereumNormalizer.normalize_transaction(_sample_raw_tx(isError="1"))

    with pytest.raises(NormalizationError, match="failed or was reverted"):
        EthereumNormalizer.normalize_transaction(_sample_raw_tx(txreceipt_status="0"))


def test_missing_or_invalid_address():
    with pytest.raises(NormalizationError, match="Invalid from_address"):
        EthereumNormalizer.normalize_transaction(_sample_raw_tx(from_="invalid_addr"))

    raw = _sample_raw_tx()
    raw["from"] = "0xShort"
    with pytest.raises(NormalizationError, match="Invalid from_address"):
        EthereumNormalizer.normalize_transaction(raw)

    raw = _sample_raw_tx(to="")
    with pytest.raises(NormalizationError, match="missing recipient address"):
        EthereumNormalizer.normalize_transaction(raw)


def test_contract_creation_with_contract_address():
    raw = _sample_raw_tx(
        to="",
        contractAddress="0x3333333333333333333333333333333333333333",
    )
    tx = EthereumNormalizer.normalize_transaction(raw)
    assert tx.to_address == "0x3333333333333333333333333333333333333333"


def test_invalid_hash_and_block_number():
    with pytest.raises(NormalizationError, match="Invalid or missing transaction hash"):
        EthereumNormalizer.normalize_transaction(_sample_raw_tx(hash="not_a_hex_hash"))

    with pytest.raises(NormalizationError, match="Malformed block number"):
        EthereumNormalizer.normalize_transaction(_sample_raw_tx(blockNumber="bad_block"))


def test_is_valid_eth_address_helper():
    assert is_valid_eth_address("0x1111111111111111111111111111111111111111")
    assert is_valid_eth_address("0xABCDEFabcdef0123456789012345678901234567")
    assert not is_valid_eth_address("1111111111111111111111111111111111111111")  # missing 0x
    assert not is_valid_eth_address("0x123")  # too short
    assert not is_valid_eth_address("0xZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ")  # non-hex
    assert not is_valid_eth_address(None)
    assert not is_valid_eth_address(12345)


def test_normalize_erc20_token_transaction():
    raw_token_tx = {
        "blockNumber": "17000000",
        "timeStamp": "1696245000",
        "hash": "0x5a6b7c8d9e0f123456789abcdef0123456789abcdef0123456789abcdef01234",
        "from": "0x1111111111111111111111111111111111111111",
        "to": "0x2222222222222222222222222222222222222222",
        "value": "2500000000",  # 2500 USDT (6 decimals)
        "tokenName": "Tether USD",
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
        "contractAddress": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "isError": "0",
    }
    tx = EthereumNormalizer.normalize_token_transaction(raw_token_tx)
    assert isinstance(tx, NormalizedTransaction)
    assert tx.chain == "ethereum"
    assert tx.asset_symbol == "USDT"
    assert tx.amount == Decimal("2500")
    assert tx.contract_address == "0xdac17f958d2ee523a2206206994597c13d831ec7"
    assert tx.block_number == 17000000
    assert tx.source == "etherscan"


def test_normalize_token_custom_decimals():
    # 8 decimals (e.g. WBTC): 50000000 = 0.5 WBTC
    from backend.tracing.normalizer import parse_token_amount
    assert parse_token_amount("50000000", token_decimal=8) == Decimal("0.5")

    # 0 decimals (non-divisible tokens): 42 = 42
    assert parse_token_amount("42", token_decimal=0) == Decimal("42")

    # 18 decimals: 1000000000000000000 = 1.0
    assert parse_token_amount("1000000000000000000", token_decimal=18) == Decimal("1.0")


def test_normalize_token_invalid_inputs():
    from backend.tracing.normalizer import parse_token_amount
    with pytest.raises(NormalizationError, match="must not be a float"):
        parse_token_amount(100.5, 6)

    with pytest.raises(NormalizationError, match="Negative"):
        parse_token_amount("-500", 6)

    with pytest.raises(NormalizationError, match="Missing"):
        parse_token_amount(None, 6)

    with pytest.raises(NormalizationError, match="out of valid range"):
        parse_token_amount("100", 40)

    # Missing contractAddress in token transfer
    raw_bad = {
        "hash": "0xabc1234567890123456789012345678901234567890123456789012345678901",
        "from": "0x1111111111111111111111111111111111111111",
        "to": "0x2222222222222222222222222222222222222222",
        "value": "1000",
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
        "contractAddress": "invalid_contract",
        "timeStamp": "1696245000",
    }
    with pytest.raises(NormalizationError, match="contractAddress"):
        EthereumNormalizer.normalize_token_transaction(raw_bad)


def test_auto_dispatch_token_in_normalize_transaction():
    raw_token_tx = {
        "hash": "0xabc1234567890123456789012345678901234567890123456789012345678901",
        "from": "0x1111111111111111111111111111111111111111",
        "to": "0x2222222222222222222222222222222222222222",
        "value": "5000000",
        "tokenSymbol": "USDC",
        "tokenDecimal": "6",
        "contractAddress": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "timeStamp": "1696245000",
    }
    tx = EthereumNormalizer.normalize_transaction(raw_token_tx)
    assert tx.asset_symbol == "USDC"
    assert tx.amount == Decimal("5")
    assert tx.contract_address == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"

