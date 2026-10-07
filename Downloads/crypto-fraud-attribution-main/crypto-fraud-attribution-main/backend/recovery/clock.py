"""Recovery Clock and Rules Table Manager.

Section 8.11 / Feature 16 / TC-14, TC-15, TC-16:
A per-case timeline of time-sensitive recovery steps:
1. I4C Report Logged
2. Preservation Notice to VASP
3. Formal Freezing Request Submitted
4. VASP Compliance Acknowledgement
5. Legal Process / Court Order Filing

Each step tracks owner, due rule, due time, elapsed time, and status:
'pending', 'sent', 'acknowledged', 'done', 'overdue'.

The rules table is stored as configurable data (editable by admin with audit logging).
Overdue steps automatically raise alerts.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class TimingRule(BaseModel):
    rule_id: str
    step_type: str
    title: str
    owner: str  # "investigator", "i4c_cell", "vasp_compliance", "legal_team"
    due_hours: float
    description: str
    editable_by_admin: bool = True
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


DEFAULT_RULES: List[TimingRule] = [
    TimingRule(
        rule_id="RULE-1",
        step_type="i4c_report_logged",
        title="Report Logged with I4C / NCRP",
        owner="Investigator",
        due_hours=2.0,
        description="Formal entry and initial acknowledgment of complaint in Indian Cyber Crime Coordination Centre feed.",
    ),
    TimingRule(
        rule_id="RULE-2",
        step_type="preservation_notice_sent",
        title="Preservation Notice to VASP",
        owner="I4C Cell",
        due_hours=6.0,
        description="Emergency preservation notice transmitted to destination exchange compliance team to retain logs and hold session.",
    ),
    TimingRule(
        rule_id="RULE-3",
        step_type="freeze_request_submitted",
        title="Formal Freezing Request Submitted",
        owner="I4C Cell",
        due_hours=12.0,
        description="Official Section 91 CrPC/BNSS or emergency freezing order served to destination VASP.",
    ),
    TimingRule(
        rule_id="RULE-4",
        step_type="vasp_acknowledgement",
        title="VASP Compliance Acknowledgement",
        owner="VASP Compliance",
        due_hours=24.0,
        description="Formal confirmation from exchange legal compliance department that assets are held.",
    ),
    TimingRule(
        rule_id="RULE-5",
        step_type="legal_court_order",
        title="Judicial Magistrate / Special Court Confirmation",
        owner="Legal Team",
        due_hours=72.0,
        description="Filing of judicial confirmation order for seizure and custody of cryptocurrency.",
    ),
]


class RecoveryStep(BaseModel):
    step_id: str
    case_id: str
    step_type: str
    title: str
    owner: str
    due_rule_hours: float
    due_time: str
    status: str = "pending"  # "pending", "sent", "acknowledged", "done", "overdue"
    created_at: str
    completed_at: Optional[str] = None
    elapsed_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RecoveryClockManager:
    """Manages configurable timing rules and per-case recovery clock timelines."""

    def __init__(self):
        # Admin-configurable rules table: step_type -> TimingRule
        self.rules: Dict[str, TimingRule] = {r.step_type: r.model_copy() for r in DEFAULT_RULES}
        # Case recovery clocks: case_id -> List[RecoveryStep]
        self._case_clocks: Dict[str, List[RecoveryStep]] = {}

    def get_rules(self) -> List[TimingRule]:
        """Returns the current configurable timing rules."""
        return list(self.rules.values())

    def update_rule(self, step_type: str, due_hours: float, actor: str = "admin") -> TimingRule:
        """Update a timing rule. Audit-logged."""
        if step_type not in self.rules:
            raise ValueError(f"Unknown rule step_type: {step_type}")
        rule = self.rules[step_type]
        old_hours = rule.due_hours
        rule.due_hours = max(0.1, due_hours)
        rule.last_updated = datetime.now(timezone.utc).isoformat()

        # Audit log event
        from backend.audit.logger import global_audit_logger
        global_audit_logger.log_event(
            event="rule_updated",
            actor=actor,
            parameters={"step_type": step_type, "old_due_hours": old_hours, "new_due_hours": rule.due_hours},
            data_source="admin_rules_table",
        )
        return rule

    def create_clock_for_case(
        self,
        case_id: str,
        start_time: Optional[datetime] = None,
    ) -> List[RecoveryStep]:
        """Initializes the recovery clock timeline for a new case using active rules table."""
        base_time = start_time or datetime.now(timezone.utc)
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)

        steps: List[RecoveryStep] = []
        for idx, rule in enumerate(self.rules.values(), start=1):
            due_dt = base_time + timedelta(hours=rule.due_hours)
            steps.append(
                RecoveryStep(
                    step_id=f"STEP-{idx}",
                    case_id=case_id,
                    step_type=rule.step_type,
                    title=rule.title,
                    owner=rule.owner,
                    due_rule_hours=rule.due_hours,
                    due_time=due_dt.isoformat(),
                    status="pending",
                    created_at=base_time.isoformat(),
                    elapsed_hours=0.0,
                )
            )

        self._case_clocks[case_id] = steps
        return steps

    def get_case_clock(
        self,
        case_id: str,
        check_overdue: bool = True,
        reference_time: Optional[datetime] = None,
    ) -> List[RecoveryStep]:
        """Returns the clock steps for a case, updating elapsed hours and overdue statuses."""
        steps = self._case_clocks.get(case_id)
        if not steps:
            steps = self.create_clock_for_case(case_id)

        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        alerts_to_raise = []
        for s in steps:
            # Calculate elapsed time
            created_dt = datetime.fromisoformat(s.created_at.replace("Z", "+00:00"))
            s.elapsed_hours = round(max(0.0, (now - created_dt).total_seconds() / 3600.0), 2)

            # Check if overdue
            if check_overdue and s.status not in ("done", "acknowledged"):
                due_dt = datetime.fromisoformat(s.due_time.replace("Z", "+00:00"))
                if now > due_dt:
                    if s.status != "overdue":
                        s.status = "overdue"
                        alerts_to_raise.append(s)

        # Raise alerts for newly overdue steps
        if alerts_to_raise:
            from backend.monitoring.alerts import global_alert_engine
            from backend.schemas.monitoring import AlertSeverity, AlertType
            for overdue_step in alerts_to_raise:
                global_alert_engine.generate_alert(
                    investigation_id=case_id,
                    target_address=overdue_step.owner,
                    tx_hash=f"CLOCK-{overdue_step.step_id}",
                    alert_type=AlertType.OVERDUE_RECOVERY_STEP,
                    severity=AlertSeverity.HIGH,
                    title=f"Golden Hour Alert: Step Overdue ({overdue_step.title})",
                    message=(
                        f"Step '{overdue_step.title}' assigned to {overdue_step.owner} is overdue! "
                        f"Due after {overdue_step.due_rule_hours}h. Rapid action required to prevent fund dissipation."
                    ),
                    metadata={"step_id": overdue_step.step_id, "due_time": overdue_step.due_time},
                )

        return steps

    def update_step_status(
        self,
        case_id: str,
        step_id: str,
        status: str,
        actor: str = "investigator",
    ) -> RecoveryStep:
        """Update the status of a specific recovery step."""
        steps = self.get_case_clock(case_id, check_overdue=False)
        target = next((s for s in steps if s.step_id.lower() == step_id.lower() or s.step_type.lower() == step_id.lower()), None)
        if not target:
            raise ValueError(f"Step '{step_id}' not found for case '{case_id}'")

        target.status = status.lower()
        if target.status in ("done", "acknowledged"):
            target.completed_at = datetime.now(timezone.utc).isoformat()

        # Audit log step status change
        from backend.audit.logger import global_audit_logger
        global_audit_logger.log_event(
            event="recovery_step_updated",
            actor=actor,
            case_id=case_id,
            parameters={"step_id": target.step_id, "step_type": target.step_type, "new_status": target.status},
            data_source="recovery_clock",
        )
        return target


global_recovery_clock = RecoveryClockManager()
