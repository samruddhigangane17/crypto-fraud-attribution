"""Schemas for continuous monitoring jobs and deduplicated alerting."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    ENDPOINT_HIT = "endpoint_hit"             # Funds entered a known exchange/VASP
    MIXER_INTERACTION = "mixer_interaction"   # Interaction with privacy mixer detected
    LARGE_OUTFLOW = "large_outflow"           # Substantial volume movement
    NEW_TRANSACTION = "new_transaction"       # New transaction on watched wallet
    NEW_HOP_DETECTED = "new_hop_detected"     # Funds traversed another hop
    HIGH_RISK_INTERACTION = "high_risk_interaction" # Funds moved to known scam/sanctioned address


class AlertStatus(str, Enum):
    NEW = "NEW"
    READ = "READ"
    DISMISSED = "DISMISSED"


class Alert(BaseModel):
    id: str = Field(..., description="Unique UUID for this alert")
    investigation_id: str
    event_key: str = Field(..., description="Deterministic deduplication key, e.g. sha256(case_id + tx_hash + alert_type)")
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    target_address: str
    tx_hash: Optional[str] = None
    hop_number: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: AlertStatus = Field(default=AlertStatus.NEW)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MonitoringConfig(BaseModel):
    investigation_id: str
    chain: str
    watched_addresses: List[str]
    is_active: bool = True
    hop_limit: int = Field(default=4, ge=1, le=10)
    check_interval_seconds: int = Field(default=300, ge=30)
    last_checked_at: Optional[str] = None
    alert_on_exchange_deposit: bool = True
    alert_on_mixer: bool = True
    alert_on_new_tx: bool = True
    min_amount_threshold: Optional[str] = None
