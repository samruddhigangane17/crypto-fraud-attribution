from datetime import datetime, timezone
from decimal import Decimal
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

import logging

from backend.database.case_store import CaseStore
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.factory import ConnectorUnavailableError, build_connector
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.etherscan import EtherscanConnector, EtherscanConnectorError
from backend.tracing.connectors.throttle import ThrottledConnector
from backend.tracing.tracer import MultiHopTracer
from backend.tracing.graph import FlowGraphBuilder
from backend.tracing.analysis import WalletRelationshipAnalyzer
from backend.tracing.validation import is_demo_address, resolve_chain_and_address
from backend.attribution.registry import global_registry
from backend.schemas.attribution import EntityCategory
from backend.api.routes import run_assessment
from backend.schemas.assessment import InvestigationAssessRequest
from backend.schemas.transaction import TracePath as AssessTracePath

logger = logging.getLogger("crypto_attribution.investigations")

router = APIRouter(prefix="/api/investigations", tags=["investigations"])

# In-memory storage for investigations during local development/session.
# NOTE: This is an ephemeral in-memory store and does not survive application restarts.
# In production, persistence is managed via Supabase by Member 3.
_INVESTIGATIONS: Dict[str, Dict[str, Any]] = {}

# Write-through persistence: memory first, Supabase as the durable copy when configured.
_store = CaseStore(_INVESTIGATIONS)


def _get_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Case from memory, or reloaded from Supabase after a restart."""
    case = _INVESTIGATIONS.get(case_id)
    if case is None:
        case = _store.load(case_id)
        if case is not None and case.get("status") == "completed":
            _rebuild_assessment(case)
    return case


def describe_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Minimal public view of a case (None if unknown). Used by routes.py for 409 vs 404."""
    case = _get_case(case_id)
    return None if case is None else {"id": case["id"], "status": case["status"]}


def restore_case(case_id: str) -> bool:
    """Make sure a persisted case and its assessment are back in memory. True if restored."""
    case = _get_case(case_id)
    return case is not None and case.get("status") == "completed"


def _rebuild_assessment(case: Dict[str, Any]) -> None:
    """Re-run the (deterministic) assessment from stored paths; does not write to Supabase again."""
    paths = case.get("paths") or []
    run_assessment(
        case["id"],
        InvestigationAssessRequest(
            chain=case["chain"],
            reported_address=case["reported_address"],
            paths=_to_assess_paths(paths, case["chain"]),
            data_completeness=1.0,
        ),
        persist_remote=False,
    )

# Test hook to allow injecting mock connectors in offline unit tests
_TEST_CONNECTOR: Optional[BaseConnector] = None


def set_test_connector(connector: Optional[BaseConnector]) -> None:
    """Allow test suites to inject custom connectors for offline integration testing."""
    global _TEST_CONNECTOR
    _TEST_CONNECTOR = connector


