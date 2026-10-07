"""FastAPI API routes for Member 2's components:

- Address Registry & Attribution
- Live Case Assessment (POST /investigations/{id}/assess)
- Explainable Risk & Confidence Assessments (GET /investigations/{id}/risk)
- Continuous Monitoring & Alerts
- PDF Evidence Report Generation and Download
"""

import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import Response

from backend.api.auth import require_authorized_investigator
from backend.attribution.matcher import EndpointMatcher, global_registry
from backend.database.repository import global_repository
from backend.mock_data.mock_case import create_mock_investigation_request
from backend.monitoring.alerts import global_alert_engine
from backend.monitoring.service import global_monitoring_service
from backend.reports.json_generator import global_json_generator
from backend.reports.pdf_generator import global_pdf_generator
from backend.schemas.assessment import AssessmentResponse, InvestigationAssessRequest
from backend.schemas.attribution import (
    AddressLabel,
    AddressLabelCreate,
    EndpointMatchResult,
    EntityCategory,
)
from backend.schemas.monitoring import Alert, MonitoringConfig
from backend.schemas.report import EvidenceReportMetadata, EvidenceReportRequest
from backend.schemas.risk import AttributionConfidenceAssessment, RiskAssessment
from backend.scoring.confidence_engine import AttributionConfidenceEngine
from backend.scoring.risk_engine import RiskScoringEngine

router = APIRouter(prefix="/api", tags=["Intelligence & Attribution"])

# Service singletons
risk_engine = RiskScoringEngine()
conf_engine = AttributionConfidenceEngine()
matcher = EndpointMatcher(global_registry)

# Flag to control whether mock data can be accessed via explicit DEMO- prefix
ENABLE_DEMO_CASES = os.getenv("ENABLE_DEMO_CASES", "true").lower() in ("true", "1", "yes")


def _get_or_404(investigation_id: str) -> EvidenceReportRequest:
    """Retrieves an existing investigation dossier, or raises 404 (unknown) / 409 (not traced yet).

    Strictly avoids returning fake fallback data for mistyped or non-existent cases.
    Only explicit 'DEMO-' prefixed IDs return mock data when ENABLE_DEMO_CASES is enabled.
    """
    case = global_repository.get_case(investigation_id)
    if case:
        return case

    # After a restart the case may only exist in Supabase; reload it and rebuild its assessment.
    from backend.api.investigations import describe_case, restore_case  # lazy: avoids circular import

    if restore_case(investigation_id):
        case = global_repository.get_case(investigation_id)
        if case:
            return case

    # Demo cases must use explicit DEMO- prefix only
    if ENABLE_DEMO_CASES and investigation_id.startswith("DEMO-"):
        demo_req = create_mock_investigation_request(case_id=investigation_id)
        global_repository.save_assessment(
            investigation_id=investigation_id,
            case_dossier=demo_req,
            risk=demo_req.risk_assessment,
            confidence=demo_req.confidence_assessment,
        )
        return demo_req

    known = describe_case(investigation_id)
    if known is not None:
        # The case exists but has no assessment: tracing never completed (e.g. the provider failed).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Investigation '{investigation_id}' exists (status: {known['status']}) but has no completed "
                "trace, so there is no risk assessment, alerts or report yet. Re-run POST "
                f"/api/investigations/{investigation_id}/trace and check the server log if it fails."
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"Investigation '{investigation_id}' not found. "
            "To evaluate a case, submit trace paths to POST /api/investigations/{id}/assess first."
        ),
    )


# --- Address Registry & Attribution Endpoints ---

@router.get("/registry/labels", response_model=List[AddressLabel])
def list_address_labels(
    query: Optional[str] = Query(None, description="Search term for address or entity name"),
    chain: Optional[str] = Query(None, description="Filter by blockchain, e.g. ethereum"),
    category: Optional[EntityCategory] = Query(None, description="Filter by entity category"),
    include_unverified: bool = Query(False, description="Whether to include unverified community labels"),
):
    """Retrieves or searches registered address labels with data provenance details."""
    if query:
        return global_registry.search(
            query=query,
            chain=chain,
            category=category,
            include_unverified=include_unverified,
        )
    labels = global_registry.get_all(include_unverified=include_unverified)
    if chain:
        labels = [l for l in labels if l.chain.lower() == chain.lower()]
    if category:
        labels = [l for l in labels if l.entity_category == category]
    return labels


