"""Recoverability Ranking Engine (Advisory).

Section 8.10 / Feature 15 / TC-13:
Ranks every last-observed destination (exchange/VASP or wallet) based on four weighted inputs:
1. Traced amount: Higher amount raises priority.
2. Time since receipt: Recent arrival raises priority (funds more likely reachable).
3. Onward movement: No onward transfer observed raises priority.
4. Attribution confidence: Higher confidence in VASP raises priority for service request.

Output assigns each destination to a prioritised hold-request tier:
- 'Act now' (score >= 70)
- 'Act soon' (score >= 40)
- 'Monitor' (score < 40)

Advisory only. Standard forensic phrasing: 'last observed destination'.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.path import TracePath


class RecoverabilityDestination(BaseModel):
    destination_address: str
    entity_name: str = "Unattributed Wallet"
    entity_category: str = "NON_CUSTODIAL_WALLET"
    traced_amount: float
    asset: str = "ETH"
    received_at: Optional[str] = None
    time_since_receipt_hours: float
    onward_transfer_observed: bool
    attribution_confidence: float
    recoverability_score: float
    tier: str  # "Act now", "Act soon", "Monitor"
    recommended_action: str
    wording_label: str = "last observed destination"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RecoverabilityRankingEngine:
    """Computes actionable recovery rankings for traced endpoints."""

    def __init__(
        self,
        weight_amount: float = 0.35,
        weight_recency: float = 0.25,
        weight_retention: float = 0.25,
        weight_confidence: float = 0.15,
    ):
        self.w_amount = weight_amount
        self.w_recency = weight_recency
        self.w_retention = weight_retention
        self.w_confidence = weight_confidence

    def rank_destinations(
        self,
        paths: List[TracePath],
        endpoints: List[EndpointMatchResult],
        reference_time: Optional[datetime] = None,
    ) -> List[RecoverabilityDestination]:
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        # Map endpoints for fast lookup
        ep_map = {e.address.lower(): e for e in endpoints}

        # Identify terminal destinations across all paths
        # A destination is an end_address of a path
        destination_data: Dict[str, Dict[str, Any]] = {}

        # Check all transactions to see if end_addresses had any outgoing transfer in paths
        all_senders = set()
        for p in paths:
            for tx in p.transactions:
                all_senders.add(tx.from_address.lower())

        for p in paths:
            dest = p.end_address.lower()
            last_tx = p.transactions[-1] if p.transactions else None
            amount = float(last_tx.amount) if last_tx else 0.0
            asset = last_tx.asset_symbol if last_tx else "ETH"
            tx_time = last_tx.timestamp if last_tx else ref_time
            if tx_time.tzinfo is None:
                tx_time = tx_time.replace(tzinfo=timezone.utc)

            if dest not in destination_data:
                destination_data[dest] = {
                    "address": dest,
                    "amount": 0.0,
                    "asset": asset,
                    "latest_tx_time": tx_time,
                    "has_onward": (dest in all_senders),
                }

            destination_data[dest]["amount"] += amount
            if tx_time > destination_data[dest]["latest_tx_time"]:
                destination_data[dest]["latest_tx_time"] = tx_time

        ranked_results: List[RecoverabilityDestination] = []

        # Find max amount for normalization
        max_amount = max((d["amount"] for d in destination_data.values()), default=1.0)
        max_amount = max(max_amount, 0.001)

        for dest_addr, d in destination_data.items():
            ep = ep_map.get(dest_addr)
            entity_name = ep.label.entity_name if (ep and ep.label) else "Unattributed Wallet"
            cat = (
                ep.label.entity_category.value
                if (ep and ep.label and hasattr(ep.label.entity_category, "value"))
                else (str(ep.label.entity_category) if ep and ep.label else "NON_CUSTODIAL_WALLET")
            )
            conf = getattr(ep, "confidence", None)
            if conf is None:
                conf = ep.label.confidence if (ep and ep.label) else 0.2

            # 1. Traced Amount Score (0-100)
            amount_score = min(100.0, (d["amount"] / max_amount) * 100.0)

            # 2. Recency Score (0-100)
            # Within 24 hours: 100, drops down over 14 days
            hours_elapsed = max(0.0, (ref_time - d["latest_tx_time"]).total_seconds() / 3600.0)
            if hours_elapsed <= 24.0:
                recency_score = 100.0
            elif hours_elapsed <= 72.0:
                recency_score = 75.0
            elif hours_elapsed <= 168.0:
                recency_score = 50.0
            elif hours_elapsed <= 336.0:
                recency_score = 25.0
            else:
                recency_score = 10.0

            # 3. Retention / Onward Transfer Score (0-100)
            # If no onward transfer observed, funds are more likely retained at this destination!
            has_onward = d["has_onward"]
            retention_score = 90.0 if not has_onward else 10.0

            # 4. Confidence Score (0-100)
            confidence_score = conf * 100.0

            # Combined weighted score
            total_score = (
                (amount_score * self.w_amount)
                + (recency_score * self.w_recency)
                + (retention_score * self.w_retention)
                + (confidence_score * self.w_confidence)
            )
            total_score = round(max(0.0, min(100.0, total_score)), 1)

            # Tiers
            if total_score >= 70.0:
                tier = "Act now"
                rec_action = f"Immediate hold request / preservation notice to {entity_name}."
            elif total_score >= 40.0:
                tier = "Act soon"
                rec_action = f"Secondary priority request to {entity_name}; monitor for sweeping."
            else:
                tier = "Monitor"
                rec_action = "Funds moved onward or small residual balance. Continue passive surveillance."

            ranked_results.append(
                RecoverabilityDestination(
                    destination_address=dest_addr,
                    entity_name=entity_name,
                    entity_category=cat,
                    traced_amount=round(d["amount"], 4),
                    asset=d["asset"],
                    received_at=d["latest_tx_time"].isoformat(),
                    time_since_receipt_hours=round(hours_elapsed, 1),
                    onward_transfer_observed=has_onward,
                    attribution_confidence=round(conf, 2),
                    recoverability_score=total_score,
                    tier=tier,
                    recommended_action=rec_action,
                )
            )

        # Sort highest score first
        ranked_results.sort(key=lambda r: -r.recoverability_score)
        return ranked_results


global_ranking_engine = RecoverabilityRankingEngine()
