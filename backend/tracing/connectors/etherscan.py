import os
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.normalizer import EthereumNormalizer, NormalizationError, is_valid_eth_address


def sanitize_message(msg: str, api_key: Optional[str] = None) -> str:
    """Redact API keys from URL strings, parameters, and exception messages."""
    if not msg:
        return ""
    sanitized = re.sub(r"([?&]apikey=)[^&\s]+", r"\1[REDACTED]", msg)
    if api_key and api_key.strip():
        sanitized = sanitized.replace(api_key.strip(), "[REDACTED]")
    return sanitized


class EtherscanConnectorError(Exception):
    """Base exception for Etherscan connector errors."""
    pass


class EtherscanRateLimitError(EtherscanConnectorError):
    """Raised when Etherscan rate limits are reached."""
    pass


class EtherscanAPIError(EtherscanConnectorError):
    """Raised when Etherscan API returns an error response."""
    pass


class EtherscanHTTPError(EtherscanConnectorError):
    """Raised when an HTTP error status code occurs."""
    pass


class EtherscanTimeoutError(EtherscanConnectorError):
    """Raised when HTTP request to Etherscan times out."""
    pass


class EtherscanConnector(BaseConnector):
    """Connector for retrieving Ethereum transactions via Etherscan Developer API V2."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.etherscan.io/v2/api",
        chain_id: int = 1,
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
        max_retries: int = 2,
        retry_delay: float = 0.05,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("ETHERSCAN_API_KEY", "")
        self.base_url = base_url
        self.chain_id = chain_id
        self.timeout = timeout
        self._external_client = client
        self.max_retries = max(0, max_retries)
        self.retry_delay = max(0.0, retry_delay)

    def _get_client(self) -> httpx.Client:
        if self._external_client is not None:
            return self._external_client
        return httpx.Client(timeout=self.timeout)

    def fetch_page(
        self,
        address: str,
        page: int = 1,
        offset: int = 100,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        action: str = "txlist",
    ) -> List[Dict[str, Any]]:
        """Fetch a single page of raw transactions (native txlist or tokentx) from Etherscan."""
        if not is_valid_eth_address(address):
            raise ValueError(f"Invalid Ethereum address: {address!r}")

        params: Dict[str, Any] = {
            "chainid": self.chain_id,
            "module": "account",
            "action": action,
            "address": address,
            "startblock": start_block if start_block is not None else 0,
            "endblock": end_block if end_block is not None else 99999999,
            "page": page,
            "offset": offset,
            "sort": "asc",
        }
        if self.api_key:
            params["apikey"] = self.api_key

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.max_retries:
            try:
                client = self._get_client()
                if self._external_client is not None:
                    resp = client.get(self.base_url, params=params)
                else:
                    with client:
                        resp = client.get(self.base_url, params=params)

                if resp.status_code != 200:
                    clean_text = sanitize_message(resp.text[:200], self.api_key)
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                        attempt += 1
                        time.sleep(self.retry_delay * (2 ** (attempt - 1)))
                        continue
                    raise EtherscanHTTPError(f"Etherscan returned HTTP {resp.status_code}: {clean_text}")

                try:
                    data = resp.json()
                except Exception as err:
                    clean_body = sanitize_message(resp.text[:200], self.api_key)
                    raise EtherscanAPIError(f"Malformed JSON returned by Etherscan: {clean_body}") from err

                status = str(data.get("status", "")).strip()
                message = str(data.get("message", "")).strip()
                result = data.get("result")

                # Status "0" indicates either no records found or an error/rate-limit
                if status == "0":
                    if "no transactions found" in message.lower() or result == []:
                        return []

                    result_str = str(result)
                    is_rate_limit = (
                        "rate limit" in result_str.lower() or "rate limit" in message.lower()
                    )

                    if is_rate_limit:
                        if attempt < self.max_retries:
                            attempt += 1
                            time.sleep(self.retry_delay * (2 ** (attempt - 1)))
                            continue
                        raise EtherscanRateLimitError(
                            sanitize_message(f"Etherscan rate limit reached: {result_str}", self.api_key)
                        )

                    raise EtherscanAPIError(
                        sanitize_message(f"Etherscan error: message={message!r}, result={result_str!r}", self.api_key)
                    )

                if not isinstance(result, list):
                    raise EtherscanAPIError(
                        f"Expected list of transactions in result, got {type(result).__name__}"
                    )

                return result

            except httpx.TimeoutException as err:
                last_error = err
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_delay * (2 ** (attempt - 1)))
                    continue
                clean_err = sanitize_message(str(err), self.api_key)
                raise EtherscanTimeoutError(f"Request to Etherscan timed out: {clean_err}") from err

            except httpx.HTTPError as err:
                last_error = err
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_delay * (2 ** (attempt - 1)))
                    continue
                clean_err = sanitize_message(str(err), self.api_key)
                raise EtherscanHTTPError(f"HTTP communication error with Etherscan: {clean_err}") from err

        if last_error:
            clean_err = sanitize_message(str(last_error), self.api_key)
            raise EtherscanConnectorError(f"Failed after retries: {clean_err}") from last_error
        return []

    def fetch_token_page(
        self,
        address: str,
        page: int = 1,
        offset: int = 100,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a single page of ERC-20 token transfers from Etherscan."""
        return self.fetch_page(
            address=address,
            page=page,
            offset=offset,
            start_block=start_block,
            end_block=end_block,
            action="tokentx",
        )

    def get_token_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_pages: int = 10,
        page_size: int = 100,
    ) -> List[NormalizedTransaction]:
        """Fetch ERC-20 token transfer history for address and return normalized records."""
        normalized: List[NormalizedTransaction] = []
        page = 1

        while page <= max_pages:
            raw_txs = self.fetch_token_page(
                address=address,
                page=page,
                offset=page_size,
                start_block=start_block,
                end_block=end_block,
            )

            if not raw_txs:
                break

            for raw_tx in raw_txs:
                try:
                    tx = EthereumNormalizer.normalize_token_transaction(raw_tx)
                    normalized.append(tx)
                except NormalizationError:
                    continue

            if len(raw_txs) < page_size:
                break

            page += 1

        return normalized

    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        max_pages: int = 10,
        page_size: int = 100,
        include_token_transfers: bool = False,
    ) -> List[NormalizedTransaction]:
        """Fetch all pages of transactions for address and return normalized records.
        
        Failed on-chain transactions (isError == "1") and unparseable records are excluded.
        If include_token_transfers is True, also fetches and merges ERC-20 token transfers.
        """
        normalized: List[NormalizedTransaction] = []
        page = 1

        while page <= max_pages:
            raw_txs = self.fetch_page(
                address=address,
                page=page,
                offset=page_size,
                start_block=start_block,
                end_block=end_block,
                action="txlist",
            )

            if not raw_txs:
                break

            for raw_tx in raw_txs:
                try:
                    tx = EthereumNormalizer.normalize_transaction(raw_tx)
                    normalized.append(tx)
                except NormalizationError:
                    # Skip reverted transactions or records that cannot be normalized
                    continue

            # If fewer transactions than page_size were returned, this was the last page
            if len(raw_txs) < page_size:
                break

            page += 1

        if include_token_transfers:
            token_txs = self.get_token_transactions(
                address=address,
                start_block=start_block,
                end_block=end_block,
                max_pages=max_pages,
                page_size=page_size,
            )
            # Combine and sort chronologically
            normalized.extend(token_txs)
            normalized.sort(key=lambda t: (t.timestamp, t.block_number or 0))

        return normalized

