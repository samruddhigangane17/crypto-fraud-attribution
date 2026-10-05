"""Schemas for investigation evidence report generation and metadata."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.schemas.attribution import EndpointMatchResult
from backend.schemas.risk import AttributionConfidenceAssessment, RiskAssessment
from backend.schemas.transaction import TracePath
from backend.schemas.monitoring import Alert


SAFE_HANDLING_ADVISORY = (
    "SAFE-HANDLING ADVISORY: Law enforcement officials, regulatory bodies, and genuine recovery processes "
    "never ask a victim for private keys, seed phrases, OTPs, or upfront recovery fees. "
    "Anyone asking for fees or private credentials claiming to be a 'recovery agent' is engaging in fraud."
)


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
    # Golden Hour Recovery Layer extensions
    typology: Optional[Dict[str, Any]] = None
    recoverability_ranking: Optional[List[Dict[str, Any]]] = None
    recovery_clock: Optional[List[Dict[str, Any]]] = None
    convergence_links: Optional[List[Dict[str, Any]]] = None
    case_summary: Optional[Dict[str, Any]] = None
    audit_trail: Optional[List[Dict[str, Any]]] = None
    clustering_findings: Optional[List[Dict[str, Any]]] = None


class EvidenceReportMetadata(BaseModel):
    report_id: str
    investigation_id: str
    filename: str
    file_size_bytes: int
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    storage_path: str
    download_url: Optional[str] = None
    report_hash: Optional[str] = None
    format: str = "pdf"
    safe_handling_advisory: str = SAFE_HANDLING_ADVISORY
