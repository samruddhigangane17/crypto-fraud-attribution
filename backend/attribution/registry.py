"""Known-address registry with strict separation of verified and community labels.

Includes data provenance fields: source, source URL, verification status,
timestamp, and confidence score.
"""

from typing import Dict, List, Optional, Tuple
import uuid

import os
from backend.attribution.seed_data import (
    DEMO_LABELS,
    SEED_UNVERIFIED_COMMUNITY_LABELS,
    SEED_VERIFIED_LABELS,
)
from backend.schemas.attribution import (
    AddressLabel,
    AddressLabelCreate,
    EntityCategory,
    VerificationStatus,
)


class KnownAddressRegistry:
    """Manages verified address labels and unverified community labels.

    Maintains two separate internal indexes to guarantee that unverified
    community data is never conflated with verified regulatory or official data.
    """

    def __init__(self, load_seed_data: bool = True):
        # Key: (chain.lower(), normalized_address)
        self._verified_labels: Dict[Tuple[str, str], AddressLabel] = {}
        self._community_labels: Dict[Tuple[str, str], AddressLabel] = {}

        if load_seed_data:
            self._load_seeds()

    def _normalize_key(self, chain: str, address: str) -> Tuple[str, str]:
        """Normalizes lookup keys.

        EVM addresses (ETH, BSC) are lowercased; UTXO (BTC) and TRON addresses
        are stripped but case-preserved when case-sensitive.
        """
        c = chain.strip().lower()
        a = address.strip()
        if c in ["ethereum", "eth", "bsc", "binance-smart-chain", "polygon", "arbitrum"]:
            a = a.lower()
        return (c, a)

    def _load_seeds(self) -> None:
        for item in SEED_VERIFIED_LABELS:
            key = self._normalize_key(item.chain, item.address)
            self._verified_labels[key] = item

        if os.getenv("ENABLE_DEMO_CASES", "true").lower() in ("true", "1", "yes"):
            for item in DEMO_LABELS:
                self._verified_labels[self._normalize_key(item.chain, item.address)] = item

        for item in SEED_UNVERIFIED_COMMUNITY_LABELS:
            key = self._normalize_key(item.chain, item.address)
            self._community_labels[key] = item

    def lookup(
        self,
        chain: str,
        address: str,
        include_unverified: bool = False,
    ) -> Optional[AddressLabel]:
        """Looks up an address in the registry.

        Verified labels are always checked first. Unverified community labels
        are only checked if explicitly requested.
        """
        key = self._normalize_key(chain, address)

        # 1. Check verified registry first
        if key in self._verified_labels:
            return self._verified_labels[key]

        # 2. Check community registry only if requested
        if include_unverified and key in self._community_labels:
            return self._community_labels[key]

        return None

    def register(self, payload: AddressLabelCreate) -> AddressLabel:
        """Registers a new address label with data provenance metadata."""
        record_id = str(uuid.uuid4())
        label = AddressLabel(
            id=record_id,
            chain=payload.chain.lower(),
            address=payload.address.strip(),
            entity_name=payload.entity_name.strip(),
            entity_category=payload.entity_category,
            source=payload.source.strip(),
            source_url=payload.source_url,
            confidence=payload.confidence,
            verification_status=payload.verification_status,
            notes=payload.notes,
        )
        key = self._normalize_key(label.chain, label.address)

        if label.verification_status == VerificationStatus.VERIFIED:
            self._verified_labels[key] = label
        else:
            self._community_labels[key] = label

        return label

    def search(
        self,
        query: str,
        chain: Optional[str] = None,
        category: Optional[EntityCategory] = None,
        include_unverified: bool = False,
    ) -> List[AddressLabel]:
        """Search records by entity name, address fragment, or category."""
        q = query.strip().lower()
        results: List[AddressLabel] = []

        pool = list(self._verified_labels.values())
        if include_unverified:
            pool.extend(self._community_labels.values())

        for label in pool:
            if chain and label.chain.lower() != chain.lower():
                continue
            if category and label.entity_category != category:
                continue

            if q in label.address.lower() or q in label.entity_name.lower():
                results.append(label)

        return results

    def get_all(self, include_unverified: bool = False) -> List[AddressLabel]:
        """Returns all registered address labels."""
        labels = list(self._verified_labels.values())
        if include_unverified:
            labels.extend(self._community_labels.values())
        return labels

    def get_stats(self) -> dict:
        return {
            "verified_count": len(self._verified_labels),
            "unverified_community_count": len(self._community_labels),
            "total_count": len(self._verified_labels) + len(self._community_labels),
        }


# Global singleton instance for easy import across modules
global_registry = KnownAddressRegistry(load_seed_data=True)
