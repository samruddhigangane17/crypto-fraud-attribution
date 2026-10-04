"""Assessment request and response schemas for real trace path evaluations."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.schemas.attribution import EndpointMatchResult
from backend.schemas.monitoring import Alert
from backend.schemas.risk import AttributionConfidenceAssessment, RiskAssessment
from backend.schemas.transaction import TracePath


class InvestigationAssessRequest(BaseModel):
    chain: str = Field(..., description="Target blockchain, e.g. ethereum, bitcoin, tron, bsc")
    reported_address: str = Field(..., description="Reported suspicious wallet address")
    paths: List[TracePath] = Field(..., description="List of traced paths output by Member 1's tracing engine")
    investigator_name: Optional[str] = "Lead Investigator"
    include_unverified_labels: bool = False
    data_completeness: float = Field(default=1.0, ge=0.0, le=1.0)
    missing_data_notes: Optional[str] = None
    investigator_notes: Optional[str] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None


class AssessmentResponse(BaseModel):
    investigation_id: str
    chain: str
    reported_address: str
    risk_assessment: RiskAssessment
    attribution_confidence: AttributionConfidenceAssessment
    endpoints: List[EndpointMatchResult]
    alerts_generated: List[Alert]
    assessed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
