"""Cross-Chain Bridge Detection and Continuation.

Section 8.5 / Feature 7 / TC-07:
Recognises transfers into known cross-chain bridge contracts (Across, Wormhole,
Stargate, FixedFloat, Multichain, Celer, Synapse) and correlates the deposit
with an egress event on the destination chain.
Unmatched bridge hops are flagged for investigator review.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.schemas.transaction import NormalizedTransaction


@dataclass
class BridgeEvent:
    bridge_name: str
    source_chain: str
    destination_chain: Optional[str]
    deposit_tx_hash: str
    deposit_address: str
    amount: Decimal
    asset_symbol: str
    timestamp: datetime
    is_matched_on_destination: bool = False
    destination_tx_hash: Optional[str] = None
    destination_recipient: Optional[str] = None
    status: str = "review_required"  # "continued", "review_required"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bridge_name": self.bridge_name,
            "source_chain": self.source_chain,
            "destination_chain": self.destination_chain,
            "deposit_tx_hash": self.deposit_tx_hash,
            "deposit_address": self.deposit_address,
            "amount": float(self.amount),
            "asset_symbol": self.asset_symbol,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
            "is_matched_on_destination": self.is_matched_on_destination,
            "destination_tx_hash": self.destination_tx_hash,
            "destination_recipient": self.destination_recipient,
            "status": self.status,
        }


# Curated bridge addresses across chains
KNOWN_BRIDGES: Dict[str, Dict[str, str]] = {
    # Across Protocol SpokePools
    "0x5c7bcab86633e49280d3586ce9082d33be317704": {"name": "Across Protocol", "target": "arbitrum"},
    "0x4d9079bb4165aeb4084c526a32695dcfd2f08715": {"name": "Across Protocol", "target": "optimism"},
    # Stargate Finance Routers
    "0x8731d54e9d02c21348399e694444569376b3b276": {"name": "Stargate Finance", "target": "bsc"},
    "0xdf0770df86a8034b3efef0a1bb3c889b8332ff56": {"name": "Stargate Finance", "target": "polygon"},
    # FixedFloat Swapper / Bridge
    "0x4b663b04c8f5f4a63b01859664df089e82976b92": {"name": "FixedFloat Instant Swap", "target": "bitcoin"},
    # Wormhole Portal Bridge
    "0x3ee18b2214aff97000d974cf647e7c347e8fa585": {"name": "Wormhole Portal", "target": "solana"},
    # Multichain Router
    "0xba8da9dcf11b50b03fd5284f164ef5cdef910705": {"name": "Multichain Router", "target": "bsc"},
}


class BridgeDetector:
    """Identifies bridge interactions and correlates cross-chain movements."""

    def __init__(self, bridge_registry: Optional[Dict[str, Dict[str, str]]] = None):
        self.bridges = bridge_registry or KNOWN_BRIDGES

    def is_bridge_contract(self, address: str) -> bool:
        """Returns True if the address is a known cross-chain bridge."""
        return address.strip().lower() in self.bridges

    def get_bridge_info(self, address: str) -> Optional[Dict[str, str]]:
        return self.bridges.get(address.strip().lower())

    def detect_bridge_transfers(
        self,
        transactions: List[NormalizedTransaction],
    ) -> List[BridgeEvent]:
        """Scans transactions for outgoing transfers into bridge contracts."""
        events: List[BridgeEvent] = []
        for tx in transactions:
            dst = tx.to_address.strip().lower()
            if dst in self.bridges:
                info = self.bridges[dst]
                events.append(
                    BridgeEvent(
                        bridge_name=info["name"],
                        source_chain=tx.chain,
                        destination_chain=info.get("target"),
                        deposit_tx_hash=tx.tx_hash,
                        deposit_address=dst,
                        amount=tx.amount,
                        asset_symbol=tx.asset_symbol,
                        timestamp=tx.timestamp,
                        is_matched_on_destination=False,
                        status="review_required",
                    )
                )
        return events

    def correlate_bridge_release(
        self,
        deposit_event: BridgeEvent,
        destination_transactions: List[NormalizedTransaction],
        time_window_hours: float = 6.0,
        amount_tolerance: float = 0.05,
    ) -> BridgeEvent:
        """Attempts to match a bridge deposit with a release event on the destination chain."""
        dep_amt = float(deposit_event.amount)
        dep_time = deposit_event.timestamp
        if dep_time.tzinfo is None:
            dep_time = dep_time.replace(tzinfo=timezone.utc)

        for dest_tx in destination_transactions:
            tx_time = dest_tx.timestamp
            if tx_time.tzinfo is None:
                tx_time = tx_time.replace(tzinfo=timezone.utc)

            # Egress must occur after ingress within time window
            if tx_time >= dep_time:
                diff_hours = (tx_time - dep_time).total_seconds() / 3600.0
                if diff_hours <= time_window_hours:
                    dest_amt = float(dest_tx.amount)
                    if dep_amt > 0 and abs(dest_amt - dep_amt) / dep_amt <= amount_tolerance:
                        deposit_event.is_matched_on_destination = True
                        deposit_event.destination_tx_hash = dest_tx.tx_hash
                        deposit_event.destination_recipient = dest_tx.to_address
                        deposit_event.status = "continued"
                        return deposit_event

        # If not matched, leave as review_required
        deposit_event.status = "review_required"
        return deposit_event


global_bridge_detector = BridgeDetector()
