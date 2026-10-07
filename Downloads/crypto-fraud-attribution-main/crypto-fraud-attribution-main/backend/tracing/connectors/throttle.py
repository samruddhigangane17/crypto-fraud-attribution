"""Call-level throttle usable around any connector (shared by the API route and scripts)."""

import threading
import time
from typing import List, Optional

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.base import BaseConnector


class ThrottledConnector(BaseConnector):
    """Wraps a connector and spaces get_transactions calls at least `delay` seconds apart.

    EtherscanConnector already paces individual HTTP requests process-wide; this wrapper adds
    spacing between whole address lookups, which keeps bursts small on free API tiers.
    """

    def __init__(self, inner: BaseConnector, delay: float = 0.3):
        self.inner = inner
        self.delay = max(0.0, delay)
        self.calls = 0
        self._lock = threading.Lock()
        self._last_call = 0.0

    def get_transactions(
        self,
        address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        include_token_transfers: bool = False,
    ) -> List[NormalizedTransaction]:
        with self._lock:
            self.calls += 1
            wait = self.delay - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
        return self.inner.get_transactions(
            address, start_block, end_block, include_token_transfers=include_token_transfers
        )
