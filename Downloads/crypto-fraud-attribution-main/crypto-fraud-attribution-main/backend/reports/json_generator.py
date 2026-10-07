"""JSON evidence report generator for system-to-system exchange and auditability.

Generates a machine-readable, canonical JSON evidence dossier including:
- Safe-handling banner
- Fact vs Finding labelling
- Forensic wording compliance (last observed destination, requires investigation)
- Structured case summary
- Ordered transactions, attributions, risk factors, and recovery ranking
- Cryptographic SHA-256 report hash for tamper detection
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Dict, List, Optional
import uuid

from fastapi.encoders import jsonable_encoder

from backend.schemas.report import (
    SAFE_HANDLING_ADVISORY,
    EvidenceReportMetadata,
    EvidenceReportRequest,
)


class JSONEvidenceReportGenerator:
    """Builds a standardized, machine-readable JSON evidence package."""

    def generate_report(
        self,
        request: EvidenceReportRequest,
        output_dir: Optional[str] = None,
    ) -> tuple[bytes, EvidenceReportMetadata]:
        report_id = f"REP-JSON-{uuid.uuid4().hex[:8].upper()}"
        filename = f"evidence_report_{request.investigation_id}_{report_id}.json"

        # 1. Fact: Extract observed on-chain transactions
        fact_transactions: List[Dict[str, Any]] = []
        seen_txs = set()
        for path in request.paths:
            for tx in path.transactions:
                if tx.tx_hash in seen_txs:
                    continue
                seen_txs.add(tx.tx_hash)
                fact_transactions.append(
                    {
                        "label": "FACT",
                        "tx_hash": tx.tx_hash,
                        "chain": tx.chain,
                        "from_address": tx.from_address,
                        "to_address": tx.to_address,
                        "amount": str(tx.amount),
                        "asset": tx.asset_symbol,
                        "timestamp": tx.timestamp.isoformat() if hasattr(tx.timestamp, "isoformat") else str(tx.timestamp),
                        "block_number": tx.block_number,
                    }
                )

        # 2. Finding: Endpoint Attributions (strictly worded: last observed destination)
        finding_attributions: List[Dict[str, Any]] = []
        for ep in request.endpoints:
            entity_name = ep.label.entity_name if ep.label else "UNKNOWN"
            cat = ep.label.entity_category.value if (ep.label and hasattr(ep.label.entity_category, "value")) else str(ep.label.entity_category if ep.label else "UNKNOWN")
            finding_attributions.append(
                {
                    "label": "FINDING",
                    "last_observed_destination": ep.address,
                    "entity": entity_name,
                    "category": cat,
                    "hop_distance": ep.hop_distance,
                    "confidence_score": getattr(ep, "confidence", None) or (ep.label.confidence if ep.label else 0.5),
                    "confidence_level": "High" if (getattr(ep, "confidence", None) or (ep.label.confidence if ep.label else 0.5)) >= 0.8 else "Medium",
                    "source": ep.label.source if ep.label else "unattributed",
                    "status": "requires_investigation",
                }
            )

        # 3. Assemble complete structured dossier
        payload: Dict[str, Any] = {
            "report_id": report_id,
            "investigation_id": request.investigation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "safe_handling_advisory": SAFE_HANDLING_ADVISORY,
            "forensic_standards": {
                "wording_rules": {
                    "destination_status": "last observed destination (never 'money is here')",
                    "advisory_status": "requires investigation (never 'criminal')",
                    "relationship_status": "likely related (never 'owned by')",
                },
                "separation": "Direct on-chain events are labeled FACT; analytical models are labeled FINDING.",
            },
            "case_metadata": {
                "reported_wallet": request.reported_wallet,
                "chain": request.chain,
                "investigator_name": request.investigator_name,
                "time_window_start": request.time_window_start,
                "time_window_end": request.time_window_end,
                "missing_data_notes": request.missing_data_notes,
                "investigator_notes": request.investigator_notes,
            },
            "case_summary": request.case_summary,
            "typology": request.typology,
            "facts": {
                "transaction_ledger": fact_transactions,
                "total_transactions_observed": len(fact_transactions),
            },
            "findings": {
                "attributions": finding_attributions,
                "risk_assessment": (
                    {
                        "label": "FINDING",
                        "overall_score": request.risk_assessment.overall_score,
                        "risk_level": request.risk_assessment.risk_level.value,
                        "summary_rationale": request.risk_assessment.summary_rationale,
                        "factors": [f.model_dump(mode="json") for f in request.risk_assessment.factors],
                    }
                    if request.risk_assessment
                    else None
                ),
                "confidence_assessment": (
                    {
                        "label": "FINDING",
                        "overall_confidence": request.confidence_assessment.overall_confidence,
                        "confidence_level": (
                            request.confidence_assessment.confidence_level.value
                            if hasattr(request.confidence_assessment.confidence_level, "value")
                            else str(request.confidence_assessment.confidence_level)
                        ),
                        "primary_entity": request.confidence_assessment.primary_entity,
                        "limitations": request.confidence_assessment.limitations,
                    }
                    if request.confidence_assessment
                    else None
                ),
                "recoverability_ranking": request.recoverability_ranking or [],
                "recovery_clock": request.recovery_clock or [],
                "convergence_links": request.convergence_links or [],
                "clustering_findings": request.clustering_findings or [],
            },
            "alerts": [a.model_dump(mode="json") if hasattr(a, "model_dump") else a for a in request.alerts],
            "audit_trail": request.audit_trail or [],
        }

        # Encode and calculate SHA-256 hash
        json_str = json.dumps(jsonable_encoder(payload), indent=2, sort_keys=True)
        json_bytes = json_str.encode("utf-8")
        report_hash = hashlib.sha256(json_bytes).hexdigest()

        # Insert hash into document representation
        payload["report_hash"] = report_hash
        json_str = json.dumps(jsonable_encoder(payload), indent=2, sort_keys=True)
        json_bytes = json_str.encode("utf-8")

        storage_path = filename
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            storage_path = os.path.join(output_dir, filename)
            with open(storage_path, "wb") as f:
                f.write(json_bytes)

        metadata = EvidenceReportMetadata(
            report_id=report_id,
            investigation_id=request.investigation_id,
            filename=filename,
            file_size_bytes=len(json_bytes),
            storage_path=storage_path,
            download_url=f"/api/investigations/{request.investigation_id}/report/download?format=json",
            report_hash=report_hash,
            format="json",
            safe_handling_advisory=SAFE_HANDLING_ADVISORY,
        )
        return json_bytes, metadata


global_json_generator = JSONEvidenceReportGenerator()
