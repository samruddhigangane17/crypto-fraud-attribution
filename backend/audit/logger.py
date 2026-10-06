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
Audit logs are persisted durably to the Supabase `audit_logs` table with in-memory caching
and hash-chain continuity across server restarts.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from backend.database.supabase_client import SupabaseClient, global_supabase_client

logger = logging.getLogger("crypto_attribution.audit")

SENSITIVE_KEY_PATTERNS = {
    "key",
    "secret",
    "password",
    "token",
    "auth",
    "cred",
    "private",
    "jwt",
    "seed",
    "mnemonic",
}


def sanitize_parameters(data: Any) -> Any:
    """Recursively redacts sensitive values such as API keys, tokens, and passwords."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(pattern in k_lower for pattern in SENSITIVE_KEY_PATTERNS):
                sanitized[str(k)] = "[REDACTED]"
            else:
                sanitized[str(k)] = sanitize_parameters(v)
        return sanitized
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_parameters(item) for item in data]
    elif hasattr(data, "isoformat"):
        return data.isoformat()
    elif isinstance(data, (int, float, bool, str)) or data is None:
        return data
    else:
        return str(data)


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

    def __init__(self, supabase: Optional[SupabaseClient] = None):
        self.supabase = supabase or global_supabase_client
        self._entries: List[AuditLogEntry] = []
        self._previous_hash: str = "GENESIS"
        self._initialized: bool = False

    def _ensure_initialized(self) -> None:
        """Loads existing audit entries from database on startup/first access to restore hash-chain."""
        if self._initialized:
            return
        self._initialized = True

        if not self.supabase or not self.supabase.is_configured:
            return

        try:
            rows = self.supabase.select_sync("audit_logs", {"order": "timestamp.asc"})
            if rows:
                loaded = []
                for r in rows:
                    try:
                        loaded.append(self._row_to_entry(r))
                    except Exception as err:
                        logger.warning("Error parsing audit log row from database: %s", err)
                if loaded:
                    # Merge with existing in-memory entries if any
                    existing_ids = {e.event_id for e in loaded}
                    for mem_entry in self._entries:
                        if mem_entry.event_id not in existing_ids:
                            loaded.append(mem_entry)
                    self._entries = loaded
                    self._previous_hash = loaded[-1].entry_hash or "GENESIS"
                    logger.info(
                        "Restored %d audit logs from database; head hash: %s",
                        len(loaded),
                        self._previous_hash[:16],
                    )
        except Exception as e:
            logger.warning("Could not restore audit logs from database: %s", e)

    @staticmethod
    def _row_to_entry(row: Dict[str, Any]) -> AuditLogEntry:
        return AuditLogEntry(
            event_id=row["event_id"],
            case_id=row.get("case_id"),
            event=row["event"],
            actor=row.get("actor", "system"),
            parameters=row.get("parameters") or {},
            data_source=row.get("data_source", "internal"),
            timestamp=str(row.get("timestamp")),
            entry_hash=row.get("entry_hash"),
        )

    def log_event(
        self,
        event: str,
        actor: str = "system",
        case_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        data_source: str = "internal",
    ) -> AuditLogEntry:
        """Appends a new audit log entry linked to previous entry hash for integrity and persists it."""
        self._ensure_initialized()

        raw_params = parameters or {}
        sanitized_params = sanitize_parameters(raw_params)

        entry = AuditLogEntry(
            case_id=case_id,
            event=event,
            actor=actor,
            parameters=sanitized_params,
            data_source=data_source,
        )

        # Hash-chain the entry
        payload = f"{self._previous_hash}:{entry.event_id}:{entry.event}:{entry.actor}:{entry.timestamp}:{json.dumps(sanitized_params, sort_keys=True)}"
        entry.entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._previous_hash = entry.entry_hash

        self._entries.append(entry)

        # Durably persist to database
        if self.supabase and self.supabase.is_configured:
            try:
                row = {
                    "event_id": entry.event_id,
                    "case_id": entry.case_id,
                    "event": entry.event,
                    "actor": entry.actor,
                    "parameters": entry.parameters,
                    "data_source": entry.data_source,
                    "timestamp": entry.timestamp,
                    "entry_hash": entry.entry_hash,
                }
                ok = self.supabase.insert_sync("audit_logs", row)
                if not ok:
                    logger.warning(
                        "Audit persistence failed for event %s (case %s); retained in memory.",
                        entry.event_id,
                        entry.case_id,
                    )
            except Exception as e:
                logger.error(
                    "Unexpected error persisting audit log entry %s: %s",
                    entry.event_id,
                    e,
                    exc_info=True,
                )

        return entry

    def get_logs_for_case(self, case_id: str) -> List[AuditLogEntry]:
        """Returns all audit logs associated with a particular case from DB or memory."""
        self._ensure_initialized()

        if self.supabase and self.supabase.is_configured:
            try:
                rows = self.supabase.select_sync(
                    "audit_logs",
                    {"case_id": f"eq.{case_id}", "order": "timestamp.asc"},
                )
                if rows is not None:
                    db_entries = [self._row_to_entry(r) for r in rows]
                    db_ids = {e.event_id for e in db_entries}
                    # Add any in-memory entries that match case_id but aren't in DB yet
                    for e in self._entries:
                        if e.case_id == case_id and e.event_id not in db_ids:
                            db_entries.append(e)
                    return db_entries
            except Exception as e:
                logger.warning("Failed to query audit logs for case %s from database: %s", case_id, e)

        return [e for e in self._entries if e.case_id == case_id]

    def get_all_logs(self, limit: int = 100) -> List[AuditLogEntry]:
        """Returns recent audit logs from DB or memory."""
        self._ensure_initialized()

        if self.supabase and self.supabase.is_configured:
            try:
                rows = self.supabase.select_sync(
                    "audit_logs",
                    {"order": "timestamp.desc", "limit": str(limit)},
                )
                if rows is not None:
                    db_entries = [self._row_to_entry(r) for r in rows]
                    db_ids = {e.event_id for e in db_entries}
                    # Merge any memory entries that might not be in DB yet
                    recent_mem = list(reversed(self._entries[-limit:]))
                    for e in recent_mem:
                        if e.event_id not in db_ids:
                            db_entries.append(e)
                    return db_entries[:limit]
            except Exception as e:
                logger.warning("Failed to query all audit logs from database: %s", e)

        return list(reversed(self._entries[-limit:]))

    def verify_hash_chain(self, entries: Optional[List[AuditLogEntry]] = None) -> bool:
        """Verifies cryptographic integrity of the audit trail.

        Returns True if every entry's hash matches SHA-256(prev_hash:entry_data)
        starting from GENESIS.
        """
        if entries is None:
            self._ensure_initialized()
            if self.supabase and self.supabase.is_configured:
                try:
                    rows = self.supabase.select_sync("audit_logs", {"order": "timestamp.asc"})
                    if rows is not None:
                        entries = [self._row_to_entry(r) for r in rows]
                except Exception as e:
                    logger.warning("Failed to fetch logs for hash verification: %s", e)
            if entries is None:
                entries = self._entries

        prev_hash = "GENESIS"
        for entry in entries:
            payload = f"{prev_hash}:{entry.event_id}:{entry.event}:{entry.actor}:{entry.timestamp}:{json.dumps(entry.parameters, sort_keys=True)}"
            computed_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if entry.entry_hash != computed_hash:
                logger.warning(
                    "Audit hash mismatch on %s: recorded=%s, computed=%s",
                    entry.event_id,
                    entry.entry_hash,
                    computed_hash,
                )
                return False
            prev_hash = entry.entry_hash
        return True


global_audit_logger = AuditLogger()
