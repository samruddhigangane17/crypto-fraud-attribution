"""Background Monitoring Scheduler Worker.

Periodically triggers poll_all_active across registered active investigations
using an asynchronous loop without blocking the API.
"""

import asyncio
import logging
from typing import Callable, List, Optional

from backend.monitoring.service import MonitoringService, global_monitoring_service
from backend.schemas.transaction import NormalizedTransaction

logger = logging.getLogger("crypto_attribution.monitoring_scheduler")


class BackgroundMonitoringWorker:
    """Async background worker that periodically polls active investigations."""

    def __init__(
        self,
        service: Optional[MonitoringService] = None,
        poll_interval_seconds: int = 60,
    ):
        self.service = service or global_monitoring_service
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._transaction_provider: Callable[[str, List[str]], List[NormalizedTransaction]] = self._default_provider

    def _default_provider(self, chain: str, addresses: List[str]) -> List[NormalizedTransaction]:
        """Default provider placeholder before Member 1 live connectors are hooked in."""
        return []

    def set_transaction_provider(
        self,
        provider: Callable[[str, List[str]], List[NormalizedTransaction]],
    ) -> None:
        """Allows Member 1 to register a real blockchain transaction provider."""
        self._transaction_provider = provider

    async def _loop(self) -> None:
        logger.info(f"Background monitoring worker started. Interval: {self.poll_interval}s")
        while self._running:
            try:
                active_cases = self.service.list_active_configs()
                if active_cases:
                    logger.debug(f"Running monitoring cycle for {len(active_cases)} active case(s)...")
                    # Offload synchronous provider calls to thread pool so blockchain network calls don't block API
                    cycle_alerts = await asyncio.to_thread(self.service.poll_all_active, self._transaction_provider)
                    for case_id, alerts in cycle_alerts.items():
                        logger.info(f"Monitoring detected {len(alerts)} new alert(s) for case {case_id}")
            except Exception as e:
                logger.error(f"Error during monitoring loop cycle: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

        logger.info("Background monitoring worker stopped.")

    def start(self) -> None:
        """Starts the background monitoring loop in the active event loop."""
        if not self._running:
            self._running = True
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._loop())

    def stop(self) -> None:
        """Signals the background monitoring worker to terminate gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()


global_background_worker = BackgroundMonitoringWorker()
