"""Continuous monitoring service for active cases.

Maintains monitoring configurations, polls/receives new transactions, runs
endpoint matching, and dispatches deduplicated alerts.
"""

from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from backend.attribution.matcher import EndpointMatcher, global_registry
from backend.monitoring.alerts import AlertEngine, global_alert_engine
from backend.schemas.monitoring import Alert, MonitoringConfig
from backend.schemas.transaction import NormalizedTransaction


class MonitoringService:
    """Orchestrates scheduled checks for active investigations."""

    def __init__(
        self,
        alert_engine: Optional[AlertEngine] = None,
        endpoint_matcher: Optional[EndpointMatcher] = None,
    ):
        self.alert_engine = alert_engine or global_alert_engine
        self.matcher = endpoint_matcher or EndpointMatcher(global_registry)
        self._configs: Dict[str, MonitoringConfig] = {}

    def register_case(self, config: MonitoringConfig) -> MonitoringConfig:
        """Enables or updates monitoring for an investigation."""
        if not config.started_at:
            config.started_at = datetime.now(timezone.utc).isoformat()
        self._configs[config.investigation_id] = config
        return config

    def unregister_case(self, investigation_id: str) -> bool:
        """Disables monitoring for an investigation."""
        if investigation_id in self._configs:
            self._configs[investigation_id].is_active = False
            return True
        return False

    def get_config(self, investigation_id: str) -> Optional[MonitoringConfig]:
        return self._configs.get(investigation_id)

    def list_active_configs(self) -> List[MonitoringConfig]:
        return [c for c in self._configs.values() if c.is_active]

    def check_investigation(
        self,
        investigation_id: str,
        incoming_transactions: List[NormalizedTransaction],
        hop_lookup: Optional[Dict[str, int]] = None,
    ) -> List[Alert]:
        """Runs a monitoring check cycle against new transactions for an investigation.

        Automatically matches destinations against the address registry and
        passes events through the deduplication engine.
        """
        config = self._configs.get(investigation_id)
        if not config or not config.is_active:
            return []

        hop_map = hop_lookup or {}
        new_alerts: List[Alert] = []

        for tx in incoming_transactions:
            # Only monitor transactions relevant to our watched addresses
            normalized_from = tx.from_address.lower()
            normalized_to = tx.to_address.lower()
            watched_set = {a.lower() for a in config.watched_addresses}

            if normalized_from in watched_set or normalized_to in watched_set:
                hop_num = hop_map.get(tx.tx_hash, 1)

                # Match recipient against registry
                match_result = self.matcher.match_address(
                    chain=config.chain,
                    address=tx.to_address,
                    hop_distance=hop_num,
                    associated_tx_hash=tx.tx_hash,
                    include_unverified=True,
                )

                # Evaluate alerts (with built-in deduplication)
                alerts = self.alert_engine.evaluate_transaction_for_alerts(
                    investigation_id=investigation_id,
                    tx=tx,
                    hop_number=hop_num,
                    match=match_result,
                    config=config,
                )
                new_alerts.extend(alerts)

        # Update last checked timestamp
        config.last_checked_at = datetime.now(timezone.utc).isoformat()
        return new_alerts

    @staticmethod
    def _only_since_start(
        config: MonitoringConfig, txs: List[NormalizedTransaction]
    ) -> List[NormalizedTransaction]:
        """Drop history that predates monitoring so enabling it doesn't alert on old activity."""
        if not config.started_at:
            return txs
        try:
            started = datetime.fromisoformat(config.started_at.replace("Z", "+00:00"))
        except ValueError:
            return txs
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)

        def _aware(ts: datetime) -> datetime:
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

        return [t for t in txs if _aware(t.timestamp) >= started]

    def poll_all_active(
        self,
        transaction_provider: Callable[[str, List[str]], List[NormalizedTransaction]],
    ) -> Dict[str, List[Alert]]:
        """Simulates or runs a polling cycle across all active cases using a transaction provider callback."""
        cycle_alerts: Dict[str, List[Alert]] = {}

        for config in self.list_active_configs():
            txs = transaction_provider(config.chain, config.watched_addresses)
            txs = self._only_since_start(config, txs)
            alerts = self.check_investigation(config.investigation_id, txs)
            if alerts:
                cycle_alerts[config.investigation_id] = alerts

        return cycle_alerts


global_monitoring_service = MonitoringService()
