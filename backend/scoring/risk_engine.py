"""Explainable rule-based risk scoring engine.

Rule: Keep risk separate from attribution confidence. A high-risk indicator does
not prove identity or guilt, and a strong address label does not establish who
controlled the funds.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.risk import RiskAssessment, RiskFactor, RiskLevel
from backend.schemas.transaction import TracePath


class RiskScoringEngine:
    """Calculates an explainable risk score from transparent forensic factors."""

    def evaluate_risk(
        self,
        investigation_id: str,
        reported_address: str,
        chain: str,
        paths: List[TracePath],
        matched_endpoints: List[EndpointMatchResult],
        data_completeness: float = 1.0,
    ) -> RiskAssessment:
        factors: List[RiskFactor] = []

        # 1. Mixer / Obfuscation Exposure Factor
        mixer_factor = self._evaluate_mixer_exposure(matched_endpoints)
        factors.append(mixer_factor)

        # 2. Proximity to Known Suspicious / Sanctioned Address
        sanction_factor = self._evaluate_illicit_proximity(matched_endpoints)
        factors.append(sanction_factor)

        # 3. Transaction Velocity / Rapid Dissipation Factor
        velocity_factor = self._evaluate_velocity(paths)
        factors.append(velocity_factor)

        # 4. Verified Service Endpoint Destination
        endpoint_factor = self._evaluate_endpoint_destination(matched_endpoints)
        factors.append(endpoint_factor)

        # 5. Data Completeness Factor
        completeness_factor = self._evaluate_completeness(data_completeness)
        factors.append(completeness_factor)

        # Calculate aggregated score
        total_score = sum(f.score_contribution for f in factors)
        total_score = max(0.0, min(100.0, round(total_score, 1)))

        # Determine Risk Level
        if total_score >= 75.0:
            level = RiskLevel.CRITICAL
        elif total_score >= 50.0:
            level = RiskLevel.HIGH
        elif total_score >= 25.0:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        # Generate human-readable summary narrative
        summary = self._build_summary_narrative(level, total_score, factors)

        return RiskAssessment(
            investigation_id=investigation_id,
            reported_address=reported_address,
            chain=chain,
            overall_score=total_score,
            risk_level=level,
            factors=factors,
            summary_rationale=summary,
        )

    def _evaluate_mixer_exposure(
        self,
        matched_endpoints: List[EndpointMatchResult],
    ) -> RiskFactor:
        mixers = [
            m for m in matched_endpoints
            if m.is_matched and m.label and m.label.entity_category == EntityCategory.MIXER
        ]

        if not mixers:
            return RiskFactor(
                factor_name="Mixer Exposure",
                score_contribution=0.0,
                weight=0.30,
                triggered=False,
                rationale="No interaction with known privacy mixers or coinjoin services detected.",
                evidence={},
            )

        # Sort by nearest hop distance
        closest_hop = min((m.hop_distance or 99) for m in mixers)
        closest_mixer = next(m for m in mixers if (m.hop_distance or 99) == closest_hop)

        if closest_hop <= 1:
            contribution = 30.0
        elif closest_hop == 2:
            contribution = 20.0
        else:
            contribution = 10.0

        return RiskFactor(
            factor_name="Mixer Exposure",
            score_contribution=contribution,
            weight=0.30,
            triggered=True,
            rationale=(
                f"Funds interacted with privacy mixer '{closest_mixer.label.entity_name}' at hop {closest_hop}. "
                "Mixer exposure is an obfuscation indicator, not proof of wrongdoing, but impedes direct tracing."
            ),
            evidence={
                "mixer_name": closest_mixer.label.entity_name,
                "mixer_address": closest_mixer.address,
                "hop_distance": closest_hop,
                "tx_hash": closest_mixer.associated_tx_hash,
            },
        )

    def _evaluate_illicit_proximity(
        self,
        matched_endpoints: List[EndpointMatchResult],
    ) -> RiskFactor:
        illicit_categories = {
            EntityCategory.SANCTIONED,
            EntityCategory.SCAM_FRAUD,
            EntityCategory.HIGH_RISK,
        }
        illicit_matches = [
            m for m in matched_endpoints
            if m.is_matched and m.label and m.label.entity_category in illicit_categories
        ]

        if not illicit_matches:
            return RiskFactor(
                factor_name="Proximity to Flagged Wallets",
                score_contribution=0.0,
                weight=0.35,
                triggered=False,
                rationale="No direct transfer links to known sanctioned, scam, or flagged addresses observed.",
                evidence={},
            )

        closest_hop = min((m.hop_distance or 99) for m in illicit_matches)
        closest = next(m for m in illicit_matches if (m.hop_distance or 99) == closest_hop)

        if closest_hop <= 1:
            contribution = 35.0
        elif closest_hop == 2:
            contribution = 25.0
        else:
            contribution = 15.0

        return RiskFactor(
            factor_name="Proximity to Flagged Wallets",
            score_contribution=contribution,
            weight=0.35,
            triggered=True,
            rationale=(
                f"Direct or multi-hop link to '{closest.label.entity_name}' ({closest.label.entity_category.value}) "
                f"at hop distance {closest_hop}. Shorter transaction distance warrants immediate priority review."
            ),
            evidence={
                "entity_name": closest.label.entity_name,
                "entity_category": closest.label.entity_category.value,
                "address": closest.address,
                "hop_distance": closest_hop,
                "source": closest.label.source,
            },
        )

    def _evaluate_velocity(self, paths: List[TracePath]) -> RiskFactor:
        rapid_hops_count = 0
        min_interval_seconds: Optional[float] = None

        for path in paths:
            if len(path.hops) >= 2:
                for i in range(len(path.hops) - 1):
                    try:
                        ts1 = path.hops[i].transaction.timestamp
                        ts2 = path.hops[i + 1].transaction.timestamp
                        t1 = ts1 if isinstance(ts1, datetime) else datetime.fromisoformat(str(ts1).replace("Z", "+00:00"))
                        t2 = ts2 if isinstance(ts2, datetime) else datetime.fromisoformat(str(ts2).replace("Z", "+00:00"))
                        diff_sec = abs((t2 - t1).total_seconds())
                        if min_interval_seconds is None or diff_sec < min_interval_seconds:
                            min_interval_seconds = diff_sec
                        # If transfer forwarded within 15 minutes (900s)
                        if diff_sec <= 900:
                            rapid_hops_count += 1
                    except Exception:
                        continue

        if rapid_hops_count > 0:
            contribution = min(15.0, 5.0 * rapid_hops_count)
            return RiskFactor(
                factor_name="Transaction Velocity & Rapid Peeling",
                score_contribution=contribution,
                weight=0.15,
                triggered=True,
                rationale=(
                    f"Observed {rapid_hops_count} rapid sequential relay hop(s) occurring within minutes of receipt. "
                    "Rapid pass-through suggests automated peeling or intentional distribution."
                ),
                evidence={
                    "rapid_hops_count": rapid_hops_count,
                    "fastest_transfer_seconds": min_interval_seconds,
                },
            )

        return RiskFactor(
            factor_name="Transaction Velocity & Rapid Peeling",
            score_contribution=0.0,
            weight=0.15,
            triggered=False,
            rationale="Transfer cadence is within standard manual operational intervals.",
            evidence={},
        )

    def _evaluate_endpoint_destination(
        self,
        matched_endpoints: List[EndpointMatchResult],
    ) -> RiskFactor:
        endpoints = [
            m for m in matched_endpoints
            if m.is_matched and m.label and m.label.entity_category in {EntityCategory.EXCHANGE_VASP, EntityCategory.BRIDGE}
        ]

        if not endpoints:
            return RiskFactor(
                factor_name="Service Endpoint Destination",
                score_contribution=0.0,
                weight=0.10,
                triggered=False,
                rationale="No known exchange, VASP, or bridge terminal endpoints identified in current paths.",
                evidence={},
            )

        first_match = endpoints[0]
        return RiskFactor(
            factor_name="Service Endpoint Destination",
            score_contribution=10.0,
            weight=0.10,
            triggered=True,
            rationale=(
                f"Funds traced to verified service endpoint '{first_match.label.entity_name}'. "
                "Documented destination provides an actionable target for legal subpoena or preservation notice."
            ),
            evidence={
                "endpoint_name": first_match.label.entity_name,
                "endpoint_address": first_match.address,
                "category": first_match.label.entity_category.value,
                "hop_distance": first_match.hop_distance,
            },
        )

    def _evaluate_completeness(self, completeness: float) -> RiskFactor:
        completeness = max(0.0, min(1.0, completeness))
        if completeness < 0.70:
            contribution = 10.0
            return RiskFactor(
                factor_name="Data Completeness & Coverage",
                score_contribution=contribution,
                weight=0.10,
                triggered=True,
                rationale=(
                    f"Tracing data completeness is partial ({int(completeness * 100)}%). "
                    "Unresolved branch paths introduce uncertainty into the final attribution."
                ),
                evidence={"completeness_ratio": completeness},
            )

        return RiskFactor(
            factor_name="Data Completeness & Coverage",
            score_contribution=0.0,
            weight=0.10,
            triggered=False,
            rationale=f"High data completeness ({int(completeness * 100)}%). Transaction history is well-resolved.",
            evidence={"completeness_ratio": completeness},
        )

    def _build_summary_narrative(
        self,
        level: RiskLevel,
        score: float,
        factors: List[RiskFactor],
    ) -> str:
        triggered_names = [f.factor_name for f in factors if f.triggered and f.score_contribution > 0]
        if not triggered_names:
            return f"Overall risk assessment is LOW ({score}/100). No anomalous or high-risk indicators were triggered in the traced paths."

        reasons = ", ".join(triggered_names)
        return (
            f"Case evaluated at {level.value} risk level ({score}/100). "
            f"Elevated risk driven by: {reasons}. "
            "Individual factor rationales should be consulted for forensic verification."
        )