def _get_connector(chain: str, reported_address: str) -> BaseConnector:
    """Select the connector. Never silently falls back to mock data for a real address."""
    if _TEST_CONNECTOR is not None:
        return _TEST_CONNECTOR
    try:
        return build_connector(chain, reported_address)
    except ConnectorUnavailableError as err:
        code = (
            status.HTTP_501_NOT_IMPLEMENTED
            if err.reason == "unsupported_chain"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(status_code=code, detail=str(err)) from err


def _exchange_labels(chain: str) -> Dict[str, str]:
    """Verified exchange/VASP addresses for this chain: {address_lower: entity_name}.

    Used both to stop tracing at an exchange and to label exchange nodes in the graph.
    """
    return {
        label.address.lower(): label.entity_name
        for label in global_registry.get_all()
        if label.chain.lower() == chain.lower()
        and label.entity_category == EntityCategory.EXCHANGE_VASP
    }


def _data_source(connector: BaseConnector) -> str:
    if isinstance(connector, ThrottledConnector):
        connector = connector.inner
    if isinstance(connector, MockConnector):
        return "mock"
    if isinstance(connector, EtherscanConnector):
        return "etherscan"
    return "custom"


def _to_assess_paths(paths, chain: str) -> List[AssessTracePath]:
    """Convert Member 1 trace paths into the shape Member 2's engines expect."""
    out = []
    for p in paths:
        first = p.transactions[0] if p.transactions else None
        out.append(
            AssessTracePath(
                investigation_id=p.investigation_id,
                chain=chain,
                start_address=first.from_address if first else p.end_address,
                end_address=p.end_address,
                hop_count=p.hop_count,
                transactions=p.transactions,
                total_volume=first.amount if first else Decimal("0"),
            )
        )
    return out


class InvestigationCreate(BaseModel):
    chain: str
    reported_address: str
    amount: Optional[float] = None
    timestamp: Optional[str] = None


class TraceRequest(BaseModel):
    max_hops: int = 5
    min_taint_share: float = Field(default=0.05, ge=0.0, le=1.0)
    min_amount: Optional[Decimal] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None



@router.post("")
def create_investigation(case: InvestigationCreate):
    try:
        chain, address = resolve_chain_and_address(case.chain, case.reported_address)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    case = case.model_copy(update={"chain": chain, "reported_address": address})

    case_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).isoformat()
    
    _INVESTIGATIONS[case_id] = {
        "id": case_id,
        "chain": case.chain.lower(),
        "reported_address": case.reported_address,
        "amount": case.amount,
        "timestamp": case.timestamp,
        "status": "Reported",
        "created_at": now_utc,
        "graph": None,
        "paths": None,
        "analysis": None,
        "data_source": None,
        "notice": None,
    }
    persisted = _store.persist_case(_INVESTIGATIONS[case_id])
    if persisted is False:
        logger.warning("Case %s created but could not be written to Supabase", case_id)

    return {
        "id": case_id,
        "chain": case.chain,
        "reported_address": case.reported_address,
        "status": "Reported",
        "created_at": now_utc,
    }


@router.get("/{case_id}")
def get_investigation(case_id: str):
    if _get_case(case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {case_id} not found",
        )
    case = _INVESTIGATIONS[case_id]
    return {
        "id": case["id"],
        "status": case["status"],
        "reported_address": case["reported_address"],
        "chain": case["chain"],
        "created_at": case["created_at"],
        "intermediate_addresses": case.get("intermediate_addresses", []),
        "data_source": case.get("data_source"),
        "notice": case.get("notice"),
    }


@router.post("/{case_id}/trace")
def start_trace(case_id: str, request: TraceRequest, background_tasks: BackgroundTasks):
    if _get_case(case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {case_id} not found",
        )
    case = _INVESTIGATIONS[case_id]
    reported_address = case["reported_address"]

    try:
        connector = _get_connector(case["chain"], reported_address)
        labels = _exchange_labels(case["chain"])
        tracer = MultiHopTracer(
            connector=connector,
            max_hops=request.max_hops,
            min_amount=request.min_amount,
            start_time=request.start_time,
            end_time=request.end_time,
            investigation_id=case_id,
            min_taint_share=request.min_taint_share,
            target_addresses=set(labels),
        )
        paths = tracer.trace(reported_address)
        if tracer.connector_errors and not paths:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Blockchain provider failed during transaction tracing",
            )

        builder = FlowGraphBuilder.build_from_paths(
            paths,
            root_address=reported_address,
            address_labels=labels,
        )
        cyto_graph = builder.to_cytoscape()

        analyzer = WalletRelationshipAnalyzer.from_paths(paths)
        summary = analyzer.get_summary()

        intermediate_addrs = sorted(list(tracer.intermediate_addresses))
        case["status"] = "completed"
        case["data_source"] = _data_source(connector)
        case["paths"] = paths
        case["intermediate_addresses"] = intermediate_addrs
        case["graph"] = cyto_graph
        case["analysis"] = summary

        warnings: List[str] = []
        if tracer.connector_errors:
            warnings.append(
                f"{len(tracer.connector_errors)} data request(s) to the blockchain provider failed, "
                "so results may be incomplete (often an API rate limit). Re-run the trace to retry."
            )
        notice: Optional[str] = None
        if not paths:
            window = f" since {request.start_time.date().isoformat()}" if request.start_time else ""
            notice = (
                f"No outgoing transfers found{window} for this address, so there is nothing to trace "
                "(zero paths). Check the address and chain, widen the time window, or lower the "
                "minimum amount."
            )
        case["notice"] = notice

        # Score the traced paths so /risk, /alerts and /report work for this case
        run_assessment(
            case_id,
            InvestigationAssessRequest(
                chain=case["chain"],
                reported_address=reported_address,
                paths=_to_assess_paths(paths, case["chain"]),
                data_completeness=0.5 if tracer.connector_errors else 1.0,
                missing_data_notes="; ".join(tracer.connector_errors) or None,
            ),
        )

    except HTTPException:
        raise
    except Exception as err:
        logger.exception("Trace failed for case %s", case_id)
        # Never leak API keys or sensitive provider details in error details
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blockchain provider failed during transaction tracing",
        ) from err

    persisted = _store.persist_trace(case)
    if persisted is False:
        logger.warning("Trace for case %s could not be persisted to Supabase", case_id)
        warnings.append("Results could not be saved to the database and will be lost on restart.")

    return {
        "message": "Tracing started",
        "job_id": str(uuid.uuid4()),
        "case_id": case_id,
        "status": "completed",
        "paths_count": len(paths),
        "data_source": case["data_source"],
        "pruned_low_taint": tracer.pruned_low_taint,
        "intermediate_addresses": intermediate_addrs,
        "notice": notice,
        "warnings": warnings,
        "persisted": persisted,
    }



