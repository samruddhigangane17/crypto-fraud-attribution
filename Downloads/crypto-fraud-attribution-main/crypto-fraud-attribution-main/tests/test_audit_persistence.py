"""Automated tests for persistent, tamper-evident audit logging.

Covers:
- Audit event creation and field compliance
- Durability/persistence in database (Supabase adapter)
- Retrieval by case_id and retrieval of all logs
- Hash-chain integrity and tamper detection
- Continuity and verification across logger/backend reinitialization (restart)
- Sensitive credentials/secrets redaction
- Safe handling of database write and read failures
- API contract via GET /api/v1/audit/logs
"""

import copy
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from backend.audit.logger import (
    AuditLogEntry,
    AuditLogger,
    sanitize_parameters,
    global_audit_logger,
)
from backend.database.supabase_client import SupabaseClient
from backend.main import app

client = TestClient(app)


class FakeAuditSupabase(SupabaseClient):
    """In-memory Supabase test double that simulates PostgREST table storage."""

    def __init__(self):
        super().__init__(base_url="https://mock-test.supabase.co", api_key="test-key")
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self.should_fail_insert: bool = False
        self.should_fail_select: bool = False

    def insert_sync(self, table: str, records: Any) -> bool:
        if self.should_fail_insert:
            return False
        rows = records if isinstance(records, list) else [records]
        self.tables.setdefault(table, []).extend(copy.deepcopy(rows))
        return True

    def select_sync(self, table: str, filters: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
        if self.should_fail_select:
            return None
        rows = copy.deepcopy(self.tables.get(table, []))

        # Filter by equality
        for k, v in filters.items():
            if k in ("order", "limit"):
                continue
            if v.startswith("eq."):
                target_val = v[3:]
                rows = [r for r in rows if str(r.get(k)) == target_val]

        # Handle order
        if "order" in filters:
            order_spec = filters["order"]
            col, direction = order_spec.split(".")
            indexed_rows = list(enumerate(rows))
            if direction == "desc":
                indexed_rows.sort(key=lambda item: (str(item[1].get(col, "")), item[0]), reverse=True)
            else:
                indexed_rows.sort(key=lambda item: (str(item[1].get(col, "")), item[0]))
            rows = [item[1] for item in indexed_rows]

        # Handle limit
        if "limit" in filters:
            lim = int(filters["limit"])
            rows = rows[:lim]

        return rows


def test_audit_event_creation_and_fields():
    """Verify that AuditLogEntry creates all required fields according to specification."""
    logger = AuditLogger(supabase=FakeAuditSupabase())
    entry = logger.log_event(
        event="rule_updated",
        actor="lead_investigator@agency.gov",
        case_id="CASE-101",
        parameters={"rule_name": "l1_freeze", "old_hours": 1.0, "new_hours": 0.5},
        data_source="admin_portal",
    )

    assert entry.event_id.startswith("AUDIT-")
    assert entry.case_id == "CASE-101"
    assert entry.event == "rule_updated"
    assert entry.actor == "lead_investigator@agency.gov"
    assert entry.data_source == "admin_portal"
    assert entry.parameters["rule_name"] == "l1_freeze"
    assert entry.parameters["new_hours"] == 0.5
    assert entry.timestamp is not None
    assert entry.entry_hash is not None
    assert len(entry.entry_hash) == 64  # SHA-256 hexdigest length

    d = entry.to_dict()
    assert d["event_id"] == entry.event_id
    assert d["entry_hash"] == entry.entry_hash


def test_audit_event_persistence():
    """Verify that log_event writes through to the database table."""
    fake_db = FakeAuditSupabase()
    logger = AuditLogger(supabase=fake_db)

    entry = logger.log_event(
        event="step_status_changed",
        actor="analyst@crypto.org",
        case_id="CASE-202",
        parameters={"step_id": "step_1", "status": "completed"},
        data_source="clock_manager",
    )

    persisted_rows = fake_db.tables.get("audit_logs", [])
    assert len(persisted_rows) == 1
    row = persisted_rows[0]
    assert row["event_id"] == entry.event_id
    assert row["case_id"] == "CASE-202"
    assert row["event"] == "step_status_changed"
    assert row["actor"] == "analyst@crypto.org"
    assert row["entry_hash"] == entry.entry_hash
    assert row["parameters"] == {"step_id": "step_1", "status": "completed"}


def test_audit_sensitive_parameter_redaction():
    """Verify that credentials, secrets, and auth tokens are redacted before hashing and storage."""
    fake_db = FakeAuditSupabase()
    logger = AuditLogger(supabase=fake_db)

    sensitive_params = {
        "api_key": "secret-live-key-xyz",
        "auth_token": "bearer eyJhbGciOi...",
        "user_password": "supersecretpassword123",
        "private_key": "0xabc123deadbeef",
        "nested": {
            "jwt_secret": "my-secret",
            "normal_field": "safe_value",
        },
        "safe_number": 42,
    }

    entry = logger.log_event(
        event="auth_action",
        case_id="CASE-SEC-01",
        parameters=sensitive_params,
    )

    # In-memory entry must be redacted
    assert entry.parameters["api_key"] == "[REDACTED]"
    assert entry.parameters["auth_token"] == "[REDACTED]"
    assert entry.parameters["user_password"] == "[REDACTED]"
    assert entry.parameters["private_key"] == "[REDACTED]"
    assert entry.parameters["nested"]["jwt_secret"] == "[REDACTED]"
    assert entry.parameters["nested"]["normal_field"] == "safe_value"
    assert entry.parameters["safe_number"] == 42

    # Database row must also be redacted
    stored_row = fake_db.tables["audit_logs"][0]
    assert stored_row["parameters"]["api_key"] == "[REDACTED]"
    assert stored_row["parameters"]["auth_token"] == "[REDACTED]"


def test_audit_retrieval_by_case_id():
    """Verify filtering logs by case_id and querying all logs."""
    fake_db = FakeAuditSupabase()
    logger = AuditLogger(supabase=fake_db)

    logger.log_event(event="e1", case_id="CASE-A")
    logger.log_event(event="e2", case_id="CASE-B")
    logger.log_event(event="e3", case_id="CASE-A")
    logger.log_event(event="e4", case_id=None)

    case_a_logs = logger.get_logs_for_case("CASE-A")
    assert len(case_a_logs) == 2
    assert [e.event for e in case_a_logs] == ["e1", "e3"]

    case_b_logs = logger.get_logs_for_case("CASE-B")
    assert len(case_b_logs) == 1
    assert case_b_logs[0].event == "e2"

    all_logs = logger.get_all_logs(limit=10)
    assert len(all_logs) == 4
    # Newest first
    assert all_logs[0].event == "e4"
    assert all_logs[-1].event == "e1"


def test_hash_chain_integrity_and_tamper_detection():
    """Verify SHA-256 hash-chain integrity check and that tampering breaks the chain."""
    logger = AuditLogger(supabase=FakeAuditSupabase())

    e1 = logger.log_event(event="init", case_id="CASE-CHAIN")
    e2 = logger.log_event(event="progress", case_id="CASE-CHAIN")
    e3 = logger.log_event(event="finish", case_id="CASE-CHAIN")

    # The chain should verify successfully
    assert logger.verify_hash_chain() is True

    # Tamper with an entry in the list
    tampered_entries = copy.deepcopy(logger.get_logs_for_case("CASE-CHAIN"))
    tampered_entries[1].parameters["injected"] = "malicious_change"
    assert logger.verify_hash_chain(tampered_entries) is False

    # Tamper with a hash
    tampered_entries2 = copy.deepcopy(logger.get_logs_for_case("CASE-CHAIN"))
    tampered_entries2[1].entry_hash = "0" * 64
    assert logger.verify_hash_chain(tampered_entries2) is False


def test_audit_survives_reinitialization():
    """Verify that audit records and hash-chain continuity survive logger/server restarts."""
    shared_db = FakeAuditSupabase()

    # Session 1: Logger records 3 events
    session1_logger = AuditLogger(supabase=shared_db)
    e1 = session1_logger.log_event(event="step_1", case_id="CASE-RESTART", parameters={"v": 1})
    e2 = session1_logger.log_event(event="step_2", case_id="CASE-RESTART", parameters={"v": 2})
    e3 = session1_logger.log_event(event="step_3", case_id="CASE-RESTART", parameters={"v": 3})

    assert session1_logger.verify_hash_chain() is True
    session1_head_hash = e3.entry_hash

    # Simulate server restart: new AuditLogger instance with the same database
    session2_logger = AuditLogger(supabase=shared_db)

    # Verify logs can be retrieved after restart
    reloaded_logs = session2_logger.get_logs_for_case("CASE-RESTART")
    assert len(reloaded_logs) == 3
    assert [e.event for e in reloaded_logs] == ["step_1", "step_2", "step_3"]

    # Verify that existing chain is valid in session 2
    assert session2_logger.verify_hash_chain() is True

    # Log new event in session 2
    e4 = session2_logger.log_event(event="step_4", case_id="CASE-RESTART", parameters={"v": 4})

    # The new event must link back to session 1's head hash
    assert e4.entry_hash != session1_head_hash
    # The full chain (events 1..4) must still verify end-to-end
    assert session2_logger.verify_hash_chain() is True


def test_audit_safe_failure_handling():
    """Verify that database write failure does not break log_event or raise exceptions."""
    failing_db = FakeAuditSupabase()
    failing_db.should_fail_insert = True

    logger = AuditLogger(supabase=failing_db)

    # Should not raise an exception despite database write failure
    entry = logger.log_event(
        event="critical_step",
        case_id="CASE-FAILSAFE",
        parameters={"step": "freeze_funds"},
    )

    assert entry is not None
    assert entry.event == "critical_step"

    # Falls back to in-memory entries safely
    logs = logger.get_logs_for_case("CASE-FAILSAFE")
    assert len(logs) == 1
    assert logs[0].event == "critical_step"


def test_api_v1_audit_logs_endpoints(monkeypatch):
    """Verify that GET /api/v1/audit/logs and GET /api/v1/audit/logs?case_id=... return persistent entries."""
    test_db = FakeAuditSupabase()
    test_logger = AuditLogger(supabase=test_db)
    test_logger.log_event(event="api_test_event_1", case_id="CASE-API-101")
    test_logger.log_event(event="api_test_event_2", case_id="CASE-API-202")

    monkeypatch.setattr("backend.api.v1.cases.global_audit_logger", test_logger)

    # Query all logs
    res_all = client.get("/api/v1/audit/logs")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert isinstance(data_all, list)
    event_names = [d["event"] for d in data_all]
    assert "api_test_event_1" in event_names
    assert "api_test_event_2" in event_names

    # Query by case_id
    res_case = client.get("/api/v1/audit/logs?case_id=CASE-API-101")
    assert res_case.status_code == 200
    data_case = res_case.json()
    assert len(data_case) == 1
    assert data_case[0]["case_id"] == "CASE-API-101"
    assert data_case[0]["event"] == "api_test_event_1"
    assert "entry_hash" in data_case[0]
