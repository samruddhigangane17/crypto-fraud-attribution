"""Schemas for explainable risk assessment and attribution confidence.

Rule: Keep risk separate from attribution confidence. A high-risk indicator does
not prove identity or guilt, and a strong address label does not establish who
controlled the funds.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskFactor(BaseModel):
    factor_name: str = Field(..., description="Name of the risk factor, e.g. Mixer Exposure, Proximity to Scam")
    score_contribution: float = Field(..., description="Contribution of this factor to overall risk score (0-100 scale)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Normalized weight assigned to factor")
    triggered: bool = Field(..., description="Whether this factor condition was detected in the trace")
    rationale: str = Field(..., description="Investigative plain-language explanation of why this factor was triggered")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting hashes, addresses, and metrics")


class AttributionConfidenceFactor(BaseModel):
    factor_name: str = Field(..., description="Name of confidence metric, e.g. Label Provenance, Hop Distance")
    score_contribution: float = Field(..., ge=0.0, le=1.0, description="Confidence metric contribution (0.0 to 1.0 scale)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight of confidence factor")
    rationale: str = Field(..., description="Explanation of attribution strength or attenuation")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Direct supporting facts")


class RiskAssessment(BaseModel):
    investigation_id: str
    reported_address: str
    chain: str
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Aggregated risk score from 0 to 100")
    risk_level: RiskLevel
    factors: List[RiskFactor] = Field(default_factory=list)
    summary_rationale: str = Field(..., description="High-level narrative explaining the risk calculation")
    methodology_note: str = Field(
        default="Scoring is rule-based and explainable. A high score flags elevated investigative concern, not criminal guilt."
    )


class AttributionConfidenceAssessment(BaseModel):
    investigation_id: str
    target_address: str
    chain: str
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Attribution confidence score between 0.0 and 1.0")
    confidence_level: ConfidenceLevel
    primary_entity: Optional[str] = None
    primary_category: Optional[str] = None
    factors: List[AttributionConfidenceFactor] = Field(default_factory=list)
    limitations: List[str] = Field(
        default_factory=lambda: [
            "Exchange deposit addresses indicate destination services, not individual depositors.",
            "Intermediate hops may represent non-custodial pass-throughs, aggregation, or unrelated third parties.",
            "Confidence decays over multiple hops due to possible co-mingling."
        ]
    )
