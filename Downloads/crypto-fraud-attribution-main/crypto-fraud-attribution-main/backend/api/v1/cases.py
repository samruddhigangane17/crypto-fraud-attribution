"""V1 Cases API for NCRP / SAHYOG Integration and Recovery Layer.

Section 9 & Appendix A & Features #14-23:
- Inbound complaint feed: POST /api/v1/cases
- Case retrieval: GET /api/v1/cases/{case_id}
- Bulk processing: POST /api/v1/cases/bulk (CSV upload)
- Recoverability ranking: GET /api/v1/cases/{id}/ranking
- Recovery clock: GET /api/v1/cases/{id}/clock
- Step update: PATCH /api/v1/cases/{id}/clock/{step_id}
- Cross-case convergence: GET /api/v1/cases/{id}/related
- Grounded case summary: GET /api/v1/cases/{id}/summary
- Admin rules table: GET / PUT /api/v1/admin/rules
- Audit logs: GET /api/v1/audit/logs
- Live streaming: WebSocket /api/v1/cases/{id}/ws
"""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import backend.api.investigations as inv
from backend.api.auth import require_authorized_investigator
from backend.api.routes import _get_or_404, run_assessment
from backend.attribution.matcher import EndpointMatcher, global_registry
from backend.audit.logger import global_audit_logger
from backend.clustering.engine import global_clustering_engine
from backend.database.repository import global_repository
from backend.recovery.clock import global_recovery_clock
from backend.recovery.context_filter import global_context_filter
from backend.recovery.convergence import global_convergence_engine
from backend.recovery.extended_signals import global_laundering_detector
from backend.recovery.ranking import global_ranking_engine
from backend.recovery.summary import global_summary_generator
from backend.recovery.typology import global_typology_engine
from backend.reports.json_generator import global_json_generator
from backend.reports.pdf_generator import global_pdf_generator
from backend.schemas.assessment import InvestigationAssessRequest
from backend.schemas.attribution import EntityCategory
from backend.schemas.path import TracePath
from backend.schemas.transaction import TracePath as AssessTracePath
from backend.tracing.analysis import WalletRelationshipAnalyzer
from backend.tracing.graph import FlowGraphBuilder
from backend.tracing.tracer import MultiHopTracer
from backend.tracing.validation import resolve_chain_and_address

logger = logging.getLogger("crypto_attribution.api.v1.cases")

router = APIRouter(prefix="/api/v1", tags=["NCRP / SAHYOG V1 Integration"])


def _hidden_victim_case_ids() -> set:
    """Victim-reported cases stay out of these (open) endpoints until an officer verifies them."""
    from backend.victim.store import global_victim_store
    hidden = {cid for cid, c in inv._INVESTIGATIONS.items()
              if c.get("source") == "victim_portal" and not c.get("source_verified")}
    return hidden | global_victim_store.hidden_case_ids()


