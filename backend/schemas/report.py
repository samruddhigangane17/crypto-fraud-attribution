"""Schemas for investigation evidence report generation and metadata."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.schemas.attribution import EndpointMatchResult
from backend.schemas.risk import AttributionConfidenceAssessment, RiskAssessment
from backend.schemas.transaction import TracePath
from backend.schemas.monitoring import Alert


class EvidenceReportRequest(BaseModel):
    investigation_id: str
    reported_wallet: str
    chain: str
    investigator_name: str = "Lead Investigator"
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    paths: List[TracePath] = Field(default_factory=list)
    endpoints: List[EndpointMatchResult] = Field(default_factory=list)
    risk_assessment: Optional[RiskAssessment] = None
    confidence_assessment: Optional[AttributionConfidenceAssessment] = None
    alerts: List[Alert] = Field(default_factory=list)
    missing_data_notes: Optional[str] = None
    investigator_notes: Optional[str] = None


class EvidenceReportMetadata(BaseModel):
    report_id: str
    investigation_id: str
    filename: str
    file_size_bytes: int
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    storage_path: str
    download_url: Optional[str] = None
