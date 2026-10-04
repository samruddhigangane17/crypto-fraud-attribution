from datetime import datetime, timezone
from decimal import Decimal
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.etherscan import EtherscanConnector, EtherscanConnectorError
from backend.tracing.tracer import MultiHopTracer
from backend.tracing.graph import FlowGraphBuilder
from backend.tracing.analysis import WalletRelationshipAnalyzer
from backend.tracing.validation import is_demo_address, resolve_chain_and_address
from tests.mock_data import MOCK_ADDRESS_LABELS
from backend.api.routes import run_assessment
from backend.schemas.assessment import InvestigationAssessRequest
from backend.schemas.transaction import TracePath as AssessTracePath

router = APIRouter(prefix="/api/investigations", tags=["investigations"])

# In-memory storage for investigations during local development/session.
# NOTE: This is an ephemeral in-memory store and does not survive application restarts.
# In production, persistence is managed via Supabase by Member 3.
_INVESTIGATIONS: Dict[str, Dict[str, Any]] = {}

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

    if is_demo_address(reported_address):
        return MockConnector()

    if chain != "ethereum":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"No live data connector for '{chain}' yet. Only Ethereum is implemented.",
        )

    api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ETHERSCAN_API_KEY is not set on the server. Set it in .env, or use a 0xmock_ demo address.",
        )
    return EtherscanConnector(api_key=api_key)


def _data_source(connector: BaseConnector) -> str:
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
    }

    return {
        "id": case_id,
        "chain": case.chain,
        "reported_address": case.reported_address,
        "status": "Reported",
        "created_at": now_utc,
    }


@router.get("/{case_id}")
def get_investigation(case_id: str):
    if case_id not in _INVESTIGATIONS:
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
    }


@router.post("/{case_id}/trace")
def start_trace(case_id: str, request: TraceRequest, background_tasks: BackgroundTasks):
    if case_id not in _INVESTIGATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {case_id} not found",
        )
    case = _INVESTIGATIONS[case_id]
    reported_address = case["reported_address"]

    try:
        connector = _get_connector(case["chain"], reported_address)
        tracer = MultiHopTracer(
            connector=connector,
            max_hops=request.max_hops,
            min_amount=request.min_amount,
            start_time=request.start_time,
            end_time=request.end_time,
            investigation_id=case_id,
            min_taint_share=request.min_taint_share,
        )
        paths = tracer.trace(reported_address)
        if tracer.connector_errors and not paths:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Blockchain provider failed during transaction tracing",
            )

        labels = {
            item["address"].lower(): item["entity_name"]
            for item in MOCK_ADDRESS_LABELS
        }
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
        # Never leak API keys or sensitive provider details in error details
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blockchain provider failed during transaction tracing",
        ) from err

    return {
        "message": "Tracing started",
        "job_id": str(uuid.uuid4()),
        "case_id": case_id,
        "status": "completed",
        "paths_count": len(paths),
        "data_source": case["data_source"],
        "pruned_low_taint": tracer.pruned_low_taint,
        "intermediate_addresses": intermediate_addrs,
    }



@router.get("/{case_id}/graph")
def get_graph(case_id: str):
    if case_id not in _INVESTIGATIONS:
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