@router.get("/{case_id}/graph")
def get_graph(case_id: str):
    if _get_case(case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {case_id} not found",
        )
    case = _INVESTIGATIONS[case_id]
    if case.get("graph") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tracing has not been executed for this investigation",
        )
    return case["graph"]


# --- Recovery Layer Aliases on /api/investigations ---

@router.get("/{case_id}/ranking")
def get_investigation_ranking(case_id: str):
    from backend.recovery.ranking import global_ranking_engine
    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Investigation {case_id} not found")
    dossier = _get_or_404(case_id)
    rankings = global_ranking_engine.rank_destinations(dossier.paths, dossier.endpoints)
    return {
        "case_id": case_id,
        "destinations_ranked": [r.to_dict() for r in rankings],
        "advisory_notice": "Advisory only. Authorised investigator review required prior to hold action.",
    }


@router.get("/{case_id}/clock")
def get_investigation_clock(case_id: str):
    from backend.recovery.clock import global_recovery_clock
    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Investigation {case_id} not found")
    steps = global_recovery_clock.get_case_clock(case_id, check_overdue=True)
    return {
        "case_id": case_id,
        "timeline_steps": [s.to_dict() for s in steps],
        "overdue_count": sum(1 for s in steps if s.status == "overdue"),
    }


@router.patch("/{case_id}/clock/{step_id}")
def update_investigation_clock_step(case_id: str, step_id: str, status_payload: dict):
    from backend.recovery.clock import global_recovery_clock
    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Investigation {case_id} not found")
    try:
        new_status = status_payload.get("status", "done")
        updated = global_recovery_clock.update_step_status(case_id, step_id, new_status)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{case_id}/related")
def get_investigation_convergence(case_id: str):
    from backend.recovery.convergence import global_convergence_engine
    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Investigation {case_id} not found")
    return global_convergence_engine.get_network_view(case_id)


@router.get("/{case_id}/summary")
def get_investigation_summary(case_id: str):
    from backend.recovery.ranking import global_ranking_engine
    from backend.recovery.summary import global_summary_generator
    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Investigation {case_id} not found")
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
        typology=getattr(dossier, "typology", None),
    )
    return summary.to_dict()


@router.get("/{case_id}/clusters")
def get_investigation_clusters(case_id: str):
    from backend.clustering.engine import global_clustering_engine
    case = _get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Investigation {case_id} not found")
    dossier = _get_or_404(case_id)
    clusters = global_clustering_engine.analyze_clusters(dossier.paths)
    return {
        "case_id": case_id,
        "clusters_count": len(clusters),
        "clusters": [c.to_dict() for c in clusters],
    }
