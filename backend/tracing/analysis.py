"""Wallet relationship analysis and structural graph metrics.

Calculates fan-in, fan-out, degree statistics, transaction volumes,
and pass-through timing from observed cryptocurrency transactions.

Important Investigative Notice:
Relationship metrics describe observed topological graph patterns (e.g. dispersion,
aggregation, and rapid forwarding). They DO NOT prove illicit intent, criminal conspiracy,
or entity ownership. Outputs should be treated as structural observations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import networkx as nx

from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.graph import FlowGraphBuilder


@dataclass
class WalletMetrics:
    """Structural relationship metrics for a single wallet address."""

    address: str
    in_degree: int = 0
    out_degree: int = 0
    fan_in: int = 0  # Number of distinct sender addresses
    fan_out: int = 0  # Number of distinct recipient addresses
    total_received: Decimal = Decimal("0")
    total_sent: Decimal = Decimal("0")
    net_flow: Decimal = Decimal("0")  # total_received - total_sent
    senders: Set[str] = field(default_factory=set)
    recipients: Set[str] = field(default_factory=set)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_rapid_pass_through: bool = False
    pass_through_duration_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a JSON-compatible dictionary."""
        return {
            "address": self.address,
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
            "fan_in": self.fan_in,
            "fan_out": self.fan_out,
            "total_received": float(self.total_received),
            "total_sent": float(self.total_sent),
            "net_flow": float(self.net_flow),
            "senders": sorted(list(self.senders)),
            "recipients": sorted(list(self.recipients)),
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_rapid_pass_through": self.is_rapid_pass_through,
            "pass_through_duration_seconds": self.pass_through_duration_seconds,
        }