@router.post("/registry/labels", response_model=AddressLabel, status_code=status.HTTP_201_CREATED)
def add_address_label(
    payload: AddressLabelCreate,
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Registers a new address label with explicit provenance fields.

    Restricted: Requires authorized investigator session (changes shared registry state).
    """
    return global_registry.register(payload)


@router.get("/attribution/match", response_model=EndpointMatchResult)
def match_single_address(
    chain: str = Query(..., description="Blockchain, e.g. ethereum"),
    address: str = Query(..., description="Address to look up"),
    include_unverified: bool = Query(False, description="Include unverified community submissions"),
):
    """Looks up an address against the known-entity registry.

    Unmatched addresses are marked as UNKNOWN rather than assuming they are suspicious.
    """
    return matcher.match_address(chain=chain, address=address, include_unverified=include_unverified)


# --- Live Case Assessment Endpoint ---

def run_assessment(
    investigation_id: str,
    payload: InvestigationAssessRequest,
    persist_remote: bool = True,
) -> AssessmentResponse:
    """Match endpoints, score risk and confidence, raise alerts, and save the dossier.

    Called by POST /assess and automatically at the end of POST /trace.
    """
    # 1. Match endpoints across all paths
    endpoints = matcher.match_trace_paths(
        chain=payload.chain,
        paths=payload.paths,
        include_unverified=payload.include_unverified_labels,
    )

    # 2. Compute explainable risk factors
    risk_assessment = risk_engine.evaluate_risk(
        investigation_id=investigation_id,
        reported_address=payload.reported_address,
        chain=payload.chain,
        paths=payload.paths,
        matched_endpoints=endpoints,
        data_completeness=payload.data_completeness,
    )

    # 3. Compute attribution confidence for primary destination (or first matched)
    primary_match = next((ep for ep in endpoints if ep.is_matched), None)
    if not primary_match and endpoints:
        primary_match = endpoints[0]
    elif not primary_match:
        primary_match = matcher.match_address(chain=payload.chain, address=payload.reported_address)

    target_addr = primary_match.address if primary_match else payload.reported_address
    confidence_assessment = conf_engine.evaluate_confidence(
        investigation_id=investigation_id,
        target_address=target_addr,
        chain=payload.chain,
        match=primary_match,
        paths=payload.paths,
    )

    # 4. Generate alerts for observed transfers
    mon_config = global_monitoring_service.get_config(investigation_id) or MonitoringConfig(
        investigation_id=investigation_id,
        chain=payload.chain,
        watched_addresses=[payload.reported_address],
        alert_on_exchange_deposit=True,
        alert_on_mixer=True,
        alert_on_new_tx=True,
    )

    generated_alerts: List[Alert] = []
    for path in payload.paths:
        for i, tx in enumerate(path.transactions):
            hop_number = i + 1
            hop_match = matcher.match_address(
                chain=payload.chain,
                address=tx.to_address,
                hop_distance=hop_number,
                associated_tx_hash=tx.tx_hash,
                include_unverified=payload.include_unverified_labels,
            )
            alerts = global_alert_engine.evaluate_transaction_for_alerts(
                investigation_id=investigation_id,
                tx=tx,
                hop_number=hop_number,
                match=hop_match,
                config=mon_config,
            )
            generated_alerts.extend(alerts)

    # 5. Build and save investigation dossier into repository
    dossier = EvidenceReportRequest(
        investigation_id=investigation_id,
        reported_wallet=payload.reported_address,
        chain=payload.chain,
        investigator_name=payload.investigator_name or "Lead Investigator",
        time_window_start=payload.time_window_start,
        time_window_end=payload.time_window_end,
        paths=payload.paths,
        endpoints=endpoints,
        risk_assessment=risk_assessment,
        confidence_assessment=confidence_assessment,
        alerts=global_alert_engine.get_alerts_by_investigation(investigation_id),
        missing_data_notes=payload.missing_data_notes,
        investigator_notes=payload.investigator_notes,
    )
    global_repository.save_assessment(
        investigation_id=investigation_id,
        case_dossier=dossier,
        risk=risk_assessment,
        confidence=confidence_assessment,
        persist_remote=persist_remote,
    )

    return AssessmentResponse(
        investigation_id=investigation_id,
        chain=payload.chain,
        reported_address=payload.reported_address,
        risk_assessment=risk_assessment,
        attribution_confidence=confidence_assessment,
        endpoints=endpoints,
        alerts_generated=generated_alerts,
    )


@router.post(
    "/investigations/{investigation_id}/assess",
    response_model=AssessmentResponse,
    status_code=status.HTTP_200_OK,
)
def assess_investigation(
    investigation_id: str,
    payload: InvestigationAssessRequest,
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Evaluates real trace paths from Member 1's tracing engine.

    Restricted: Requires authorized investigator session.
    1. Matches endpoints and intermediate nodes against known registry.
    2. Runs explainable risk scoring engine.
    3. Runs separate attribution confidence engine on identified destination services.
    4. Evaluates transaction alerts and updates deduplication engine.
    5. Stores dossier in repository for downstream report generation.
    """
    return run_assessment(investigation_id, payload)


# --- Risk & Confidence Assessment Endpoints ---

@router.get("/investigations/{investigation_id}/risk")
def get_investigation_risk_and_confidence(investigation_id: str):
    """Returns separate explainable risk assessment and attribution confidence assessment.

    Returns HTTP 404 if investigation_id has not been assessed.
    """
    req = _get_or_404(investigation_id)

    return {
        "investigation_id": investigation_id,
        "reported_wallet": req.reported_wallet,
        "chain": req.chain,
        "risk_assessment": req.risk_assessment,
        "attribution_confidence": req.confidence_assessment,
        "methodology": "Transparent rule-based scoring without black-box ML model.",
    }


# --- Continuous Monitoring & Alerts Endpoints ---

@router.post("/investigations/{investigation_id}/monitor", response_model=MonitoringConfig)
def set_monitoring_state(
    investigation_id: str,
    config: MonitoringConfig,
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Enables or configures continuous background monitoring for an investigation.

    Restricted: Requires authorized investigator session (modifies surveillance jobs).
    """
    config.investigation_id = investigation_id
    return global_monitoring_service.register_case(config)


@router.get("/investigations/{investigation_id}/alerts", response_model=List[Alert])
def get_investigation_alerts(investigation_id: str):
    """Retrieves all deduplicated alerts recorded for an investigation.

    Returns HTTP 404 if investigation_id is invalid or unassessed.
    """
    _get_or_404(investigation_id)
    return global_alert_engine.get_alerts_by_investigation(investigation_id)


# --- Evidence Report Generation & Retrieval (PDF & JSON) ---

@router.post(
    "/investigations/{investigation_id}/report",
    response_model=EvidenceReportMetadata,
    status_code=status.HTTP_201_CREATED,
)
def generate_evidence_report(
    investigation_id: str,
    payload: Optional[EvidenceReportRequest] = None,
    report_format: str = Query("pdf", alias="format", description="Report format: 'pdf' or 'json'"),
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Generates an investigator-ready evidence dossier (PDF or canonical JSON).

    Restricted: Requires authorized investigator session (Supabase Auth token).
    """
    req = payload or _get_or_404(investigation_id)

    if report_format.lower() == "json":
        raw_bytes, metadata = global_json_generator.generate_report(req)
    else:
        raw_bytes, metadata = global_pdf_generator.generate_report(req)

    global_repository.save_report_metadata(metadata)
    return metadata


@router.get("/investigations/{investigation_id}/report")
def get_report_reference(
    investigation_id: str,
    report_format: str = Query("pdf", alias="format", description="Report format: 'pdf' or 'json'"),
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Retrieves authorized metadata reference for the generated evidence report.

    Restricted: Requires authorized investigator session (Supabase Auth token).
    """
    metadata = global_repository.get_report_metadata(investigation_id)
    if not metadata or getattr(metadata, "format", "pdf") != report_format.lower():
        req = _get_or_404(investigation_id)
        if report_format.lower() == "json":
            raw_bytes, metadata = global_json_generator.generate_report(req)
        else:
            raw_bytes, metadata = global_pdf_generator.generate_report(req)
        global_repository.save_report_metadata(metadata)

    return metadata


@router.get("/investigations/{investigation_id}/report/download")
def download_evidence_report(
    investigation_id: str,
    report_format: str = Query("pdf", alias="format", description="Report format: 'pdf' or 'json'"),
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Downloads the generated evidence dossier directly (PDF or canonical JSON).

    Restricted: Requires authorized investigator session (Supabase Auth token).
    """
    req = _get_or_404(investigation_id)
    if report_format.lower() == "json":
        raw_bytes, metadata = global_json_generator.generate_report(req)
        media_type = "application/json"
    else:
        raw_bytes, metadata = global_pdf_generator.generate_report(req)
        media_type = "application/pdf"

    return Response(
        content=raw_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{metadata.filename}"'},
    )


@router.get("/investigations/{investigation_id}/report/verify")
def verify_report_integrity(
    investigation_id: str,
    report_hash: str = Query(..., description="Cryptographic SHA-256 hash to verify against stored metadata"),
    current_investigator: dict = Depends(require_authorized_investigator),
):
    """Verifies that an exported report matches its stored tamper-evident SHA-256 hash."""
    metadata = global_repository.get_report_metadata(investigation_id)
    if not metadata or not metadata.report_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored report hash found for investigation '{investigation_id}'.",
        )
    is_valid = metadata.report_hash.lower() == report_hash.strip().lower()
    return {
        "investigation_id": investigation_id,
        "provided_hash": report_hash,
        "recorded_hash": metadata.report_hash,
        "verified": is_valid,
        "status": "VALID_AUTHENTIC" if is_valid else "TAMPERED_OR_MODIFIED",
        "created_at": metadata.created_at,
    }


# --- USP 1: Freeze-Point Finder & Statutory Freeze Notice Generator ---

from backend.reports.freeze_notice_generator import (
    FreezeNoticeRequest,
    build_freeze_notice_data,
    global_freeze_notice_generator,
)


@router.post("/freeze-notice/generate")
def generate_freeze_notice(
    body: FreezeNoticeRequest,
    format: Optional[str] = Query(None, description="Output format: 'pdf' or 'json'"),
):
    """USP 1: Generates an official Law Enforcement Freeze & Preservation Notice with BSA 2023 s.63 Certificate."""
    data = build_freeze_notice_data(body)
    out_format = (format or body.format or "pdf").lower()

    if out_format == "json":
        return {
            "case_id": data.case_id,
            "ncrp_ack_no": data.ncrp_ack_no,
            "destination_address": data.destination_address,
            "entity_name": data.entity_name,
            "freezable_by": data.freezable_by,
            "freeze_mechanism": data.freeze_mechanism,
            "issuer_contact_portal": data.issuer_contact_portal,
            "traced_amount": data.traced_amount,
            "asset": data.asset,
            "chain": data.chain,
            "token_contract": data.token_contract,
            "blacklist_selector": data.blacklist_selector,
            "attribution_confidence": data.attribution_confidence,
            "confidence_gate_passed": data.confidence_gate_passed,
            "registry_version": data.registry_version,
            "bsa_section_63_certificate": {
                "status": "Attested",
                "system_description": "Real-Time Crypto Fraud Attribution System",
                "registry_version": data.registry_version,
                "electronic_evidence_act": "Bharatiya Sakshya Adhiniyam (BSA), 2023 Section 63",
            },
        }

    pdf_bytes = global_freeze_notice_generator.generate_notice_pdf(data)
    safe_addr = data.destination_address[:10] if data.destination_address else "wallet"
    filename = f"Freeze_Notice_{data.case_id}_{safe_addr}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

