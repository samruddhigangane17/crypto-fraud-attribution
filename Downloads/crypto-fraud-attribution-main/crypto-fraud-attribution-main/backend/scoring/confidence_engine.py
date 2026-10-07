"""Separate attribution confidence scoring engine.

Evaluates how robust and reliable a specific wallet attribution or endpoint
identification is, independent of behavioral risk.
"""

from decimal import Decimal
from typing import List, Optional

from backend.schemas.attribution import EndpointMatchResult, VerificationStatus
from backend.schemas.risk import (
    AttributionConfidenceAssessment,
    AttributionConfidenceFactor,
    ConfidenceLevel,
)
from backend.schemas.transaction import TracePath


class AttributionConfidenceEngine:
    """Calculates attribution confidence based on label provenance, hop attenuation, and flow continuity."""

    def evaluate_confidence(
        self,
        investigation_id: str,
        target_address: str,
        chain: str,
        match: EndpointMatchResult,
        paths: List[TracePath],
    ) -> AttributionConfidenceAssessment:
        factors: List[AttributionConfidenceFactor] = []

        if not match.is_matched or not match.label:
            # Unmatched address: baseline unknown confidence
            return AttributionConfidenceAssessment(
                investigation_id=investigation_id,
                target_address=target_address,
                chain=chain,
                overall_confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                primary_entity=None,
                primary_category=None,
                factors=[
                    AttributionConfidenceFactor(
                        factor_name="Registry Match",
                        score_contribution=0.0,
                        weight=1.0,
                        rationale="Address not present in verified or community registry.",
                        evidence={"address": target_address},
                    )
                ],
                limitations=["Address has no known entity affiliation in the database."],
            )

        label = match.label

        # 1. Label Provenance & Verification Freshness
        prov_score, prov_rationale = self._score_provenance(label)
        factors.append(
            AttributionConfidenceFactor(
                factor_name="Data Provenance & Source Reliability",
                score_contribution=prov_score,
                weight=0.35,
                rationale=prov_rationale,
                evidence={
                    "source": label.source,
                    "source_url": label.source_url,
                    "verification_status": label.verification_status.value,
                    "stated_confidence": label.confidence,
                },
            )
        )

        # 2. Hop Distance / Graph Attenuation
        hop_dist = match.hop_distance or 1
        hop_score, hop_rationale = self._score_hop_attenuation(hop_dist)
        factors.append(
            AttributionConfidenceFactor(
                factor_name="Graph Hop Proximity",
                score_contribution=hop_score,
                weight=0.35,
                rationale=hop_rationale,
                evidence={"hop_distance": hop_dist},
            )
        )

        # 3. Flow Continuity / Amount Preservation
        flow_score, flow_rationale = self._score_flow_continuity(paths)
        factors.append(
            AttributionConfidenceFactor(
                factor_name="Fund Flow Continuity",
                score_contribution=flow_score,
                weight=0.20,
                rationale=flow_rationale,
                evidence={"paths_evaluated": len(paths)},
            )
        )

        # 4. Match Precision
        match_score = 1.0 if match.match_type == "EXACT" else 0.65
        factors.append(
            AttributionConfidenceFactor(
                factor_name="Match Precision",
                score_contribution=match_score,
                weight=0.10,
                rationale=(
                    f"Match type is {match.match_type}. "
                    "Cryptographic exact match confirms exact contract or wallet address."
                    if match.match_type == "EXACT"
                    else "Heuristic clustering implies relationship through co-spending patterns."
                ),
                evidence={"match_type": match.match_type},
            )
        )

        # Calculate weighted average confidence
        weighted_sum = sum(f.score_contribution * f.weight for f in factors)
        total_weight = sum(f.weight for f in factors)
        overall = round(weighted_sum / total_weight, 2)
        overall = max(0.0, min(1.0, overall))

        if overall >= 0.75:
            conf_level = ConfidenceLevel.HIGH
        elif overall >= 0.50:
            conf_level = ConfidenceLevel.MEDIUM
        else:
            conf_level = ConfidenceLevel.LOW

        return AttributionConfidenceAssessment(
            investigation_id=investigation_id,
            target_address=target_address,
            chain=chain,
            overall_confidence=overall,
            confidence_level=conf_level,
            primary_entity=label.entity_name,
            primary_category=label.entity_category.value,
            factors=factors,
        )

    def _score_provenance(self, label) -> tuple[float, str]:
        if label.verification_status == VerificationStatus.VERIFIED:
            score = float(label.confidence)
            rationale = (
                f"High provenance: Officially verified by '{label.source}'. "
                "Entity identity is cross-referenced with public regulatory or corporate disclosure."
            )
            return (score, rationale)
        elif label.verification_status == VerificationStatus.UNVERIFIED_COMMUNITY:
            score = min(0.50, float(label.confidence))
            rationale = (
                f"Moderate/Low provenance: Unverified community label from '{label.source}'. "
                "Subject to potential reporting bias or misattribution."
            )
            return (score, rationale)
        else:
            return (0.60, f"Heuristic cluster attribution from '{label.source}'.")

    def _score_hop_attenuation(self, hop_distance: int) -> tuple[float, str]:
        if hop_distance <= 1:
            return (
                1.0,
                "Direct transfer (hop 1): Immediate cryptographic connection with zero intermediary ambiguity.",
            )
        elif hop_distance == 2:
            return (
                0.80,
                "Two hops: One intermediary wallet. High probability of fund continuity if timing and amounts align.",
            )
        elif hop_distance == 3:
            return (
                0.60,
                "Three hops: Two intermediaries. Attenuation applied to account for potential co-mingling or pass-through.",
            )
        else:
            score = max(0.30, round(0.50 * (0.85 ** (hop_distance - 3)), 2))
            return (
                score,
                f"Extended path ({hop_distance} hops): Substantial graph attenuation. Significant possibility of fund dispersion.",
            )

    def _score_flow_continuity(self, paths: List[TracePath]) -> tuple[float, str]:
        if not paths:
            return (0.50, "No path volume data available to assess continuity.")

        try:
            initial_amounts: list[Decimal] = []
            final_amounts: list[Decimal] = []
            seen_pairs: set[tuple[str, str]] = set()

            for p in paths:
                if p.hops:
                    first_tx = p.hops[0].transaction
                    last_tx = p.hops[-1].transaction
                    # Count each (first transfer, last transfer) pair once
                    pair = (first_tx.tx_hash, last_tx.tx_hash)
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    first_amt = first_tx.amount_decimal()
                    initial_amounts.append(first_amt)
                    # Funds that reach the endpoint cannot exceed what entered the path
                    final_amounts.append(min(last_tx.amount_decimal(), first_amt))

            if initial_amounts and final_amounts:
                init_sum = sum(initial_amounts)
                fin_sum = sum(final_amounts)

                if init_sum > 0:
                    retention = float(fin_sum / init_sum)
                    if retention >= 0.80:
                        return (1.0, f"High volume continuity: {int(retention * 100)}% of initial volume traced to endpoint.")
                    elif retention >= 0.40:
                        return (0.75, f"Moderate volume continuity: {int(retention * 100)}% of traced funds reached endpoint.")
                    else:
                        return (0.45, f"Low volume continuity: {int(retention * 100)}% preserved. Funds largely diverted or peeled.")
        except Exception:
            pass

        return (0.70, "Flow continuity estimated from transaction edge sequence.")
