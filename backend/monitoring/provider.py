"""Live transaction provider for the monitoring worker.

Plugs the blockchain connectors into BackgroundMonitoringWorker so monitored cases actually
see new on-chain activity (the worker's built-in default provider returns nothing).
"""

import inspect
import logging
from typing import Callable, Dict, List, Optional, Set, Tuple

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.factory import ConnectorUnavailableError, build_connector

logger = logging.getLogger("crypto_attribution.monitoring_provider")


class ConnectorTransactionProvider:
    """Callable (chain, addresses) -> transactions, backed by the real connectors.

    Remembers the highest block seen per address and only asks the provider for newer blocks,
    so each polling cycle stays small and inside free-tier rate limits. Failures are isolated
    per address: one failing lookup never stops the rest of the cycle.
    """

    def __init__(self, connector_factory: Callable[[str, str], BaseConnector] = build_connector):
        self._factory = connector_factory
        self._last_block: Dict[Tuple[str, str], int] = {}
        self._warned: Set[Tuple[str, str]] = set()

    def _warn_once(self, key: Tuple[str, str], message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(message)

    def __call__(self, chain: str, addresses: List[str]) -> List[NormalizedTransaction]:
        collected: List[NormalizedTransaction] = []
        for address in addresses:
            key = (chain, address.lower())
            try:
                connector = self._factory(chain, address)
            except ConnectorUnavailableError as err:
                self._warn_once(key, f"Monitoring skipped {address} on {chain}: {err}")
                continue

            last = self._last_block.get(key)
            kwargs = {"start_block": last + 1} if last is not None else {}
            try:
                if "include_token_transfers" in inspect.signature(connector.get_transactions).parameters:
                    kwargs["include_token_transfers"] = True
                txs = connector.get_transactions(address, **kwargs)
            except Exception as err:  # noqa: BLE001
                logger.warning("Monitoring fetch failed for %s on %s: %s", address, chain, err)
                continue

            blocks = [t.block_number for t in txs if t.block_number is not None]
            if blocks:
                self._last_block[key] = max(blocks)
            collected.extend(txs)
        return collected
