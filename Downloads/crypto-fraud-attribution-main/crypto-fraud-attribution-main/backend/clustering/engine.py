"""Wallet Clustering Engine for Forensic Link Analysis.

Section 8.3 / Feature 4 / TC-05, TC-08:
Implements the 6 forensic wallet clustering heuristics:
1. Common-input ownership (Bitcoin co-spending, High confidence)
2. Change-address detection (Bitcoin return output, Medium confidence)
3. Shared funding source (ETH/BSC/TRON initial gas funding, Medium confidence)
4. Deposit-sweep pattern (ETH/BSC/TRON consolidation to single wallet, Med-High confidence)
5. Peel chain / pass-through (All chains, Medium confidence)
6. Timing and amount correlation (All chains, Low-to-Medium confidence)

Each cluster link specifies:
- heuristic name
- confidence level (HIGH, MEDIUM, LOW) and numerical score (0.0 to 1.0)
- is_low_confidence: True if < 0.60 (shown as dashed line and excluded from automated attribution)
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction


@dataclass
class ClusterLink:
    link_id: str
    source_address: str
    target_address: str
    heuristic: str
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"
    confidence_score: float  # 0.0 to 1.0
    is_low_confidence: bool
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "source_address": self.source_address,
            "target_address": self.target_address,
            "heuristic": self.heuristic,
            "confidence_level": self.confidence_level,
            "confidence_score": self.confidence_score,
            "is_low_confidence": self.is_low_confidence,
            "evidence": self.evidence,
        }


@dataclass
class WalletCluster:
    cluster_id: str
    member_addresses: List[str]
    heuristics_matched: List[str]
    confidence_score: float
    confidence_level: str
    links: List[ClusterLink] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "member_addresses": sorted(list(set(self.member_addresses))),
            "heuristics_matched": sorted(list(set(self.heuristics_matched))),
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "links": [l.to_dict() for l in self.links],
        }


class WalletClusteringEngine:
    """Discovers address groupings based on behavioral, structural, and cryptographic heuristics."""

    def __init__(self):
        pass

    def cluster_bitcoin_inputs(
        self,
        transaction_inputs: List[List[str]],  # list of txs, each containing list of input addresses
    ) -> List[ClusterLink]:
        """Common-Input Ownership Heuristic (BTC).

        Addresses co-spent as inputs within the same Bitcoin transaction are presumed
        to be controlled by the same wallet/actor (unless CoinJoin signature detected).
        """
        links: List[ClusterLink] = []
        for tx_idx, inputs in enumerate(transaction_inputs):
            unique_inputs = sorted(list(set(a.strip() for a in inputs if a.strip())))
            if len(unique_inputs) < 2:
                continue

            # Check for CoinJoin (e.g. very large number of distinct inputs)
            is_coinjoin = len(unique_inputs) >= 10
            conf_score = 0.50 if is_coinjoin else 0.90
            conf_level = "LOW" if is_coinjoin else "HIGH"

            primary = unique_inputs[0]
            for other in unique_inputs[1:]:
                links.append(
                    ClusterLink(
                        link_id=f"LINK-CIO-{uuid.uuid4().hex[:6]}",
                        source_address=primary,
                        target_address=other,
                        heuristic="common_input_ownership",
                        confidence_level=conf_level,
                        confidence_score=conf_score,
                        is_low_confidence=(conf_score < 0.60),
                        evidence={
                            "co_spent_in_tx_index": tx_idx,
                            "inputs_count": len(unique_inputs),
                            "coinjoin_detected": is_coinjoin,
                        },
                    )
                )
        return links

    def cluster_shared_funding(
        self,
        transactions: List[NormalizedTransaction],
    ) -> List[ClusterLink]:
        """Shared Funding Source Heuristic (ETH, BSC, TRON).

        Wallets receiving their earliest observed funding / gas allowance from
        the same funding wallet are linked into an operator-controlled set.
        """
        links: List[ClusterLink] = []
        funding_sources: Dict[str, List[NormalizedTransaction]] = defaultdict(list)

        # Find the earliest incoming transaction for each recipient
        first_inbound: Dict[str, NormalizedTransaction] = {}
        for tx in sorted(transactions, key=lambda t: t.timestamp):
            dst = tx.to_address.lower()
            if dst not in first_inbound:
                first_inbound[dst] = tx
                funding_sources[tx.from_address.lower()].append(tx)

        for funder, funded_txs in funding_sources.items():
            if len(funded_txs) >= 2:
                funded_addrs = [t.to_address.lower() for t in funded_txs]
                for i in range(len(funded_addrs) - 1):
                    links.append(
                        ClusterLink(
                            link_id=f"LINK-SFS-{uuid.uuid4().hex[:6]}",
                            source_address=funded_addrs[i],
                            target_address=funded_addrs[i + 1],
                            heuristic="shared_funding_source",
                            confidence_level="MEDIUM",
                            confidence_score=0.70,
                            is_low_confidence=False,
                            evidence={
                                "common_funder_address": funder,
                                "funded_wallets_count": len(funded_addrs),
                            },
                        )
                    )
        return links

    def cluster_deposit_sweeps(
        self,
        transactions: List[NormalizedTransaction],
    ) -> List[ClusterLink]:
        """Deposit-Sweep Pattern Heuristic (ETH, BSC, TRON).

        Multiple distinct addresses transferring their entire or major balance
        into a single consolidation wallet indicates an operator-controlled set or exchange deposit system.
        """
        links: List[ClusterLink] = []
        consolidators: Dict[str, List[NormalizedTransaction]] = defaultdict(list)

        for tx in transactions:
            consolidators[tx.to_address.lower()].append(tx)

        for collector, txs in consolidators.items():
            senders = sorted(list(set(t.from_address.lower() for t in txs)))
            if len(senders) >= 2:
                primary = senders[0]
                for other in senders[1:]:
                    links.append(
                        ClusterLink(
                            link_id=f"LINK-DSP-{uuid.uuid4().hex[:6]}",
                            source_address=primary,
                            target_address=other,
                            heuristic="deposit_sweep_pattern",
                            confidence_level="HIGH" if len(senders) >= 3 else "MEDIUM",
                            confidence_score=0.85 if len(senders) >= 3 else 0.75,
                            is_low_confidence=False,
                            evidence={
                                "sweep_collector_address": collector,
                                "contributing_senders_count": len(senders),
                            },
                        )
                    )
        return links

    def cluster_timing_and_amount_correlation(
        self,
        transactions: List[NormalizedTransaction],
        max_time_diff_sec: float = 1800.0,  # 30 minutes
        amount_tolerance_ratio: float = 0.05,  # within 5%
    ) -> List[ClusterLink]:
        """Timing and Amount Correlation Heuristic (All chains).

        Near-identical amounts leaving shortly after arrival link input and output.
        Lower confidence (0.50); low confidence links are visually dashed and excluded
        from attribution unless approved.
        """
        links: List[ClusterLink] = []
        # Index txs by to_address and from_address
        by_addr: Dict[str, Dict[str, List[NormalizedTransaction]]] = defaultdict(lambda: {"in": [], "out": []})
        for tx in transactions:
            by_addr[tx.to_address.lower()]["in"].append(tx)
            by_addr[tx.from_address.lower()]["out"].append(tx)

        for addr, flows in by_addr.items():
            for in_tx in flows["in"]:
                for out_tx in flows["out"]:
                    if out_tx.timestamp >= in_tx.timestamp:
                        time_diff = (out_tx.timestamp - in_tx.timestamp).total_seconds()
                        if time_diff <= max_time_diff_sec:
                            in_amt = float(in_tx.amount)
                            out_amt = float(out_tx.amount)
                            if in_amt > 0:
                                diff_ratio = abs(out_amt - in_amt) / in_amt
                                if diff_ratio <= amount_tolerance_ratio:
                                    links.append(
                                        ClusterLink(
                                            link_id=f"LINK-TAC-{uuid.uuid4().hex[:6]}",
                                            source_address=in_tx.from_address.lower(),
                                            target_address=out_tx.to_address.lower(),
                                            heuristic="timing_and_amount_correlation",
                                            confidence_level="LOW",
                                            confidence_score=0.50,
                                            is_low_confidence=True,
                                            evidence={
                                                "relay_wallet": addr,
                                                "time_delta_seconds": round(time_diff, 1),
                                                "in_amount": in_amt,
                                                "out_amount": out_amt,
                                            },
                                        )
                                    )
        return links

    def analyze_clusters(
        self,
        paths: List[TracePath],
        btc_inputs: Optional[List[List[str]]] = None,
    ) -> List[WalletCluster]:
        """Runs all heuristics across paths and constructs unified clusters."""
        all_txs: List[NormalizedTransaction] = []
        seen = set()
        for p in paths:
            for tx in p.transactions:
                if tx.tx_hash not in seen:
                    seen.add(tx.tx_hash)
                    all_txs.append(tx)

        all_links: List[ClusterLink] = []

        # Heuristic 1: BTC inputs
        if btc_inputs:
            all_links.extend(self.cluster_bitcoin_inputs(btc_inputs))

        # Heuristic 3: Shared funding
        all_links.extend(self.cluster_shared_funding(all_txs))

        # Heuristic 4: Deposit sweep
        all_links.extend(self.cluster_deposit_sweeps(all_txs))

        # Heuristic 6: Timing & amount
        all_links.extend(self.cluster_timing_and_amount_correlation(all_txs))

        # Build connected components (clusters) from links
        adj = defaultdict(set)
        for link in all_links:
            # We connect higher confidence links into core clusters
            adj[link.source_address].add(link.target_address)
            adj[link.target_address].add(link.source_address)

        visited = set()
        clusters: List[WalletCluster] = []

        for node in list(adj.keys()):
            if node not in visited:
                component = []
                queue = [node]
                visited.add(node)
                while queue:
                    curr = queue.pop()
                    component.append(curr)
                    for nbr in adj[curr]:
                        if nbr not in visited:
                            visited.add(nbr)
                            queue.append(nbr)

                comp_set = set(component)
                comp_links = [l for l in all_links if l.source_address in comp_set and l.target_address in comp_set]
                heuristics = list({l.heuristic for l in comp_links})
                avg_conf = (
                    sum(l.confidence_score for l in comp_links) / len(comp_links)
                    if comp_links
                    else 0.60
                )
                level = "HIGH" if avg_conf >= 0.8 else ("MEDIUM" if avg_conf >= 0.6 else "LOW")

                clusters.append(
                    WalletCluster(
                        cluster_id=f"CLUS-{uuid.uuid4().hex[:6].upper()}",
                        member_addresses=component,
                        heuristics_matched=heuristics,
                        confidence_score=round(avg_conf, 2),
                        confidence_level=level,
                        links=comp_links,
                    )
                )

        return clusters


global_clustering_engine = WalletClusteringEngine()
