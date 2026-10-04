"""Alert generation and deterministic deduplication engine.

Guarantees that repeated monitoring cycles or overlapping polling runs
never generate duplicate alerts for the same event or transaction.
"""

import hashlib
from typing import Dict, List, Optional, Set
import uuid

from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.monitoring import Alert, AlertSeverity, AlertStatus, AlertType, MonitoringConfig
from backend.schemas.transaction import NormalizedTransaction


class AlertEngine:
    """Creates, deduplicates, and manages investigation alerts."""

    def __init__(self):
        # In-memory store: investigation_id -> list of alerts
        self._alerts_by_case: Dict[str, List[Alert]] = {}
        # Deduplication index: set of event_keys
        self._seen_event_keys: Set[str] = set()

    @staticmethod
    def compute_event_key(
        investigation_id: str,
        tx_hash: Optional[str],
        alert_type: AlertType,
        target_address: str,
    ) -> str:
        """Generates a deterministic SHA256 deduplication key."""
        raw = f"{investigation_id}:{tx_hash or 'no_tx'}:{alert_type.value}:{target_address.lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_alert(
        self,
        investigation_id: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        target_address: str,
        tx_hash: Optional[str] = None,
        hop_number: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Alert]:
        """Creates an alert if not already seen.

        Returns None if duplicate event key was already processed.
        """
        event_key = self.compute_event_key(
            investigation_id=investigation_id,
            tx_hash=tx_hash,
            alert_type=alert_type,
            target_address=target_address,
        )

        # Deduplication check
        if event_key in self._seen_event_keys:
            return None

        # Record new alert
        self._seen_event_keys.add(event_key)
        alert = Alert(
            id=str(uuid.uuid4()),
            investigation_id=investigation_id,
            event_key=event_key,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            target_address=target_address,
            tx_hash=tx_hash,
            hop_number=hop_number,
            metadata=metadata or {},
            status=AlertStatus.NEW,
        )

        if investigation_id not in self._alerts_by_case:
            self._alerts_by_case[investigation_id] = []
        self._alerts_by_case[investigation_id].append(alert)

        return alert

    def evaluate_transaction_for_alerts(
        self,
        investigation_id: str,
        tx: NormalizedTransaction,
        hop_number: int,
        match: Optional[EndpointMatchResult],
        config: MonitoringConfig,
    ) -> List[Alert]:
        """Inspects an observed transaction and generates appropriate alerts."""
        generated: List[Alert] = []

        # 1. Check for Exchange / VASP Deposit
        if config.alert_on_exchange_deposit and match and match.is_matched and match.label:
            if match.label.entity_category == EntityCategory.EXCHANGE_VASP:
                alert = self.generate_alert(
                    investigation_id=investigation_id,
                    alert_type=AlertType.ENDPOINT_HIT,
                    severity=AlertSeverity.HIGH if hop_number <= 2 else AlertSeverity.WARNING,
                    title=f"Funds Deposited to Exchange: {match.label.entity_name}",
                    message=(
                        f"Transfer of {tx.amount} {tx.asset_symbol} reached verified exchange endpoint "
                        f"'{match.label.entity_name}' at hop {hop_number}. Tx: {tx.tx_hash}"
                    ),
                    target_address=tx.to_address,
                    tx_hash=tx.tx_hash,
                    hop_number=hop_number,
                    metadata={
                        "entity_name": match.label.entity_name,
                        "entity_category": match.label.entity_category.value,
                        "amount": tx.amount,
                        "asset": tx.asset_symbol,
                    },
                )
                if alert:
                    generated.append(alert)

            # 2. Check for Privacy Mixer interaction
            elif match.label.entity_category == EntityCategory.MIXER:
                if config.alert_on_mixer:
                    alert = self.generate_alert(
                        investigation_id=investigation_id,
                        alert_type=AlertType.MIXER_INTERACTION,
                        severity=AlertSeverity.CRITICAL,
                        title=f"Mixer Interaction Detected: {match.label.entity_name}",
                        message=(
                            f"Funds routed to privacy mixer '{match.label.entity_name}' at hop {hop_number}. "
                            "Immediate obfuscation risk identified."
                        ),
                        target_address=tx.to_address,
                        tx_hash=tx.tx_hash,
                        hop_number=hop_number,
                        metadata={
                            "mixer_name": match.label.entity_name,
                            "amount": tx.amount,
                            "asset": tx.asset_symbol,
                        },
                    )
                    if alert:
                        generated.append(alert)

            # 3. Check for Sanctioned / Scam Flagged Wallets
            elif match.label.entity_category in {EntityCategory.SANCTIONED, EntityCategory.SCAM_FRAUD}:
                alert = self.generate_alert(
                    investigation_id=investigation_id,
                    alert_type=AlertType.HIGH_RISK_INTERACTION,
                    severity=AlertSeverity.CRITICAL,
                    title=f"Flagged Illicit Wallet Link: {match.label.entity_name}",
                    message=(
                        f"Transaction linked to illicit flagged entity '{match.label.entity_name}' "
                        f"({match.label.entity_category.value}) at hop {hop_number}."
                    ),
                    target_address=tx.to_address,
                    tx_hash=tx.tx_hash,
                    hop_number=hop_number,
                    metadata={"entity_name": match.label.entity_name},
                )
                if alert:
                    generated.append(alert)

        # 4. Standard New Transaction Alert
        if config.alert_on_new_tx:
            alert = self.generate_alert(
                investigation_id=investigation_id,
                alert_type=AlertType.NEW_TRANSACTION,
                severity=AlertSeverity.INFO,
                title="New On-Chain Activity Detected",
                message=f"New transfer of {tx.amount} {tx.asset_symbol} detected from {tx.from_address} to {tx.to_address}.",
                target_address=tx.to_address,
                tx_hash=tx.tx_hash,
                hop_number=hop_number,
                metadata={"amount": tx.amount, "asset": tx.asset_symbol},
            )
            if alert:
                generated.append(alert)

        return generated

    def get_alerts_by_investigation(self, investigation_id: str) -> List[Alert]:
        return self._alerts_by_case.get(investigation_id, [])

    def mark_alert_status(self, alert_id: str, new_status: AlertStatus) -> bool:
        for alerts in self._alerts_by_case.values():
            for a in alerts:
                if a.id == alert_id:
                    a.status = new_status
                    return True
        return False

    def clear(self) -> None:
        """Reset internal stores (primarily for testing)."""
        self._alerts_by_case.clear()
        self._seen_event_keys.clear()


global_alert_engine = AlertEngine()
