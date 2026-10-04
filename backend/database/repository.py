"""Investigation repository interface with Supabase bridge and in-memory fallback.

Coordinates with Member 3's Supabase tables (investigations, risk_assessments,
evidence_reports) and Supabase Storage bucket ('evidence-reports').
"""

import asyncio
import logging
from typing import Dict, List, Optional
import uuid

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
    ) -> None:
        """Stores assessment results locally and syncs to Supabase if configured."""
        self._investigations[investigation_id] = case_dossier
        self._risk_assessments[investigation_id] = risk
        self._confidence_assessments[investigation_id] = confidence

        if self.supabase.is_configured:
            # Schedule async sync to Supabase in background
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._sync_assessment_to_supabase(investigation_id, case_dossier, risk))
            except Exception as e:
                logger.debug(f"Async loop not running, skipping background Supabase push: {e}")

    async def _sync_assessment_to_supabase(
        self,
        investigation_id: str,
        case_dossier: EvidenceReportRequest,
        risk: RiskAssessment,
    ) -> None:
        inv_record = {
            "id": investigation_id,
            "chain": case_dossier.chain,
            "reported_address": case_dossier.reported_wallet,
            "status": "completed",
            "notes": case_dossier.investigator_notes,
        }
        await self.supabase.insert_record("investigations", inv_record)

        risk_record = {
            "investigation_id": investigation_id,
            "overall_score": float(risk.overall_score),
            "risk_level": risk.risk_level.value,
            "factors": [f.model_dump() for f in risk.factors],
            "summary_rationale": risk.summary_rationale,
        }
        await self.supabase.insert_record("risk_assessments", risk_record)

    def get_case(self, investigation_id: str) -> Optional[EvidenceReportRequest]:
        return self._investigations.get(investigation_id)

    def get_risk(self, investigation_id: str) -> Optional[RiskAssessment]:
        return self._risk_assessments.get(investigation_id)

    def get_confidence(self, investigation_id: str) -> Optional[AttributionConfidenceAssessment]:
        return self._confidence_assessments.get(investigation_id)

    def save_report_metadata(self, metadata: EvidenceReportMetadata) -> None:
        """Stores evidence report metadata locally and syncs to Supabase if configured."""
        self._evidence_reports[metadata.investigation_id] = metadata

        if self.supabase.is_configured:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    rep_record = {
                        "investigation_id": metadata.investigation_id,
                        "report_id": metadata.report_id,
                        "storage_path": metadata.storage_path,
                        "file_size_bytes": metadata.file_size_bytes,
                    }
                    loop.create_task(self.supabase.insert_record("evidence_reports", rep_record))
            except Exception as e:
                logger.debug(f"Async loop not running, skipping background Supabase report push: {e}")

    def get_report_metadata(self, investigation_id: str) -> Optional[EvidenceReportMetadata]:
        return self._evidence_reports.get(investigation_id)

    def case_exists(self, investigation_id: str) -> bool:
        return investigation_id in self._investigations


# Global repository instance
global_repository = InvestigationRepository()
