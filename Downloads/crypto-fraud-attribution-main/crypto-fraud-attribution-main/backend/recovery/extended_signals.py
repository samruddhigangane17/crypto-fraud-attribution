"""Extended Laundering Signals Detector.

Section 8.14 / Feature 19:
Adds forensic checks for:
1. Amount fragmentation: A larger amount split into several smaller transfers shortly after receipt.
2. Dormant-to-active shift: A wallet with little/no history suddenly receiving and forwarding high-volume flows.
3. Layering depth: Funds passing through many intermediaries within a short time.
4. Path convergence: Apparently separate paths merging on a common destination.

Each signal is accompanied by measured empirical evidence and incorporates the ContextFilter
to prevent false alerts on legitimate high-volume exchange hot wallets and routers.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.recovery.context_filter import ContextFilter, global_context_filter
from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction


@dataclass
class LaunderingSignal:
    signal_type: str  # "amount_fragmentation", "dormant_to_active_shift", "layering_depth", "path_convergence"
    target_address: str
    description: str
    severity: str  # "LOW", "MEDIUM", "HIGH"
    score_contribution: float
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "target_address": self.target_address,
            "description": self.description,
            "severity": self.severity,
            "score_contribution": self.score_contribution,
            "evidence": self.evidence,
        }


class ExtendedLaunderingDetector:
    """Analyzes trace graph flows for sophisticated money-laundering topologies."""

    def __init__(self, context_filter: Optional[ContextFilter] = None):
        self.context_filter = context_filter or global_context_filter

    def detect_signals(
        self,
        paths: List[TracePath],
        chain: str = "ethereum",
    ) -> List[LaunderingSignal]:
        """Runs all extended signal evaluations across traced paths."""
        signals: List[LaunderingSignal] = []

        # Index transactions by address
        incoming: Dict[str, List[NormalizedTransaction]] = defaultdict(list)
        outgoing: Dict[str, List[NormalizedTransaction]] = defaultdict(list)
        seen_txs: Set[str] = set()

        for path in paths:
            for tx in path.transactions:
                if tx.tx_hash in seen_txs:
                    continue
                seen_txs.add(tx.tx_hash)
                src = tx.from_address.lower()
                dst = tx.to_address.lower()
                incoming[dst].append(tx)
                outgoing[src].append(tx)

        all_addresses = set(incoming.keys()).union(set(outgoing.keys()))

        # 1. Amount Fragmentation
        for addr in all_addresses:
            # Check context filter: suppress legitimate exchange hot wallets/routers
            if self.context_filter.is_suppressed(addr, chain=chain):
                continue

            in_txs = incoming.get(addr, [])
            out_txs = outgoing.get(addr, [])

            if not in_txs or len(out_txs) < 2:
                continue

            for in_tx in in_txs:
                total_in = in_tx.amount
                if total_in <= Decimal("0"):
                    continue

                # Look for subsequent outflows within 4 hours (14400s)
                related_outs = [
                    o for o in out_txs
                    if o.timestamp >= in_tx.timestamp
                    and (o.timestamp - in_tx.timestamp).total_seconds() <= 14400
                ]

                if len(related_outs) >= 2:
                    out_amounts = [float(o.amount) for o in related_outs]
                    sum_out = sum(out_amounts)
                    ratio = sum_out / float(total_in) if float(total_in) > 0 else 0

                    # Classic fragmentation: outgoing split into smaller fractions
                    if 0.5 <= ratio <= 1.5:
                        time_window_sec = (max(o.timestamp for o in related_outs) - in_tx.timestamp).total_seconds()
                        signals.append(
                            LaunderingSignal(
                                signal_type="amount_fragmentation",
                                target_address=addr,
                                description=(
                                    f"Wallet received {total_in} and fragmented it into {len(related_outs)} "
                                    f"smaller transfers within {int(time_window_sec)}s."
                                ),
                                severity="HIGH" if len(related_outs) >= 3 else "MEDIUM",
                                score_contribution=15.0 if len(related_outs) >= 3 else 10.0,
                                evidence={
                                    "inflow_amount": float(total_in),
                                    "inflow_tx": in_tx.tx_hash,
                                    "outflow_count": len(related_outs),
                                    "outflow_amounts": out_amounts,
                                    "time_window_seconds": round(time_window_sec, 1),
                                    "percentage_forwarded": round(ratio * 100, 1),
                                },
                            )
                        )
                        break

        # 2. Dormant-to-Active Shift
        for addr in all_addresses:
            if self.context_filter.is_suppressed(addr, chain=chain):
                continue

            in_txs = incoming.get(addr, [])
            out_txs = outgoing.get(addr, [])
            total_activity = len(in_txs) + len(out_txs)

            # A wallet appearing for the first time in our trace with rapid high volume and near-zero historical spread
            if total_activity >= 2:
                all_times = sorted([tx.timestamp for tx in in_txs + out_txs])
                first_seen = all_times[0]
                last_seen = all_times[-1]
                lifespan_sec = (last_seen - first_seen).total_seconds()
                total_vol = sum((tx.amount for tx in in_txs), Decimal("0"))

                # Bursts of activity in a short lifespan (< 3 hours) with rapid forwarding
                if lifespan_sec <= 10800 and total_vol > Decimal("0.5"):
                    signals.append(
                        LaunderingSignal(
                            signal_type="dormant_to_active_shift",
                            target_address=addr,
                            description=(
                                f"Previously inactive address exhibited sudden high-volume burst of {total_vol} "
                                f"across {total_activity} transfers in {int(lifespan_sec)}s."
                            ),
                            severity="MEDIUM",
                            score_contribution=10.0,
                            evidence={
                                "first_seen": first_seen.isoformat(),
                                "last_seen": last_seen.isoformat(),
                                "burst_duration_seconds": round(lifespan_sec, 1),
                                "burst_volume": float(total_vol),
                                "transfers_in_burst": total_activity,
                            },
                        )
                    )

        # 3. Layering Depth
        for path in paths:
            if path.hop_count >= 3:
                # Calculate transit time across hops
                if path.transactions:
                    t_start = path.transactions[0].timestamp
                    t_end = path.transactions[-1].timestamp
                    duration_sec = (t_end - t_start).total_seconds()
                    # If 3+ hops happened in under 6 hours (21600 seconds), flag rapid layering
                    if duration_sec <= 21600:
                        signals.append(
                            LaunderingSignal(
                                signal_type="layering_depth",
                                target_address=path.end_address,
                                description=(
                                    f"Funds traversed {path.hop_count} hops through intermediary wallets "
                                    f"in {int(duration_sec)}s."
                                ),
                                severity="HIGH" if path.hop_count >= 4 else "MEDIUM",
                                score_contribution=15.0 if path.hop_count >= 4 else 10.0,
                                evidence={
                                    "hop_depth": path.hop_count,
                                    "transit_duration_seconds": round(duration_sec, 1),
                                    "start_address": path.start_address,
                                    "end_address": path.end_address,
                                },
                            )
                        )

        # 4. Path Convergence
        end_destinations: Dict[str, List[TracePath]] = defaultdict(list)
        for path in paths:
            end_destinations[path.end_address.lower()].append(path)

        for dest, matching_paths in end_destinations.items():
            if len(matching_paths) >= 2:
                # Check that paths had different intermediary routes
                distinct_intermediates = set()
                for p in matching_paths:
                    for tx in p.transactions[:-1]:
                        distinct_intermediates.add(tx.to_address.lower())

                if len(distinct_intermediates) >= 2 and not self.context_filter.is_suppressed(dest, chain=chain):
                    total_converged_vol = sum(
                        (p.transactions[-1].amount for p in matching_paths if p.transactions),
                        Decimal("0"),
                    )
                    signals.append(
                        LaunderingSignal(
                            signal_type="path_convergence",
                            target_address=dest,
                            description=(
                                f"{len(matching_paths)} separate transaction paths converged on common "
                                f"destination {dest} with aggregated volume {total_converged_vol}."
                            ),
                            severity="MEDIUM",
                            score_contribution=10.0,
                            evidence={
                                "converging_paths_count": len(matching_paths),
                                "destination_address": dest,
                                "aggregated_volume": float(total_converged_vol),
                                "distinct_intermediate_count": len(distinct_intermediates),
                            },
                        )
                    )

        # Deduplicate signals by (signal_type, target_address)
        unique_signals: List[LaunderingSignal] = []
        seen_keys: Set[Tuple[str, str]] = set()
        for s in signals:
            key = (s.signal_type, s.target_address)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_signals.append(s)

        return unique_signals


global_laundering_detector = ExtendedLaunderingDetector()
