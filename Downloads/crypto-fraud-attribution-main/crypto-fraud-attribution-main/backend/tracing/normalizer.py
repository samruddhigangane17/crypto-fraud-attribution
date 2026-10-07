from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
import re

from backend.schemas.transaction import NormalizedTransaction

WEI_PER_ETH = Decimal("1000000000000000000")  # 10^18 Wei = 1 ETH
ETH_ADDRESS_REGEX = re.compile(r"^0x[0-9a-fA-F]{40}$")


class NormalizationError(ValueError):
    """Raised when raw transaction data cannot be normalized."""
    pass


def is_valid_eth_address(address: Optional[str]) -> bool:
    """Check if string is a valid 42-character hex Ethereum address."""
    if not address or not isinstance(address, str):
        return False
    return bool(ETH_ADDRESS_REGEX.match(address))


def parse_wei_to_eth(raw_wei: Any) -> Decimal:
    """Convert raw Wei (string or integer) to ETH Decimal without using float math."""
    if raw_wei is None:
        raise NormalizationError("Missing transaction value (Wei)")
    
    # Reject float values to avoid floating-point precision loss
    if isinstance(raw_wei, float):
        raise NormalizationError("Transaction value must not be a float")

    wei_str = str(raw_wei).strip()
    if not wei_str:
        raise NormalizationError("Empty transaction value string")

    try:
        wei_decimal = Decimal(wei_str)
    except InvalidOperation:
        raise NormalizationError(f"Malformed Wei value: {raw_wei!r}")

    # Wei cannot be negative or have decimal places
    if wei_decimal < 0:
        raise NormalizationError(f"Negative Wei value is invalid: {raw_wei!r}")
    if wei_decimal != wei_decimal.to_integral_value():
        raise NormalizationError(f"Wei value cannot contain fractional sub-units: {raw_wei!r}")

    # Precise Decimal division by 10^18
    return wei_decimal / WEI_PER_ETH


