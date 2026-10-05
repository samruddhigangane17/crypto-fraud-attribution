"""Cross-Case Convergence Engine.

Section 8.13 / Feature 18 / TC-18:
Detects when traces from different complaints converge on the same:
- Attributed exchange deposit address or VASP endpoint ('shared_endpoint')
- Heuristic cluster ('shared_cluster')
- Intermediary laundering relay wallet ('shared_intermediary')

Groups linked cases into a suspected network view with typed links and confidence scores,
enabling law enforcement to coordinate unified freezing notices across multiple complaints.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
import uuid
from pydantic import BaseModel, Field


class ConvergenceLink(BaseModel):
    link_id: str = Field(default_factory=lambda: f"CONV-{uuid.uuid4().hex[:8].upper()}")
    case_ids: List[str]
    link_type: str  # "shared_endpoint", "shared_cluster", "shared_intermediary"
    shared_identifier: str  # Address or cluster_id
    entity_name: Optional[str] = None
    confidence: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CrossCaseConvergenceEngine:
    """Detects multi-case intersection points across complaints."""

    def __init__(self):
        # Index of cases: case_id -> metadata
        self._case_index: Dict[str, Dict[str, Any]] = {}
        # Reverse indexes for fast matching
        # address -> set of case_ids
        self._address_to_cases: Dict[str, Set[str]] = defaultdict(set)
        # cluster_id -> set of case_ids
        self._cluster_to_cases: Dict[str, Set[str]] = defaultdict(set)
        # endpoint_address -> (entity_name, set of case_ids)
        self._endpoint_to_cases: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"entity": None, "cases": set()})
        # All discovered convergence links
        self._links: List[ConvergenceLink] = []

    def index_case(
        self,
        case_id: str,
        reported_address: str,
        all_traced_addresses: List[str],
        clusters: Optional[List[Dict[str, Any]]] = None,
        endpoints: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ConvergenceLink]:
        """Indexes a completed case and discovers links with any prior cases."""
        new_links: List[ConvergenceLink] = []
        clean_case_id = str(case_id)

        # Record case profile
        self._case_index[clean_case_id] = {
            "case_id": clean_case_id,
            "reported_address": reported_address.lower(),
            "traced_addresses": {a.lower() for a in all_traced_addresses},
            "clusters": clusters or [],
            "endpoints": endpoints or [],
        }

        # 1. Check & Index Attributed Endpoints (highest confidence)
        for ep in (endpoints or []):
            ep_addr = ep.get("address", "").lower()
            if not ep_addr:
                continue
            lbl = ep.get("label") or {}
            entity_name = ep.get("entity_name") or lbl.get("entity_name")
            if not entity_name or entity_name == "UNKNOWN":
                continue

            existing = self._endpoint_to_cases[ep_addr]["cases"]
            if existing and clean_case_id not in existing:
                for prior_case in existing:
                    link = ConvergenceLink(
                        case_ids=sorted([clean_case_id, prior_case]),
                        link_type="shared_endpoint",
                        shared_identifier=ep_addr,
                        entity_name=entity_name,
                        confidence=0.95,
                        description=(
                            f"Cases {clean_case_id} and {prior_case} both funnel funds to "
                            f"destination service endpoint {entity_name} ({ep_addr[:10]}...)."
                        ),
                    )
                    self._add_unique_link(link)
                    new_links.append(link)

            self._endpoint_to_cases[ep_addr]["entity"] = entity_name
            self._endpoint_to_cases[ep_addr]["cases"].add(clean_case_id)

        # 2. Check & Index Clusters (medium-high confidence)
        for cl in (clusters or []):
            c_id = cl.get("cluster_id")
            if not c_id:
                continue
            existing = self._cluster_to_cases[c_id]
            if existing and clean_case_id not in existing:
                for prior_case in existing:
                    link = ConvergenceLink(
                        case_ids=sorted([clean_case_id, prior_case]),
                        link_type="shared_cluster",
                        shared_identifier=c_id,
                        confidence=0.85,
                        description=(
                            f"Cases {clean_case_id} and {prior_case} intersect at heuristic wallet cluster {c_id}."
                        ),
                    )
                    self._add_unique_link(link)
                    new_links.append(link)
            self._cluster_to_cases[c_id].add(clean_case_id)

        # 3. Check & Index Intermediary Wallets (medium confidence)
        for addr in all_traced_addresses:
            a_lower = addr.lower()
            # Skip if it is already an attributed endpoint (handled above)
            if a_lower in self._endpoint_to_cases:
                continue

            existing = self._address_to_cases[a_lower]
            if existing and clean_case_id not in existing:
                for prior_case in existing:
                    link = ConvergenceLink(
                        case_ids=sorted([clean_case_id, prior_case]),
                        link_type="shared_intermediary",
                        shared_identifier=a_lower,
                        confidence=0.75,
                        description=(
                            f"Cases {clean_case_id} and {prior_case} routed through common intermediary {a_lower[:10]}..."
                        ),
                    )
                    self._add_unique_link(link)
                    new_links.append(link)

            self._address_to_cases[a_lower].add(clean_case_id)

        return new_links

    def _add_unique_link(self, link: ConvergenceLink) -> None:
        """Avoid duplicate links between identical case pairs and identifiers."""
        for existing in self._links:
            if (
                existing.case_ids == link.case_ids
                and existing.link_type == link.link_type
                and existing.shared_identifier == link.shared_identifier
            ):
                return
        self._links.append(link)

    def get_links_for_case(self, case_id: str) -> List[ConvergenceLink]:
        """Returns all convergence links involving the specified case."""
        cid = str(case_id)
        return [l for l in self._links if cid in l.case_ids]

    def get_network_view(self, case_id: str) -> Dict[str, Any]:
        """Generates a coordinated network view for multi-case syndicate tracking."""
        links = self.get_links_for_case(case_id)
        linked_case_ids = set()
        shared_endpoints = []
        shared_intermediaries = []
        shared_clusters = []

        for l in links:
            for c in l.case_ids:
                if c != str(case_id):
                    linked_case_ids.add(c)
            if l.link_type == "shared_endpoint":
                shared_endpoints.append(
                    {"endpoint": l.shared_identifier, "entity": l.entity_name, "cases": l.case_ids}
                )
            elif l.link_type == "shared_cluster":
                shared_clusters.append({"cluster": l.shared_identifier, "cases": l.case_ids})
            elif l.link_type == "shared_intermediary":
                shared_intermediaries.append({"address": l.shared_identifier, "cases": l.case_ids})

        return {
            "primary_case_id": case_id,
            "converged_cases_count": len(linked_case_ids),
            "linked_case_ids": sorted(list(linked_case_ids)),
            "total_links": len(links),
            "links": [l.to_dict() for l in links],
            "shared_endpoints": shared_endpoints,
            "shared_intermediaries": shared_intermediaries,
            "shared_clusters": shared_clusters,
            "investigative_guidance": (
                "Syndicate network detected: Multiple independent complaints converge on common off-chain "
                "infrastructure. Recommend issuing consolidated freezing order referencing all linked FIRs."
                if linked_case_ids
                else "No cross-case intersection observed with historical complaint database."
            ),
        }


global_convergence_engine = CrossCaseConvergenceEngine()
