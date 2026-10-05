"""Tests for Multi-Chain Connectors and Chain Auto-detection (TC-01, TC-02)."""

import pytest
from backend.tracing.connectors.factory import build_connector
from backend.tracing.validation import detect_chain, is_valid_address, resolve_chain_and_address


# --- TC-01: Valid BTC / ETH / TRON / BSC address auto-detected ---
def test_tc01_valid_addresses_and_chain_autodetection():
    # Valid Ethereum address
    eth_addr = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    chain_eth, norm_eth = resolve_chain_and_address("auto", eth_addr)
    assert chain_eth == "ethereum"
    assert norm_eth == eth_addr

    # Valid Bitcoin address (Legacy 1..., Segwit 3..., Native Segwit bc1...)
    btc_addr = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
    chain_btc, norm_btc = resolve_chain_and_address("auto", btc_addr)
    assert chain_btc == "bitcoin"
    assert norm_btc == btc_addr

    btc_legacy = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert detect_chain(btc_legacy) == "bitcoin"

    # Valid TRON address (T...)
    tron_addr = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    chain_tron, norm_tron = resolve_chain_and_address("auto", tron_addr)
    assert chain_tron == "tron"
    assert norm_tron == tron_addr

    # Valid BSC address (explicit chain with EVM address)
    chain_bsc, norm_bsc = resolve_chain_and_address("bsc", eth_addr)
    assert chain_bsc == "bsc"
    assert norm_bsc == eth_addr


# --- TC-02: Malformed or Unsupported Address ---
def test_tc02_malformed_or_unsupported_address():
    # Malformed EVM / BSC
    with pytest.raises(ValueError, match="not a valid"):
        resolve_chain_and_address("ethereum", "0xinvalidlength")

    # Malformed TRON
    with pytest.raises(ValueError, match="not a valid"):
        resolve_chain_and_address("tron", "T123Short")

    # Malformed Bitcoin
    with pytest.raises(ValueError, match="not a valid"):
        resolve_chain_and_address("bitcoin", "bc1invalidCharsO0Il")

    # Unsupported chain
    with pytest.raises(ValueError, match="Unsupported chain"):
        resolve_chain_and_address("dogecoin", "D123456789")

    # Auto-detection on gibberish
    with pytest.raises(ValueError, match="Could not detect"):
        resolve_chain_and_address("auto", "not_an_address_at_all")


# --- Connectors Factory Builds for All 4 Chains ---
def test_connectors_build_without_501(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test_key")
    monkeypatch.setenv("BSCSCAN_API_KEY", "test_key")

    conn_eth = build_connector("ethereum", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
    assert conn_eth is not None

    conn_bsc = build_connector("bsc", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
    assert conn_bsc is not None

    conn_btc = build_connector("bitcoin", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
    assert conn_btc is not None

    conn_tron = build_connector("tron", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
    assert conn_tron is not None
