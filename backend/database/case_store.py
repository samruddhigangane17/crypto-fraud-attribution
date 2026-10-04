"""Durable storage for investigations, trace paths and the fund-flow graph.

Cases are always held in memory for speed. When Supabase is configured they are also written
through to PostgreSQL (tables `investigations` and `trace_paths`) so they survive a restart,
and a case missing from memory is reloaded from the database on demand.

Writes are best-effort: a Supabase outage is logged and reported (`persisted: false`) but never
fails the investigation itself.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder

from backend.database.supabase_client import SupabaseClient, global_supabase_client
from backend.schemas.path import TracePath

logger = logging.getLogger("crypto_attribution.case_store")

# In-memory status -> DB status (the table CHECK allows active/completed/monitoring/archived)
_TO_DB_STATUS = {"Reported": "active", "completed": "completed"}
_FROM_DB_STATUS = {"active": "Reported", "completed": "completed", "monitoring": "completed", "archived": "completed"}


class CaseStore:
    def __init__(self, cases: Dict[str, Dict[str, Any]], supabase: Optional[SupabaseClient] = None):
        self.cases = cases
        self.supabase = supabase or global_supabase_client

    @property
    def durable(self) -> bool:
        return self.supabase.is_configured

    # ---- writes -----------------------------------------------------------------------
    def persist_case(self, case: Dict[str, Any]) -> Optional[bool]:
        """Write the investigation row (create or update). None if Supabase isn't configured."""
        if not self.durable:
            return None
        row = {
            "id": case["id"],
            "chain": case["chain"],
            "reported_address": case["reported_address"],
            "status": _TO_DB_STATUS.get(case.get("status"), "active"),
            "data_source": case.get("data_source"),
            "notice": case.get("notice"),
            "created_at": case.get("created_at"),
        }
        if case.get("graph") is not None:
            row["graph_data"] = jsonable_encoder(case["graph"])
        if case.get("analysis") is not None:
            row["analysis"] = jsonable_encoder(case["analysis"])
        return self.supabase.upsert_sync("investigations", row, on_conflict="id")

    def persist_trace(self, case: Dict[str, Any]) -> Optional[bool]:
        """Write the investigation, then replace its trace paths. None if not configured."""
        if not self.durable:
            return None
        if not self.persist_case(case):
            return False
        case_id = case["id"]
        # Replace rather than append so re-tracing a case never leaves stale paths behind.
        if not self.supabase.delete_sync("trace_paths", {"investigation_id": f"eq.{case_id}"}):
            return False
        rows = []
        for p in case.get("paths") or []:
            first = p.transactions[0] if p.transactions else None
            rows.append(
                {
                    "investigation_id": case_id,
                    "chain": case["chain"],
                    "start_address": first.from_address if first else case["reported_address"],
                    "end_address": p.end_address,
                    "hop_count": p.hop_count,
                    "path_data": jsonable_encoder(p.model_dump(mode="json")),
                    "total_volume": str(first.amount) if first else "0",
                    "is_terminal_endpoint": False,
                }
            )
        return self.supabase.insert_sync("trace_paths", rows) if rows else True

    # ---- reads ------------------------------------------------------------------------
    def load(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Reload a case from Supabase into memory. Returns None if absent/unavailable."""
        if not self.durable:
            return None
        rows = self.supabase.select_sync("investigations", {"id": f"eq.{case_id}"})
        if not rows:
            return None
        row = rows[0]
        path_rows = self.supabase.select_sync("trace_paths", {"investigation_id": f"eq.{case_id}"}) or []

        paths: List[TracePath] = []
        for pr in path_rows:
            try:
                paths.append(TracePath.model_validate(pr["path_data"]))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Skipping unreadable stored path for case {case_id}: {e}")

        status = _FROM_DB_STATUS.get(row.get("status"), "Reported")
        case: Dict[str, Any] = {
            "id": row["id"],
            "chain": row["chain"],
            "reported_address": row["reported_address"],
            "amount": None,
            "timestamp": None,
            "status": status,
            "created_at": row.get("created_at"),
            "graph": row.get("graph_data"),
            "paths": paths if status == "completed" else None,
            "analysis": row.get("analysis"),
            "data_source": row.get("data_source"),
            "notice": row.get("notice"),
            "intermediate_addresses": sorted({a for p in paths for a in p.intermediate_addresses}),
        }
        self.cases[case_id] = case
        return case
