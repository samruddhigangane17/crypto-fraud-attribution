"""Multi-hop transaction tracing engine for cryptocurrency fund flows.

Assumptions & Methodological Limitations:
1. Account-Based Model Fungibility:
   In Ethereum, balances in an account are fungible (unlike UTXO inputs in Bitcoin).
   When an address holds multiple deposits and later sends funds, blockchain data alone
   cannot definitively identify which specific Wei was forwarded.
2. Temporal Causality:
   To trace fund propagation plausibly, outgoing transfers are only followed if they
   occurred at or after the timestamp of incoming funds (t_out >= t_in).
3. No Proof of Ownership:
   Observing that funds moved from Address A to Address B to an exchange does NOT prove
   common ownership or criminal intent. Results represent observed sequential flow paths.
"""

import inspect
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set
import uuid

from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector


class TracingError(Exception):
    """Base exception for tracing operations."""
    pass


class MultiHopTracer:
    """Explores forward transaction paths starting from a reported cryptocurrency address."""

    def __init__(
        self,
        connector: BaseConnector,
        max_hops: int = 5,
        min_amount: Optional[Decimal] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        target_addresses: Optional[Set[str]] = None,
        investigation_id: Optional[str] = None,
        max_paths: int = 100,
        min_taint_share: float = 0.0,
    ):
        """Initialize the tracer.
        
        Args:
            connector: Blockchain connector providing get_transactions(address).
            max_hops: Maximum path depth (must be >= 1).
            min_amount: Optional minimum transfer amount threshold (in Decimal).
            start_time: Optional earliest timestamp for initial outgoing transactions.
            end_time: Optional latest timestamp for outgoing transactions.
            target_addresses: Optional set of known target/exchange addresses to stop expanding once reached.
            investigation_id: Identifier for the investigation case.
            max_paths: Maximum number of paths to collect (guards against combinatorial explosion).
            min_taint_share: Stop following a branch once the share of the first transfer's value
                that can still be traced along it falls below this fraction (0.0 disables pruning).
                Proportional model: tainted value never exceeds the previous hop's tainted value
                or the transfer amount, so share = tainted value / first transfer amount.
        """
        if max_hops < 1:
            raise ValueError(f"max_hops must be at least 1, got {max_hops}")

        if min_amount is not None:
            if isinstance(min_amount, float):
                raise ValueError("min_amount must be a Decimal or string, not a float")
            self.min_amount: Optional[Decimal] = Decimal(str(min_amount))
            if self.min_amount < 0:
                raise ValueError("min_amount cannot be negative")
        else:
            self.min_amount = None

        self.connector = connector
        self.max_hops = max_hops
        self.start_time = start_time
        self.end_time = end_time
        self.target_addresses: Set[str] = {
            a.lower() for a in target_addresses
        } if target_addresses else set()
        self.investigation_id = investigation_id or str(uuid.uuid4())
        self.max_paths = max_paths
        if not 0.0 <= min_taint_share <= 1.0:
            raise ValueError("min_taint_share must be between 0 and 1")
        self.min_taint_share = Decimal(str(min_taint_share))
        self.pruned_low_taint: int = 0

        # Cache connector responses during a trace run to prevent duplicate network calls
        self._tx_cache: Dict[str, List[NormalizedTransaction]] = {}
        self.connector_errors: List[str] = []
        self.cycles_detected: int = 0
        self.intermediate_addresses: Set[str] = set()
        self.discovered_addresses: Set[str] = set()

    def _connector_supports_tokens(self) -> bool:
        """True if the connector's get_transactions accepts include_token_transfers (ERC-20 support)."""
        try:
            return "include_token_transfers" in inspect.signature(self.connector.get_transactions).parameters
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _asset_key(tx: NormalizedTransaction) -> tuple:
        """Identity of the transferred asset: native coin or a specific token contract."""
        return (tx.asset_symbol, (tx.contract_address or "").lower())

    def _fetch_transactions(self, address: str) -> List[NormalizedTransaction]:
        """Fetch transactions for an address using cache, recording errors gracefully."""
        addr_key = address.lower()
        if addr_key in self._tx_cache:
            return self._tx_cache[addr_key]

        try:
            if self._connector_supports_tokens():
                txs = self.connector.get_transactions(address, include_token_transfers=True)
            else:
                txs = self.connector.get_transactions(address)
            self._tx_cache[addr_key] = txs
            return txs
        except Exception as err:
            self.connector_errors.append(f"Failed to fetch transactions for {address}: {err}")
            self._tx_cache[addr_key] = []
            return []

    def trace(self, reported_address: str) -> List[TracePath]:
        """Execute forward multi-hop tracing starting from reported_address.
        
        Returns:
            List of TracePath objects ordered chronologically along each path.
        """
        if not reported_address or not isinstance(reported_address, str):
            raise ValueError(f"Invalid reported_address: {reported_address!r}")

        root_addr = reported_address.lower()
        self._tx_cache.clear()
        self.connector_errors.clear()
        self.cycles_detected = 0
        self.pruned_low_taint = 0
        self.intermediate_addresses = set()
        self.discovered_addresses = {root_addr}

        paths: List[TracePath] = []

        # Each search state represents an in-progress path:
        # (current_address, list_of_transactions_in_path, visited_address_set)
        # Using a queue for Breadth-First exploration
        initial_state = (root_addr, [], {root_addr}, Decimal("0"))
        queue = deque([initial_state])

        while queue and len(paths) < self.max_paths:
            curr_addr, curr_txs, visited, curr_tainted = queue.popleft()
            hop_count = len(curr_txs)

            # If we've reached the maximum allowed hop limit, terminate this path
            if hop_count >= self.max_hops:
                paths.append(
                    TracePath(
                        investigation_id=self.investigation_id,
                        hop_count=hop_count,
                        transactions=curr_txs,
                        end_address=curr_addr,
                    )
                )
                continue

            # If current address is a target endpoint (e.g. exchange) and we have made >=1 hop, stop expanding
            if hop_count > 0 and curr_addr in self.target_addresses:
                paths.append(
                    TracePath(
                        investigation_id=self.investigation_id,
                        hop_count=hop_count,
                        transactions=curr_txs,
                        end_address=curr_addr,
                    )
                )
                continue

            all_txs = self._fetch_transactions(curr_addr)

            # Filter outgoing transactions
            outgoing_candidates: List[NormalizedTransaction] = []
            for tx in all_txs:
                # Must be sent from the current address
                if tx.from_address.lower() != curr_addr:
                    continue

                # Zero-value transfers (e.g. 0 ETH contract calls) move no funds, so never follow them
                if tx.amount <= 0:
                    continue

                # Filter by minimum transfer amount
                if self.min_amount is not None and tx.amount < self.min_amount:
                    continue

                # Filter by upper timestamp bound if specified
                if self.end_time is not None and tx.timestamp > self.end_time:
                    continue

                # Asset continuity: a path follows one asset. ETH arriving and USDT leaving is a
                # different flow (swap/unrelated), and mixing units would corrupt taint maths.
                if curr_txs and self._asset_key(tx) != self._asset_key(curr_txs[0]):
                    continue

                # Temporal causality: funds cannot leave before they arrive
                if curr_txs:
                    last_incoming_tx = curr_txs[-1]
                    if tx.timestamp < last_incoming_tx.timestamp:
                        continue
                elif self.start_time is not None:
                    if tx.timestamp < self.start_time:
                        continue

                outgoing_candidates.append(tx)

            # Sort candidate transactions chronologically for deterministic exploration
            outgoing_candidates.sort(key=lambda t: (t.timestamp, t.block_number or 0, t.tx_hash))

            # Check for dead ends or cycles
            valid_branches = 0
            for tx in outgoing_candidates:
                recipient = tx.to_address.lower()

                # Cycle prevention: if recipient is already visited in this path or self-transfer
                if recipient in visited:
                    self.cycles_detected += 1
                    continue

                # Taint: tainted value can never exceed what arrived or what is sent onward
                new_tainted = tx.amount if not curr_txs else min(tx.amount, curr_tainted)
                first_amount = curr_txs[0].amount if curr_txs else tx.amount
                share = (new_tainted / first_amount) if first_amount > 0 else Decimal("0")
                if share < self.min_taint_share:
                    self.pruned_low_taint += 1
                    continue

                valid_branches += 1
                new_txs = curr_txs + [tx]
                new_visited = visited | {recipient}
                self.discovered_addresses.add(recipient)
                queue.append((recipient, new_txs, new_visited, new_tainted))

            # If no further valid outgoing branches could be taken (terminal node or all cycles):
            if valid_branches == 0:
                if curr_txs:
                    # Completed path reaching a terminal/exchange/dead-end address
                    paths.append(
                        TracePath(
                            investigation_id=self.investigation_id,
                            hop_count=hop_count,
                            transactions=curr_txs,
                            end_address=curr_addr,
                        )
                    )

        # Collect all intermediate addresses across all paths
        for p in paths:
            self.intermediate_addresses.update(p.intermediate_addresses)

        # Sort paths by hop count descending then end address for predictable output
        paths.sort(key=lambda p: (-p.hop_count, p.end_address))
        return paths


    @staticmethod
    def extract_unique_transactions(paths: List[TracePath]) -> List[NormalizedTransaction]:
        """Helper to collect and deduplicate all transactions across paths."""
        seen_hashes: Set[str] = set()
        unique_txs: List[NormalizedTransaction] = []

        for p in paths:
            for tx in p.transactions:
                if tx.tx_hash not in seen_hashes:
                    seen_hashes.add(tx.tx_hash)
                    unique_txs.append(tx)

        return unique_txs
