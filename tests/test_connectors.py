import json
from decimal import Decimal
import pytest
import httpx

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.etherscan import (
    EtherscanConnector,
    EtherscanRateLimitError,
    EtherscanAPIError,
    EtherscanHTTPError,
    EtherscanTimeoutError,
)
from tests.mock_data import MOCK_TRANSACTIONS


# --- MockConnector Tests ---

def test_mock_connector_default_transactions():
    connector = MockConnector()
    txs_a = connector.get_transactions("0xmock_wallet_a")
    assert len(txs_a) >= 2  # mock data has multiple transfers from 0xmock_wallet_a
    assert all("0xmock_wallet_a" in (tx.from_address, tx.to_address) for tx in txs_a)


def test_mock_connector_case_insensitive():
    connector = MockConnector()
    txs_lower = connector.get_transactions("0xmock_wallet_a")
    txs_upper = connector.get_transactions("0xMOCK_WALLET_A")
    assert len(txs_lower) == len(txs_upper)


def test_mock_connector_unknown_address():
    connector = MockConnector()
    txs = connector.get_transactions("0x0000000000000000000000000000000000000000")
    assert txs == []


def test_mock_connector_block_range():
    connector = MockConnector()
    txs_filtered = connector.get_transactions("0xmock_wallet_a", start_block=1002, end_block=1020)
    for tx in txs_filtered:
        assert tx.block_number is not None
        assert 1002 <= tx.block_number <= 1020


def test_mock_connector_custom_txs():
    custom_tx = NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xcustom123",
        from_address="0x1111111111111111111111111111111111111111",
        to_address="0x2222222222222222222222222222222222222222",
        amount=Decimal("5.0"),
        asset_symbol="ETH",
        timestamp="2026-10-02T12:00:00Z",
    )
    connector = MockConnector(transactions=[custom_tx])
    assert len(connector.get_transactions("0x1111111111111111111111111111111111111111")) == 1
    assert len(connector.get_transactions("0xmock_wallet_a")) == 0


# --- EtherscanConnector Tests with Mocked HTTP Transport ---

VALID_ADDR = "0x1111111111111111111111111111111111111111"
VALID_RECIPIENT = "0x2222222222222222222222222222222222222222"

def _make_etherscan_raw_tx(tx_hash="0xabc123", value_wei="1000000000000000000"):
    return {
        "blockNumber": "15000000",
        "timeStamp": "1696245000",
        "hash": tx_hash,
        "nonce": "1",
        "from": VALID_ADDR,
        "to": VALID_RECIPIENT,
        "value": value_wei,
        "gas": "21000",
        "gasPrice": "20000000000",
        "isError": "0",
        "txreceipt_status": "1",
        "input": "0x",
        "contractAddress": "",
    }


