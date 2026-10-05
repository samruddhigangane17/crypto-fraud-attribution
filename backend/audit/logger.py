"""Immutable Audit Logging Service for Chain of Custody and Reproducibility.

Section 6.3 & Section 8.9 / Feature 12:
Records tamper-evident audit records of:
- Searches & address submissions
- Parameter changes
- Label overrides
- Admin recovery rules updates
- Recovery clock step status changes
- Evidence report generation & cryptographic hash verifications

Every log entry captures event, actor, case_id, parameters, data_source, and timestamp.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    event_id: str = Field(default_factory=lambda: f"AUDIT-{uuid.uuid4().hex[:8].upper()}")
    case_id: Optional[str] = None
    event: str
    actor: str = "system"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    data_source: str = "internal"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entry_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AuditLogger:
    """Stores immutable audit logs in memory and coordinates with persistence."""

    def __init__(self):
        self._entries: List[AuditLogEntry] = []
        self._previous_hash: str = "GENESIS"

    def log_event(
        self,
        event: str,
        actor: str = "system",
        case_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        data_source: str = "internal",
    ) -> AuditLogEntry:
        """Appends a new audit log entry linked to previous entry hash for integrity."""
        params = parameters or {}
        entry = AuditLogEntry(
            case_id=case_id,
            event=event,
            actor=actor,
            parameters=params,
            data_source=data_source,
        )

        # Hash-chain the entry
        payload = f"{self._previous_hash}:{entry.event_id}:{entry.event}:{entry.actor}:{entry.timestamp}:{json.dumps(params, sort_keys=True)}"
        entry.entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._previous_hash = entry.entry_hash

        self._entries.append(entry)
        return entry

    def get_logs_for_case(self, case_id: str) -> List[AuditLogEntry]:
        """Returns all audit logs associated with a particular case."""
        return [e for e in self._entries if e.case_id == case_id]

    def get_all_logs(self, limit: int = 100) -> List[AuditLogEntry]:
        """Returns recent audit logs."""
        return list(reversed(self._entries[-limit:]))


global_audit_logger = AuditLogger()
