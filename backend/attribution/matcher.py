"""Endpoint matching module for identifying Exchange/VASP, Mixer, or Flagged entities.

Implements exact lookup, heuristic clustering notes, unknown address handling,
and compliance with forensic attribution caveats.
"""

from typing import List, Optional

from backend.attribution.registry import KnownAddressRegistry, global_registry
from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.transaction import TracePath


class EndpointMatcher:
    """Matches destination addresses and multi-hop paths against known entity registries."""

    def __init__(self, registry: Optional[KnownAddressRegistry] = None):
        self.registry = registry or global_registry

    def match_address(
        self,
        chain: str,
        address: str,
        hop_distance: Optional[int] = None,
        associated_tx_hash: Optional[str] = None,
        include_unverified: bool = False,
    ) -> EndpointMatchResult:
        """Looks up a single address against the registry.

        Unmatched endpoints are marked as UNKNOWN rather than assuming they are suspicious.
        """
        label = self.registry.lookup(chain, address, include_unverified=include_unverified)

        if label:
            match_type = "EXACT" if label.verification_status != "heuristic_cluster" else "HEURISTIC"
            return EndpointMatchResult(
                chain=chain,
                address=address,
                is_matched=True,
                label=label,
                match_type=match_type,
                hop_distance=hop_distance,
                associated_tx_hash=associated_tx_hash,
                investigative_note=(
                    f"Identified {label.entity_name} ({label.entity_category.value}) via {label.source}. "
                    "A known deposit or service address is an investigative lead, not proof of individual depositor identity."
                ),
            )

        # Unmatched address: Mark as unknown rather than suspicious
        return EndpointMatchResult(
            chain=chain,
            address=address,
            is_matched=False,
            label=None,
            match_type="UNKNOWN",
            hop_distance=hop_distance,
            associated_tx_hash=associated_tx_hash,
            investigative_note="Address not matched to any known registry service or cluster. Marked as UNKNOWN.",
        )

    def match_trace_paths(
        self,
        chain: str,
        paths: List[TracePath],
        include_unverified: bool = False,
    ) -> List[EndpointMatchResult]:
        """Analyzes all terminal endpoints and intermediate nodes across traced paths."""
        results: List[EndpointMatchResult] = []
        seen_addresses = set()

        for path in paths:
            # Check terminal address first
            terminal_addr = path.end_address
            if terminal_addr not in seen_addresses:
                seen_addresses.add(terminal_addr)
                last_hop_tx = path.transactions[-1].tx_hash if path.transactions else None
                result = self.match_address(
                    chain=chain,
                    address=terminal_addr,
                    hop_distance=path.hop_count,
                    associated_tx_hash=last_hop_tx,
                    include_unverified=include_unverified,
                )
                results.append(result)

            # Also check intermediate hops for intermediary mixers, bridges, or high-risk stops
            for i, tx in enumerate(path.transactions):
                recipient = tx.to_address
                if recipient not in seen_addresses:
                    seen_addresses.add(recipient)
                    res = self.match_address(
                        chain=chain,
                        address=recipient,
                        hop_distance=i + 1,
                        associated_tx_hash=tx.tx_hash,
                        include_unverified=include_unverified,
                    )
                    if res.is_matched:
                        results.append(res)

        return results

    def filter_by_category(
        self,
        matches: List[EndpointMatchResult],
        category: EntityCategory,
    ) -> List[EndpointMatchResult]:
        """Filters matched endpoints by entity category (e.g. EXCHANGE_VASP or MIXER)."""
        return [
            m for m in matches
            if m.is_matched and m.label and m.label.entity_category == category
        ]