def test_etherscan_connector_success():
    raw_tx = _make_etherscan_raw_tx()
    api_response = {
        "status": "1",
        "message": "OK",
        "result": [raw_tx],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "address=" + VALID_ADDR in str(request.url)
        assert "action=txlist" in str(request.url)
        return httpx.Response(200, json=api_response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    txs = connector.get_transactions(VALID_ADDR)
    assert len(txs) == 1
    assert txs[0].tx_hash == "0xabc123"
    assert txs[0].amount == Decimal("1.0")
    assert txs[0].source == "etherscan"


def test_etherscan_connector_empty_history():
    api_response = {
        "status": "0",
        "message": "No transactions found",
        "result": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=api_response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    txs = connector.get_transactions(VALID_ADDR)
    assert txs == []


def test_etherscan_connector_rate_limit_error():
    api_response = {
        "status": "0",
        "message": "NOTOK",
        "result": "Max rate limit reached",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=api_response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    with pytest.raises(EtherscanRateLimitError, match="rate limit"):
        connector.get_transactions(VALID_ADDR)


def test_etherscan_connector_api_error():
    api_response = {
        "status": "0",
        "message": "NOTOK",
        "result": "Invalid API Key",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=api_response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    with pytest.raises(EtherscanAPIError, match="Invalid API Key"):
        connector.get_transactions(VALID_ADDR)


def test_etherscan_connector_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    with pytest.raises(EtherscanHTTPError, match="HTTP 500"):
        connector.get_transactions(VALID_ADDR)


def test_etherscan_connector_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    with pytest.raises(EtherscanTimeoutError, match="timed out"):
        connector.get_transactions(VALID_ADDR)


def test_etherscan_connector_invalid_address():
    connector = EtherscanConnector(api_key="test_key")
    with pytest.raises(ValueError, match="Invalid Ethereum address"):
        connector.get_transactions("not_an_eth_address")


def test_etherscan_connector_pagination():
    tx1 = _make_etherscan_raw_tx("0xhash1")
    tx2 = _make_etherscan_raw_tx("0xhash2")

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(httpx.QueryParams(request.url.query))
        page = params.get("page")
        if page == "1":
            return httpx.Response(200, json={"status": "1", "message": "OK", "result": [tx1]})
        elif page == "2":
            return httpx.Response(200, json={"status": "1", "message": "OK", "result": [tx2]})
        else:
            return httpx.Response(200, json={"status": "0", "message": "No transactions found", "result": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    # With page_size=1, page 1 returns 1 tx, page 2 returns 1 tx, page 3 returns 0 txs
    txs = connector.get_transactions(VALID_ADDR, page_size=1, max_pages=5)
    assert len(txs) == 2
    assert [t.tx_hash for t in txs] == ["0xhash1", "0xhash2"]


def test_etherscan_retry_on_transient_error_succeeds():
    attempts = 0
    raw_tx = _make_etherscan_raw_tx("0xretry_success")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, text="Temporary Server Error")
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": [raw_tx]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="secret_key_123", client=client, max_retries=2, retry_delay=0.01)

    txs = connector.get_transactions(VALID_ADDR)
    assert attempts == 2
    assert len(txs) == 1
    assert txs[0].tx_hash == "0xretry_success"


def test_etherscan_retry_on_rate_limit_succeeds():
    attempts = 0
    raw_tx = _make_etherscan_raw_tx("0xrate_limit_success")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(200, json={"status": "0", "message": "NOTOK", "result": "Max rate limit reached"})
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": [raw_tx]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="secret_key_123", client=client, max_retries=2, retry_delay=0.01)

    txs = connector.get_transactions(VALID_ADDR)
    assert attempts == 2
    assert len(txs) == 1
    assert txs[0].tx_hash == "0xrate_limit_success"


def test_etherscan_api_key_redacted_in_exceptions():
    secret_key = "very_secret_api_key_xyz"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=f"Forbidden request with apikey={secret_key}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key=secret_key, client=client, max_retries=0)

    with pytest.raises(EtherscanHTTPError) as exc_info:
        connector.get_transactions(VALID_ADDR)

    err_text = str(exc_info.value)
    assert secret_key not in err_text
    assert "[REDACTED]" in err_text


def test_etherscan_fetch_token_transfers():
    raw_token_tx = {
        "blockNumber": "15000000",
        "timeStamp": "1696245000",
        "hash": "0xtokentx123",
        "from": VALID_ADDR,
        "to": VALID_RECIPIENT,
        "value": "10000000",  # 10.0 USDT (6 decimals)
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
        "contractAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "isError": "0",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "action=tokentx" in str(request.url)
        return httpx.Response(200, json={"status": "1", "message": "OK", "result": [raw_token_tx]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    token_txs = connector.get_token_transactions(VALID_ADDR)
    assert len(token_txs) == 1
    assert token_txs[0].asset_symbol == "USDT"
    assert token_txs[0].amount == Decimal("10")
    assert token_txs[0].contract_address == "0xdac17f958d2ee523a2206206994597c13d831ec7"


def test_etherscan_include_token_transfers_combined():
    native_tx = _make_etherscan_raw_tx("0xnative1")
    token_tx = {
        "blockNumber": "15000001",
        "timeStamp": "1696245100",
        "hash": "0xtoken1",
        "from": VALID_ADDR,
        "to": VALID_RECIPIENT,
        "value": "5000000",
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
        "contractAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "isError": "0",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        query_str = str(request.url)
        if "action=txlist" in query_str:
            return httpx.Response(200, json={"status": "1", "message": "OK", "result": [native_tx]})
        elif "action=tokentx" in query_str:
            return httpx.Response(200, json={"status": "1", "message": "OK", "result": [token_tx]})
        return httpx.Response(200, json={"status": "0", "message": "No transactions found", "result": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)

    combined = connector.get_transactions(VALID_ADDR, include_token_transfers=True)
    assert len(combined) == 2
    symbols = {t.asset_symbol for t in combined}
    assert symbols == {"ETH", "USDT"}


def test_etherscan_connector_v2_endpoint_and_chainid():
    raw_tx = _make_etherscan_raw_tx()
    api_response = {
        "status": "1",
        "message": "OK",
        "result": [raw_tx],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        assert "https://api.etherscan.io/v2/api" in url_str
        assert "chainid=1" in url_str
        assert "module=account" in url_str
        assert "action=txlist" in url_str
        return httpx.Response(200, json=api_response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = EtherscanConnector(api_key="test_key", client=client)
    assert connector.base_url == "https://api.etherscan.io/v2/api"
    assert connector.chain_id == 1

    txs = connector.get_transactions(VALID_ADDR)
    assert len(txs) == 1