def parse_unix_timestamp(raw_timestamp: Any) -> datetime:
    """Convert Unix epoch timestamp string or int to timezone-aware UTC datetime."""
    if raw_timestamp is None:
        raise NormalizationError("Missing timestamp")

    if isinstance(raw_timestamp, float):
        raise NormalizationError("Timestamp must not be a float")

    ts_str = str(raw_timestamp).strip()
    if not ts_str:
        raise NormalizationError("Empty timestamp string")

    try:
        ts_int = int(ts_str)
    except ValueError:
        raise NormalizationError(f"Malformed Unix timestamp: {raw_timestamp!r}")

    if ts_int < 0:
        raise NormalizationError(f"Negative Unix timestamp is invalid: {raw_timestamp!r}")

    try:
        return datetime.fromtimestamp(ts_int, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as err:
        raise NormalizationError(f"Timestamp out of valid range: {raw_timestamp!r}") from err


def parse_token_amount(raw_value: Any, token_decimal: Any = 18) -> Decimal:
    """Convert raw token units to Decimal based on token decimals without float math."""
    if raw_value is None:
        raise NormalizationError("Missing token value")

    if isinstance(raw_value, float):
        raise NormalizationError("Token value must not be a float")

    val_str = str(raw_value).strip()
    if not val_str:
        raise NormalizationError("Empty token value string")

    try:
        val_decimal = Decimal(val_str)
    except InvalidOperation:
        raise NormalizationError(f"Malformed token value: {raw_value!r}")

    if val_decimal < 0:
        raise NormalizationError(f"Negative token value is invalid: {raw_value!r}")
    if val_decimal != val_decimal.to_integral_value():
        raise NormalizationError(f"Token value cannot contain fractional sub-units: {raw_value!r}")

    # Validate token_decimal
    if token_decimal is None:
        token_decimal = 18
    try:
        dec_int = int(str(token_decimal).strip())
    except (ValueError, TypeError):
        raise NormalizationError(f"Malformed token decimal: {token_decimal!r}")

    if dec_int < 0 or dec_int > 36:
        raise NormalizationError(f"Token decimal out of valid range (0-36): {token_decimal!r}")

    divisor = Decimal(10) ** dec_int
    return val_decimal / divisor


class EthereumNormalizer:
    """Normalizes raw Etherscan Ethereum transaction payloads into NormalizedTransaction."""

    @classmethod
    def normalize_token_transaction(cls, raw: Dict[str, Any]) -> NormalizedTransaction:
        """Convert a raw Etherscan ERC-20 token transfer record into NormalizedTransaction."""
        if not isinstance(raw, dict):
            raise NormalizationError(f"Raw transaction must be a dictionary, got {type(raw).__name__}")

        # Check for failed transactions
        is_error = str(raw.get("isError", "0")).strip()
        txreceipt_status = str(raw.get("txreceipt_status", "1")).strip()
        if is_error == "1" or txreceipt_status == "0":
            raise NormalizationError("Transaction failed or was reverted on-chain")

        tx_hash = raw.get("hash")
        if not tx_hash or not isinstance(tx_hash, str) or not tx_hash.startswith("0x"):
            raise NormalizationError(f"Invalid or missing transaction hash: {tx_hash!r}")

        from_addr = raw.get("from")
        if not is_valid_eth_address(from_addr):
            raise NormalizationError(f"Invalid from_address: {from_addr!r}")

        to_addr = raw.get("to")
        if not is_valid_eth_address(to_addr):
            raise NormalizationError(f"Invalid to_address: {to_addr!r}")

        contract_addr = raw.get("contractAddress")
        if not is_valid_eth_address(contract_addr):
            raise NormalizationError(f"Invalid or missing token contractAddress: {contract_addr!r}")

        token_symbol = str(raw.get("tokenSymbol") or "").strip() or "TOKEN"
        raw_decimals = raw.get("tokenDecimal", 18)
        amount = parse_token_amount(raw.get("value"), token_decimal=raw_decimals)

        utc_dt = parse_unix_timestamp(raw.get("timeStamp"))

        raw_block = raw.get("blockNumber")
        block_number: Optional[int] = None
        if raw_block is not None and str(raw_block).strip():
            try:
                block_number = int(str(raw_block).strip())
            except ValueError:
                raise NormalizationError(f"Malformed block number: {raw_block!r}")

        return NormalizedTransaction(
            chain="ethereum",
            tx_hash=tx_hash,
            from_address=from_addr,
            to_address=to_addr,
            amount=amount,
            asset_symbol=token_symbol,
            timestamp=utc_dt,
            block_number=block_number,
            contract_address=contract_addr.lower() if contract_addr else None,
            source="etherscan",
            raw_ref=tx_hash,
        )

    @classmethod
    def normalize_transaction(cls, raw: Dict[str, Any]) -> NormalizedTransaction:
        """Convert a single raw Etherscan transaction record into a NormalizedTransaction.
        
        Handles both native ETH transfers and ERC-20 token transfers.
        Raises NormalizationError if the transaction is invalid, missing required fields,
        or indicates a failed execution on-chain.
        """
        if not isinstance(raw, dict):
            raise NormalizationError(f"Raw transaction must be a dictionary, got {type(raw).__name__}")

        # If tokenSymbol or tokenDecimal is provided and contractAddress is present, treat as token transfer
        if ("tokenSymbol" in raw or "tokenDecimal" in raw) and raw.get("contractAddress"):
            return cls.normalize_token_transaction(raw)

        # Check for failed transactions
        is_error = str(raw.get("isError", "0")).strip()
        txreceipt_status = str(raw.get("txreceipt_status", "1")).strip()
        if is_error == "1" or txreceipt_status == "0":
            raise NormalizationError("Transaction failed or was reverted on-chain")

        # Required transaction hash
        tx_hash = raw.get("hash")
        if not tx_hash or not isinstance(tx_hash, str) or not tx_hash.startswith("0x"):
            raise NormalizationError(f"Invalid or missing transaction hash: {tx_hash!r}")

        # Addresses
        from_addr = raw.get("from")
        if not is_valid_eth_address(from_addr):
            raise NormalizationError(f"Invalid from_address: {from_addr!r}")

        to_addr = raw.get("to")
        # In contract creations, 'to' may be empty in Etherscan. If 'contractAddress' is present, we check that.
        if not to_addr:
            created_contract = raw.get("contractAddress")
            if is_valid_eth_address(created_contract):
                to_addr = created_contract
            else:
                raise NormalizationError("Transaction missing recipient address ('to' is empty)")
        elif not is_valid_eth_address(to_addr):
            raise NormalizationError(f"Invalid to_address: {to_addr!r}")

        # Value
        amount_eth = parse_wei_to_eth(raw.get("value"))

        # Timestamp
        utc_dt = parse_unix_timestamp(raw.get("timeStamp"))

        # Block Number (optional)
        raw_block = raw.get("blockNumber")
        block_number: Optional[int] = None
        if raw_block is not None and str(raw_block).strip():
            try:
                block_number = int(str(raw_block).strip())
            except ValueError:
                raise NormalizationError(f"Malformed block number: {raw_block!r}")

        contract_addr = raw.get("contractAddress")
        valid_contract = contract_addr if is_valid_eth_address(contract_addr) else None

        return NormalizedTransaction(
            chain="ethereum",
            tx_hash=tx_hash,
            from_address=from_addr,
            to_address=to_addr,
            amount=amount_eth,
            asset_symbol="ETH",
            timestamp=utc_dt,
            block_number=block_number,
            contract_address=valid_contract,
            source="etherscan",
            raw_ref=tx_hash,
        )

