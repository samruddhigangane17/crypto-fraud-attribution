"""Context Filter for innocent-until-contextualised laundering detection.

Section 8.15 / Feature 20:
Recognises legitimate high-volume entities (exchange hot wallets, payment processors,
popular protocol contracts, known bridge routers) and prevents them from being falsely scored
as illicit laundering/peel-chain wallets. Records each exclusion decision with justification
for complete investigative auditability.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from backend.attribution.registry import KnownAddressRegistry, global_registry
from backend.schemas.attribution import EntityCategory


@dataclass
class ContextFilterDecision:
    address: str
    entity_name: str
    category: str
    is_excluded_from_laundering: bool
    reason: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "entity_name": self.entity_name,
            "category": self.category,
            "is_excluded_from_laundering": self.is_excluded_from_laundering,
            "reason": self.reason,
            "evidence": self.evidence,
        }


class ContextFilter:
    """Filters high-volume legitimate infrastructure to reduce false laundering flags."""

    # Entities that inherently demonstrate heavy fan-in, fan-out, and pass-through
    LEGITIMATE_HIGH_VOLUME_CATEGORIES = {
        EntityCategory.EXCHANGE_VASP,
        EntityCategory.BRIDGE,
    }

    # Known high-volume protocol addresses / DEX routers / payment processors
    KNOWN_HIGH_VOLUME_CONTRACTS: Set[str] = {
        # Uniswap Universal Router & V3 / V2 Routers
        "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad",
        "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b",
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",
        "0xe592427a0aece92de3edee1f18e0157c05861564",
        # 1inch Aggregator
        "0x1111111254eeb25477b68fb85ed929f73a960582",
        "0x111111125421ca6dc452d289314280a0f8842a65",
        # Curve 3pool / stETH Pool
        "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7",
        "0xdc24316b9ae028f1497c275eb9192a3ea0f67022",
    }

    def __init__(self, registry: Optional[KnownAddressRegistry] = None):
        self.registry = registry or global_registry
        self._decisions: Dict[str, ContextFilterDecision] = {}

    def evaluate_address(
        self,
        address: str,
        chain: str = "ethereum",
        historical_volume: Optional[float] = None,
        observed_fan_out: Optional[int] = None,
    ) -> ContextFilterDecision:
        """Evaluate if an address should be excluded from laundering behavior flags."""
        addr_lower = address.strip().lower()

        # 1. Check verified label in known registry
        label = self.registry.lookup(chain=chain, address=addr_lower)
        if label:
            cat = label.entity_category
            if cat in self.LEGITIMATE_HIGH_VOLUME_CATEGORIES:
                decision = ContextFilterDecision(
                    address=addr_lower,
                    entity_name=label.entity_name,
                    category=cat.value if hasattr(cat, "value") else str(cat),
                    is_excluded_from_laundering=True,
                    reason=(
                        f"Recognised as legitimate high-volume entity ({label.entity_name}). "
                        "Fan-out, fan-in, and rapid throughput are standard operational baselines for this VASP/service."
                    ),
                    evidence={
                        "source": label.source,
                        "confidence": label.confidence,
                        "category": cat.value if hasattr(cat, "value") else str(cat),
                    },
                )
                self._decisions[addr_lower] = decision
                return decision

        # 2. Check known high-volume DEX routers / protocol contracts
        if addr_lower in self.KNOWN_HIGH_VOLUME_CONTRACTS:
            decision = ContextFilterDecision(
                address=addr_lower,
                entity_name="Known High-Volume DeFi Protocol Contract",
                category="DEFI_PROTOCOL",
                is_excluded_from_laundering=True,
                reason="Recognised automated routing contract with legitimate high throughput.",
                evidence={"contract_type": "DEX_ROUTER_OR_AGGREGATOR"},
            )
            self._decisions[addr_lower] = decision
            return decision

        # 3. Not excluded (subject to standard laundering analysis)
        decision = ContextFilterDecision(
            address=addr_lower,
            entity_name="Non-exempt Participant",
            category="UNCLASSIFIED",
            is_excluded_from_laundering=False,
            reason="Address does not match recognized high-volume institutional infrastructure.",
            evidence={"historical_volume": historical_volume, "fan_out": observed_fan_out},
        )
        self._decisions[addr_lower] = decision
        return decision

    def is_suppressed(self, address: str, chain: str = "ethereum") -> bool:
        """Convenience method returning True if address is excluded from laundering scoring."""
        decision = self.evaluate_address(address, chain=chain)
        return decision.is_excluded_from_laundering

    def get_decisions(self) -> List[Dict[str, Any]]:
        """Return all recorded filter decisions for audit logging."""
        return [d.to_dict() for d in self._decisions.values()]


global_context_filter = ContextFilter()
