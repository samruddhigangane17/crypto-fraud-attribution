from datetime import datetime, timezone
from decimal import Decimal
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from backend.tracing.connectors.base import BaseConnector
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.etherscan import EtherscanConnector, EtherscanConnectorError
from backend.tracing.tracer import MultiHopTracer
from backend.tracing.graph import FlowGraphBuilder
from backend.tracing.analysis import WalletRelationshipAnalyzer
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


def _get_connector(reported_address: str) -> BaseConnector:
    """Select the appropriate connector without exposing API keys."""
    if _TEST_CONNECTOR is not None:
        return _TEST_CONNECTOR

    addr_lower = reported_address.lower()
    api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()

    # Use MockConnector if address starts with 0xmock_ or if no API key is configured
    if addr_lower.startswith("0xmock_") or not api_key:
        return MockConnector()

    return EtherscanConnector(api_key=api_key)


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
    min_taint_share: float = 0.05
    min_amount: Optional[Decimal] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None



@router.post("")
def create_investigation(case: InvestigationCreate):
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
        connector = _get_connector(reported_address)
        tracer = MultiHopTracer(
            connector=connector,
            max_hops=request.max_hops,
            min_amount=request.min_amount,
            start_time=request.start_time,
            end_time=request.end_time,
            investigation_id=case_id,
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