class CaseCreateOptions(BaseModel):
    max_hops: int = 5
    min_taint_share: float = Field(default=0.05, ge=0.0, le=1.0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    min_amount: Optional[Decimal] = None


class CaseCreateRequest(BaseModel):
    complaint_ref: Optional[str] = "NCRP-PENDING"
    wallet_address: str
    chain: str = "auto"
    reported_amount: Optional[float] = 0.0
    asset: Optional[str] = "USDT"
    reported_time: Optional[str] = None
    options: Optional[CaseCreateOptions] = Field(default_factory=CaseCreateOptions)
    complaint_category: Optional[str] = None
    investigator_name: Optional[str] = "Lead Investigator"


class ClockStepUpdateRequest(BaseModel):
    status: str = Field(..., description="Status: 'pending', 'sent', 'acknowledged', 'done'")


class AdminRuleUpdateRequest(BaseModel):
    step_type: str
    due_hours: float = Field(..., gt=0.0)


def _execute_case_pipeline(
    case_id: str,
    chain: str,
    reported_address: str,
    options: CaseCreateOptions,
    complaint_category: Optional[str] = None,
    reported_amount: float = 0.0,
) -> Dict[str, Any]:
    """Runs tracing, clustering, attribution, risk scoring, and recovery layer."""
    case = inv._get_case(case_id)
    connector = inv._get_connector(chain, reported_address)
    labels = inv._exchange_labels(chain)

    tracer = MultiHopTracer(
        connector=connector,
        max_hops=options.max_hops,
        min_amount=options.min_amount,
        start_time=options.start_time,
        end_time=options.end_time,
        investigation_id=case_id,
        min_taint_share=options.min_taint_share,
        target_addresses=set(labels),
    )
    paths = tracer.trace(reported_address)

    builder = FlowGraphBuilder.build_from_paths(paths, root_address=reported_address, address_labels=labels)
    cyto_graph = builder.to_cytoscape()
    analyzer = WalletRelationshipAnalyzer.from_paths(paths)
    summary_metrics = analyzer.get_summary()

    intermediate_addrs = sorted(list(tracer.intermediate_addresses))
    case["status"] = "completed"
    case["data_source"] = inv._data_source(connector)
    case["paths"] = paths
    case["intermediate_addresses"] = intermediate_addrs
    case["graph"] = cyto_graph
    case["analysis"] = summary_metrics

    # Notice if zero paths
    notice = None
    if not paths:
        notice = "No outgoing transfers found for this address (zero paths)."
    case["notice"] = notice

    # 1. Assessment (Risk, Confidence, Alerts)
    assessment = run_assessment(
        case_id,
        InvestigationAssessRequest(
            chain=chain,
            reported_address=reported_address,
            paths=inv._to_assess_paths(paths, chain),
            data_completeness=0.5 if tracer.connector_errors else 1.0,
            missing_data_notes="; ".join(tracer.connector_errors) or None,
        ),
    )

    # 2. Recovery Clock
    clock_steps = global_recovery_clock.get_case_clock(case_id)

    # 3. Recoverability Ranking
    ranking_destinations = global_ranking_engine.rank_destinations(paths, assessment.endpoints)

    # 4. Typology Classification
    typology_profile = global_typology_engine.classify_case(
        complaint_category=complaint_category,
        reported_amount=reported_amount,
        paths=paths,
        matched_endpoints=assessment.endpoints,
    )

    # 5. Heuristic Clustering
    clusters = global_clustering_engine.analyze_clusters(paths)

    # 6. Cross-Case Convergence
    all_addrs = [a for p in paths for a in p.all_addresses]
    conv_links = global_convergence_engine.index_case(
        case_id=case_id,
        reported_address=reported_address,
        all_traced_addresses=all_addrs,
        clusters=[c.to_dict() for c in clusters],
        endpoints=[e.model_dump() for e in assessment.endpoints],
    )

    # 7. Grounded Case Summary
    grounded_summary = global_summary_generator.generate_summary(
        case_id=case_id,
        reported_address=reported_address,
        chain=chain,
        paths=paths,
        endpoints=assessment.endpoints,
        risk_assessment=assessment.risk_assessment,
        confidence_assessment=assessment.attribution_confidence,
        recovery_ranking=[r.to_dict() for r in ranking_destinations],
        typology=typology_profile.to_dict(),
    )

    # Store extended recovery artifacts on case
    case["ranking"] = [r.to_dict() for r in ranking_destinations]
    case["clock"] = [s.to_dict() for s in clock_steps]
    case["typology"] = typology_profile.to_dict()
    case["clusters"] = [c.to_dict() for c in clusters]
    case["convergence_links"] = [l.to_dict() for l in conv_links]
    case["case_summary"] = grounded_summary.to_dict()

    # Update saved dossier in repository for reports
    dossier = global_repository.get_case(case_id)
    if dossier:
        dossier.typology = typology_profile.to_dict()
        dossier.recoverability_ranking = [r.to_dict() for r in ranking_destinations]
        dossier.recovery_clock = [s.to_dict() for s in clock_steps]
        dossier.convergence_links = [l.to_dict() for l in conv_links]
        dossier.case_summary = grounded_summary.to_dict()
        dossier.clustering_findings = [c.to_dict() for c in clusters]

    # Persist trace
    inv._store.persist_trace(case)

    # Immutable audit log
    global_audit_logger.log_event(
        event="case_completed",
        case_id=case_id,
        parameters={
            "paths_count": len(paths),
            "endpoints_matched": len(assessment.endpoints),
            "risk_score": assessment.risk_assessment.overall_score,
            "typology": typology_profile.typology_id,
        },
        data_source=case["data_source"],
    )

    return case


def _format_case_contract(case_id: str) -> Dict[str, Any]:
    """Formats case response according to Appendix A Contract."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")

    dossier = None
    try:
        dossier = _get_or_404(case_id)
    except HTTPException:
        pass

    risk_data = {"score": 0.0, "category": "Low", "factors": []}
    attribution_list = []
    flags = []

    if dossier and dossier.risk_assessment:
        risk_data = {
            "score": dossier.risk_assessment.overall_score,
            "category": dossier.risk_assessment.risk_level.value,
            "factors": [f.factor_name for f in dossier.risk_assessment.factors if f.triggered],
        }
        for ep in dossier.endpoints:
            if ep.is_matched and ep.label:
                ep_conf = getattr(ep.label, "confidence", 1.0)
                attribution_list.append(
                    {
                        "entity": ep.label.entity_name,
                        "hop_distance": ep.hop_distance or 1,
                        "amount": float(case.get("amount") or 0.0),
                        "confidence": "High" if ep_conf >= 0.8 else "Medium",
                        "destination_address": ep.address,
                        "category": ep.label.entity_category.value if hasattr(ep.label.entity_category, "value") else str(ep.label.entity_category),
                    }
                )
                if ep.label.entity_category == EntityCategory.MIXER:
                    flags.append("mixer_exposure")
                if ep.label.entity_category == EntityCategory.BRIDGE:
                    flags.append("bridge_transfer")

    return {
        "id": case_id,
        "case_id": case_id,
        "complaint_ref": case.get("complaint_ref", "NCRP-PENDING"),
        "status": case.get("status", "completed"),
        "chain": case["chain"],
        "reported_address": case["reported_address"],
        "reported_amount": case.get("amount", 0.0),
        "asset": case.get("asset", "USDT"),
        "created_at": case["created_at"],
        "risk": risk_data,
        "attribution": attribution_list,
        "flags": list(set(flags)),
        "report_url": f"/api/v1/cases/{case_id}/report",
        "notice": case.get("notice"),
    }


# --- Inbound Complaint Endpoints ---

@router.post("/cases", status_code=status.HTTP_201_CREATED)
def submit_case_ncrp(payload: CaseCreateRequest, background_tasks: BackgroundTasks):
    """NCRP/SAHYOG Inbound Complaint Endpoint (Appendix A).

    Ingests wallet address, auto-detects chain, runs multi-hop tracing,
    matching, risk scoring, and recovery layer.
    """
    try:
        chain, address = resolve_chain_and_address(payload.chain, payload.wallet_address)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))

    case_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).isoformat()

    inv._INVESTIGATIONS[case_id] = {
        "id": case_id,
        "case_id": case_id,
        "complaint_ref": payload.complaint_ref or "NCRP-AUTO",
        "chain": chain.lower(),
        "reported_address": address,
        "amount": payload.reported_amount,
        "asset": payload.asset or "USDT",
        "timestamp": payload.reported_time or now_utc,
        "status": "Reported",
        "created_at": now_utc,
        "graph": None,
        "paths": None,
        "analysis": None,
        "data_source": None,
        "notice": None,
    }
    inv._store.persist_case(inv._INVESTIGATIONS[case_id])

    global_audit_logger.log_event(
        event="case_created",
        case_id=case_id,
        parameters={"complaint_ref": payload.complaint_ref, "wallet_address": address, "chain": chain},
        data_source="ncrp_inbound_api",
    )

    opts = payload.options or CaseCreateOptions()
    _execute_case_pipeline(
        case_id=case_id,
        chain=chain,
        reported_address=address,
        options=opts,
        complaint_category=payload.complaint_category,
        reported_amount=payload.reported_amount or 0.0,
    )

    return _format_case_contract(case_id)


@router.get("/cases")
def list_cases(limit: int = 50):
    """List all registered cases (combining in-memory and persisted investigations)."""
    seen_ids = set()
    results = []
    hidden_ids = _hidden_victim_case_ids()

    # 1. First format active in-memory cases
    for cid in list(inv._INVESTIGATIONS.keys()):
        seen_ids.add(cid)
        if cid in hidden_ids:
            continue
        try:
            results.append(_format_case_contract(cid))
        except Exception as e:
            logger.warning("Failed to format in-memory case %s: %s", cid, e)

    # 2. Add persisted cases from Supabase if configured
    if inv._store.durable:
        try:
            db_rows = inv._store.supabase.select_sync("investigations", {}) or []
            db_rows = sorted(db_rows, key=lambda r: r.get("created_at") or "", reverse=True)
            for row in db_rows:
                cid = row.get("id")
                if not cid or cid in seen_ids or cid in hidden_ids:
                    continue
                seen_ids.add(cid)
                results.append(
                    {
                        "id": cid,
                        "case_id": cid,
                        "complaint_ref": row.get("complaint_ref", "NCRP-PERSISTED"),
                        "status": row.get("status", "completed"),
                        "chain": row.get("chain", "ethereum"),
                        "reported_address": row.get("reported_address", ""),
                        "reported_amount": row.get("amount", 0.0),
                        "asset": row.get("asset", "USDT"),
                        "created_at": row.get("created_at"),
                        "risk": {"score": 0.0, "category": "Persisted", "factors": []},
                        "attribution": [],
                        "flags": [],
                        "report_url": f"/api/v1/cases/{cid}/report",
                        "notice": row.get("notice"),
                    }
                )
                if len(results) >= limit:
                    break
        except Exception as e:
            logger.warning("Failed to fetch cases from Supabase: %s", e)

    return results


@router.get("/cases/{case_id}")
def get_case_ncrp(case_id: str):
    """Retrieve case details formatted for NCRP / SAHYOG integration."""
    if case_id in _hidden_victim_case_ids():
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return _format_case_contract(case_id)


# --- Bulk CSV Processing ---

@router.post("/cases/bulk")
async def bulk_upload_cases(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = None,
):
    """Bulk CSV Ingestion for Batches of Reported Addresses.

    CSV header expected: complaint_ref, wallet_address, chain, amount, asset
    Auto-detects chains and validates address formats.
    """
    content = ""
    if file:
        file_bytes = await file.read()
        content = file_bytes.decode("utf-8", errors="replace")
    elif csv_text:
        content = csv_text
    else:
        raise HTTPException(status_code=400, detail="Provide CSV file upload or csv_text string.")

    reader = csv.DictReader(io.StringIO(content))
    created_cases = []
    failed_rows = []

    for idx, row in enumerate(reader, start=1):
        wallet = (row.get("wallet_address") or row.get("address") or "").strip()
        if not wallet:
            continue
        chain_input = (row.get("chain") or "auto").strip()
        ref = (row.get("complaint_ref") or row.get("complaint_id") or f"BULK-ROW-{idx}").strip()
        amt_str = (row.get("amount") or row.get("reported_amount") or "0").strip()
        asset = (row.get("asset") or "USDT").strip()

        try:
            amt = float(amt_str) if amt_str else 0.0
            chain, norm_addr = resolve_chain_and_address(chain_input, wallet)
            case_id = str(uuid.uuid4())
            now_utc = datetime.now(timezone.utc).isoformat()

            inv._INVESTIGATIONS[case_id] = {
                "id": case_id,
                "case_id": case_id,
                "complaint_ref": ref,
                "chain": chain.lower(),
                "reported_address": norm_addr,
                "amount": amt,
                "asset": asset,
                "status": "Reported",
                "created_at": now_utc,
                "graph": None,
                "paths": None,
                "analysis": None,
                "data_source": "bulk_csv",
            }
            inv._store.persist_case(inv._INVESTIGATIONS[case_id])

            created_cases.append(
                {
                    "case_id": case_id,
                    "complaint_ref": ref,
                    "chain": chain,
                    "wallet_address": norm_addr,
                    "status": "Reported",
                }
            )
        except Exception as e:
            failed_rows.append({"row_index": idx, "wallet_address": wallet, "error": str(e)})

    return {
        "total_rows_read": idx if "idx" in locals() else 0,
        "successfully_ingested": len(created_cases),
        "failed_count": len(failed_rows),
        "cases": created_cases,
        "errors": failed_rows,
    }


# --- Golden Hour Recovery Layer Endpoints ---

@router.get("/cases/{case_id}/ranking")
def get_case_recoverability_ranking(case_id: str):
    """Returns the Recoverability Ranking (Act now, Act soon, Monitor) for all destinations."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    dossier = _get_or_404(case_id)
    rankings = global_ranking_engine.rank_destinations(dossier.paths, dossier.endpoints)
    return {
        "case_id": case_id,
        "destinations_ranked": [r.to_dict() for r in rankings],
        "advisory_notice": "Advisory only. Authorised investigator review required prior to hold action.",
    }


@router.get("/cases/{case_id}/clock")
def get_case_recovery_clock(case_id: str):
    """Returns the per-case recovery timeline with owners, deadlines, and statuses."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    steps = global_recovery_clock.get_case_clock(case_id, check_overdue=True)
    return {
        "case_id": case_id,
        "timeline_steps": [s.to_dict() for s in steps],
        "overdue_count": sum(1 for s in steps if s.status == "overdue"),
    }


@router.patch("/cases/{case_id}/clock/{step_id}")
def update_case_recovery_step(case_id: str, step_id: str, body: ClockStepUpdateRequest):
    """Updates the status of a time-critical recovery step."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    try:
        updated = global_recovery_clock.update_step_status(case_id, step_id, body.status)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/related")
def get_case_convergence(case_id: str):
    """Returns cross-case convergence links and coordinated network view."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return global_convergence_engine.get_network_view(case_id)


@router.get("/cases/{case_id}/summary")
def get_grounded_case_summary(case_id: str):
    """Returns the strictly grounded case summary with source record IDs."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    dossier = _get_or_404(case_id)
    ranking = global_ranking_engine.rank_destinations(dossier.paths, dossier.endpoints)
    summary = global_summary_generator.generate_summary(
        case_id=case_id,
        reported_address=dossier.reported_wallet,
        chain=dossier.chain,
        paths=dossier.paths,
        endpoints=dossier.endpoints,
        risk_assessment=dossier.risk_assessment,
        confidence_assessment=dossier.confidence_assessment,
        recovery_ranking=[r.to_dict() for r in ranking],
        typology=dossier.typology,
    )
    return summary.to_dict()


@router.get("/cases/{case_id}/clusters")
def get_case_clusters(case_id: str):
    """Returns heuristic wallet clusters discovered for this case."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    dossier = _get_or_404(case_id)
    clusters = global_clustering_engine.analyze_clusters(dossier.paths)
    return {
        "case_id": case_id,
        "clusters_count": len(clusters),
        "clusters": [c.to_dict() for c in clusters],
    }


# --- Admin Timing Rules Table ---

@router.get("/admin/rules")
def get_admin_timing_rules():
    """Reads the active recovery timing rules table."""
    return [r.model_dump() for r in global_recovery_clock.get_rules()]


@router.put("/admin/rules")
def update_admin_timing_rule(rule_update: AdminRuleUpdateRequest):
    """Edits a timing rule. Audit-logged."""
    try:
        updated = global_recovery_clock.update_rule(
            step_type=rule_update.step_type,
            due_hours=rule_update.due_hours,
            actor="admin_api",
        )
        return updated.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Audit Logs Endpoint ---

@router.get("/audit/logs")
def get_audit_logs(case_id: Optional[str] = None, limit: int = 100):
    """Retrieves immutable audit logs for compliance, court admissibility, and reproducibility."""
    if case_id:
        return [l.to_dict() for l in global_audit_logger.get_logs_for_case(case_id)]
    return [l.to_dict() for l in global_audit_logger.get_all_logs(limit=limit)]


# --- Reports & Evidence Export (V1 Aliases) ---

@router.get("/cases/{case_id}/report")
def get_case_report_v1(
    case_id: str,
    report_format: str = Query("pdf", alias="format"),
):
    """Retrieves metadata or generated report in PDF or JSON."""
    dossier = _get_or_404(case_id)
    if report_format.lower() == "json":
        raw_bytes, metadata = global_json_generator.generate_report(dossier)
    else:
        raw_bytes, metadata = global_pdf_generator.generate_report(dossier)
    return metadata


@router.get("/cases/{case_id}/report/download")
def download_case_report_v1(
    case_id: str,
    report_format: str = Query("pdf", alias="format"),
):
    """Directly downloads evidence report in PDF or JSON format."""
    dossier = _get_or_404(case_id)
    if report_format.lower() == "json":
        raw_bytes, metadata = global_json_generator.generate_report(dossier)
        media_type = "application/json"
    else:
        raw_bytes, metadata = global_pdf_generator.generate_report(dossier)
        media_type = "application/pdf"

    return Response(
        content=raw_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{metadata.filename}"'},
    )


# --- Live WebSockets Updates ---

@router.websocket("/cases/{case_id}/ws")
async def case_live_websocket(websocket: WebSocket, case_id: str):
    """Streams live trace progress, new alerts, and clock updates to frontend clients."""
    await websocket.accept()
    try:
        case = inv._get_case(case_id)
        status_msg = case.get("status") if case else "unknown"
        await websocket.send_json(
            {
                "event": "connection_established",
                "case_id": case_id,
                "status": status_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        while True:
            # Receive any client ping
            data = await websocket.receive_text()
            # Send latest case heartbeat & alerts count
            alerts = []
            try:
                dossier = _get_or_404(case_id)
                alerts = [a.model_dump(mode="json") for a in dossier.alerts]
            except Exception:
                pass

            await websocket.send_json(
                {
                    "event": "heartbeat",
                    "case_id": case_id,
                    "alerts_count": len(alerts),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for case {case_id}")
    except Exception as e:
        logger.warning(f"WebSocket error for case {case_id}: {e}")


# --- USP 1: Case Freeze Notice Generation ---

from backend.reports.freeze_notice_generator import (
    FreezeNoticeRequest,
    build_freeze_notice_data,
    global_freeze_notice_generator,
)


@router.post("/cases/{case_id}/freeze-notice")
def generate_case_freeze_notice(
    case_id: str,
    body: Optional[FreezeNoticeRequest] = None,
    format: Optional[str] = Query(None, description="Output format: 'pdf' or 'json'"),
):
    """USP 1: Generates court-ready Freeze Notice & BSA Section 63 Certificate for a specific case."""
    case = inv._get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")

    if body is None:
        req = FreezeNoticeRequest(case_id=case_id)
    else:
        req = body
        req.case_id = case_id

    data = build_freeze_notice_data(req)
    out_format = (format or req.format or "pdf").lower()

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
    filename = f"Freeze_Notice_{case_id}_{safe_addr}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

