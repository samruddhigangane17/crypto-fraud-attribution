"""Investigation repository interface with Supabase bridge and in-memory fallback.

Coordinates with Member 3's Supabase tables (investigations, risk_assessments,
evidence_reports) and Supabase Storage bucket ('evidence-reports').
"""

import logging
from typing import Dict, List, Optional
import uuid

from fastapi.encoders import jsonable_encoder

from backend.database.supabase_client import SupabaseClient, global_supabase_client
from backend.schemas.assessment import AssessmentResponse
from backend.schemas.monitoring import Alert
from backend.schemas.report import EvidenceReportMetadata, EvidenceReportRequest
from backend.schemas.risk import AttributionConfidenceAssessment, RiskAssessment

logger = logging.getLogger("crypto_attribution.repository")


class InvestigationRepository:
    """Repository handling investigations, assessments, alerts, and reports."""

    def __init__(self, supabase: Optional[SupabaseClient] = None):
        self.supabase = supabase or global_supabase_client
        # In-memory persistence for prototype / local execution
        self._investigations: Dict[str, EvidenceReportRequest] = {}
        self._risk_assessments: Dict[str, RiskAssessment] = {}
        self._confidence_assessments: Dict[str, AttributionConfidenceAssessment] = {}
        self._evidence_reports: Dict[str, EvidenceReportMetadata] = {}

    def save_assessment(
        self,
        investigation_id: str,
        case_dossier: EvidenceReportRequest,
        risk: RiskAssessment,
        confidence: AttributionConfidenceAssessment,
        persist_remote: bool = True,
    ) -> None:
        """Stores assessment results locally and writes them through to Supabase if configured."""
        self._investigations[investigation_id] = case_dossier
        self._risk_assessments[investigation_id] = risk
        self._confidence_assessments[investigation_id] = confidence

        if persist_remote and self.supabase.is_configured:
            self._sync_assessment_to_supabase(investigation_id, case_dossier, risk, confidence)

    def _sync_assessment_to_supabase(
        self,
        investigation_id: str,
        case_dossier: EvidenceReportRequest,
        risk: RiskAssessment,
        confidence: AttributionConfidenceAssessment,
    ) -> None:
        # Blocking, best-effort calls: the endpoints are sync handlers running in worker threads.
        self.supabase.upsert_sync(
            "investigations",
            {
                "id": investigation_id,
                "chain": case_dossier.chain,
                "reported_address": case_dossier.reported_wallet,
                "status": "completed",
                "notes": case_dossier.investigator_notes,
            },
            on_conflict="id",
        )
        self.supabase.insert_sync(
            "risk_assessments",
            {
                "investigation_id": investigation_id,
                "overall_score": float(risk.overall_score),
                "risk_level": risk.risk_level.value,
                "factors": jsonable_encoder([f.model_dump() for f in risk.factors]),
                "summary_rationale": risk.summary_rationale,
                "confidence_score": float(confidence.overall_confidence),
            },
        )

    def get_case(self, investigation_id: str) -> Optional[EvidenceReportRequest]:
        return self._investigations.get(investigation_id)

    def get_risk(self, investigation_id: str) -> Optional[RiskAssessment]:
        return self._risk_assessments.get(investigation_id)

    def get_confidence(self, investigation_id: str) -> Optional[AttributionConfidenceAssessment]:
        return self._confidence_assessments.get(investigation_id)

    def save_report_metadata(self, metadata: EvidenceReportMetadata) -> None:
        """Stores evidence report metadata locally and writes it through to Supabase if configured."""
        self._evidence_reports[metadata.investigation_id] = metadata

        if self.supabase.is_configured:
            self.supabase.upsert_sync(
                "evidence_reports",
                {
                    "investigation_id": metadata.investigation_id,
                    "report_id": metadata.report_id,
                    "storage_path": metadata.storage_path,
                    "file_size_bytes": metadata.file_size_bytes,
                },
                on_conflict="report_id",
            )

    def get_report_metadata(self, investigation_id: str) -> Optional[EvidenceReportMetadata]:
        return self._evidence_reports.get(investigation_id)

    def case_exists(self, investigation_id: str) -> bool:
        return investigation_id in self._investigations


# Global repository instance
global_repository = InvestigationRepository()