class WalletRelationshipAnalyzer:
    """Analyzes transaction flows and calculates graph relationship metrics."""

    def __init__(self, transactions: Optional[List[NormalizedTransaction]] = None):
        """Initialize the analyzer with a list of transactions."""
        self.transactions: List[NormalizedTransaction] = []
        # Grouped records per address for fast lookup
        self._incoming: Dict[str, List[NormalizedTransaction]] = {}
        self._outgoing: Dict[str, List[NormalizedTransaction]] = {}
        self._all_addresses: Set[str] = set()

        if transactions:
            self.load_transactions(transactions)

    def load_transactions(self, transactions: List[NormalizedTransaction]) -> None:
        """Load and index transactions by wallet address."""
        seen_tx_hashes: Set[str] = set()

        for tx in transactions:
            # Deduplicate by tx_hash to avoid double-counting parallel/repeated path edges
            if tx.tx_hash in seen_tx_hashes:
                continue
            seen_tx_hashes.add(tx.tx_hash)
            self.transactions.append(tx)

            src = tx.from_address.lower()
            dst = tx.to_address.lower()
            self._all_addresses.add(src)
            self._all_addresses.add(dst)

            if src not in self._outgoing:
                self._outgoing[src] = []
            self._outgoing[src].append(tx)

            if dst not in self._incoming:
                self._incoming[dst] = []
            self._incoming[dst].append(tx)

    @classmethod
    def from_paths(cls, paths: List[TracePath]) -> "WalletRelationshipAnalyzer":
        """Instantiate analyzer from a collection of TracePath objects."""
        all_txs: List[NormalizedTransaction] = []
        for p in paths:
            all_txs.extend(p.transactions)
        return cls(transactions=all_txs)

    @classmethod
    def from_graph(cls, builder_or_graph: Union[FlowGraphBuilder, nx.MultiDiGraph]) -> "WalletRelationshipAnalyzer":
        """Instantiate analyzer from a FlowGraphBuilder or NetworkX MultiDiGraph."""
        if isinstance(builder_or_graph, FlowGraphBuilder):
            graph = builder_or_graph.graph
        else:
            graph = builder_or_graph

        txs: List[NormalizedTransaction] = []
        for u, v, key, data in graph.edges(keys=True, data=True):
            txs.append(
                NormalizedTransaction(
                    chain=data.get("chain", "ethereum"),
                    tx_hash=data.get("tx_hash", key),
                    from_address=u,
                    to_address=v,
                    amount=data.get("amount", Decimal("0")),
                    asset_symbol=data.get("asset", "ETH"),
                    timestamp=data.get("timestamp", datetime.now()),
                    block_number=data.get("block_number"),
                    source=data.get("source", "graph"),
                )
            )
        return cls(transactions=txs)

    def calculate_pass_through(
        self,
        address: str,
        max_window_seconds: float = 86400.0,
    ) -> Tuple[bool, Optional[float]]:
        """Determine if an address exhibits rapid pass-through behavior.
        
        A wallet exhibits pass-through if it receives funds and subsequently
        forwards funds within max_window_seconds (t_out >= t_in and t_out - t_in <= window).
        
        Returns:
            (is_rapid_pass_through, minimum_pass_through_duration_seconds)
        """
        addr = address.lower()
        incoming = self._incoming.get(addr, [])
        outgoing = self._outgoing.get(addr, [])

        if not incoming or not outgoing:
            return False, None

        min_duration: Optional[float] = None

        for in_tx in incoming:
            for out_tx in outgoing:
                if out_tx.timestamp >= in_tx.timestamp:
                    diff_seconds = (out_tx.timestamp - in_tx.timestamp).total_seconds()
                    if diff_seconds <= max_window_seconds:
                        if min_duration is None or diff_seconds < min_duration:
                            min_duration = diff_seconds

        if min_duration is not None:
            return True, min_duration

        return False, None

    def analyze_wallet(
        self,
        address: str,
        max_pass_through_seconds: float = 86400.0,
    ) -> WalletMetrics:
        """Compute full relationship metrics for a specific wallet address."""
        addr = address.lower()
        incoming = self._incoming.get(addr, [])
        outgoing = self._outgoing.get(addr, [])

        in_degree = len(incoming)
        out_degree = len(outgoing)

        senders: Set[str] = {tx.from_address.lower() for tx in incoming}
        recipients: Set[str] = {tx.to_address.lower() for tx in outgoing}

        fan_in = len(senders)
        fan_out = len(recipients)

        # Precise Decimal summing without floats
        total_received = sum((tx.amount for tx in incoming), Decimal("0"))
        total_sent = sum((tx.amount for tx in outgoing), Decimal("0"))
        net_flow = total_received - total_sent

        # Timestamps
        all_timestamps = [tx.timestamp for tx in incoming + outgoing]
        first_seen = min(all_timestamps) if all_timestamps else None
        last_seen = max(all_timestamps) if all_timestamps else None

        # Pass-through detection
        is_pass_through, duration = self.calculate_pass_through(
            addr, max_window_seconds=max_pass_through_seconds
        )

        return WalletMetrics(
            address=addr,
            in_degree=in_degree,
            out_degree=out_degree,
            fan_in=fan_in,
            fan_out=fan_out,
            total_received=total_received,
            total_sent=total_sent,
            net_flow=net_flow,
            senders=senders,
            recipients=recipients,
            first_seen=first_seen,
            last_seen=last_seen,
            is_rapid_pass_through=is_pass_through,
            pass_through_duration_seconds=duration,
        )

    def analyze_all(
        self,
        max_pass_through_seconds: float = 86400.0,
    ) -> Dict[str, WalletMetrics]:
        """Compute relationship metrics for all wallets present in the dataset."""
        return {
            addr: self.analyze_wallet(addr, max_pass_through_seconds=max_pass_through_seconds)
            for addr in sorted(self._all_addresses)
        }

    def detect_fan_out_wallets(self, min_recipients: int = 2) -> List[Tuple[str, int]]:
        """Identify wallets dispersing funds to multiple distinct recipients (peeling/dispersion)."""
        results: List[Tuple[str, int]] = []
        for addr, txs in self._outgoing.items():
            distinct_recipients = {tx.to_address.lower() for tx in txs}
            if len(distinct_recipients) >= min_recipients:
                results.append((addr, len(distinct_recipients)))
        results.sort(key=lambda x: -x[1])
        return results

    def detect_fan_in_wallets(self, min_senders: int = 2) -> List[Tuple[str, int]]:
        """Identify wallets receiving funds from multiple distinct senders (consolidation/aggregation)."""
        results: List[Tuple[str, int]] = []
        for addr, txs in self._incoming.items():
            distinct_senders = {tx.from_address.lower() for tx in txs}
            if len(distinct_senders) >= min_senders:
                results.append((addr, len(distinct_senders)))
        results.sort(key=lambda x: -x[1])
        return results

    def detect_rapid_pass_through_wallets(
        self,
        max_window_seconds: float = 7200.0,
    ) -> List[Tuple[str, float]]:
        """Identify wallets that quickly forward received funds within the time threshold."""
        results: List[Tuple[str, float]] = []
        for addr in self._all_addresses:
            is_rapid, duration = self.calculate_pass_through(
                addr, max_window_seconds=max_window_seconds
            )
            if is_rapid and duration is not None:
                results.append((addr, duration))
        results.sort(key=lambda x: x[1])
        return results

    def get_summary(
        self,
        max_pass_through_seconds: float = 86400.0,
    ) -> Dict[str, Any]:
        """Generate high-level summary statistics of the observed network."""
        all_metrics = self.analyze_all(max_pass_through_seconds=max_pass_through_seconds)

        total_volume = sum((m.total_sent for m in all_metrics.values()), Decimal("0"))
        pass_through_wallets = [
            addr for addr, m in all_metrics.items() if m.is_rapid_pass_through
        ]

        return {
            "total_wallets": len(self._all_addresses),
            "total_transactions": len(self.transactions),
            "total_transferred_volume": float(total_volume),
            "rapid_pass_through_wallets": pass_through_wallets,
            "fan_out_wallets": self.detect_fan_out_wallets(min_recipients=2),
            "fan_in_wallets": self.detect_fan_in_wallets(min_senders=2),
            "wallets": {addr: m.to_dict() for addr, m in all_metrics.items()},
        }
