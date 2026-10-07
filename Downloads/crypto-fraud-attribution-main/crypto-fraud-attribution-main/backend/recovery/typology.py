"""Recovery Path Engine (Fraud Typology Classification).

Section 8.12 / Feature 17 / TC-17:
Classifies crypto fraud into standardized typologies:
- Investment scam / task-based fraud
- Sextortion
- Ransomware
- Phishing / account takeover
- Other

Classifies using complaint metadata combined with on-chain signatures (inbound distribution,
consolidation, fragmentation, mixer exposure, and transit speed).
Pre-packages the matching evidence checklist, recommended VASP request type, and responsible party.
Supports investigator override.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.path import TracePath


class TypologyProfile(BaseModel):
    typology_id: str
    title: str
    description: str
    confidence: float
    on_chain_signature: str
    evidence_checklist: List[str]
    recommended_request_type: str
    responsible_party: str
    override_applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


TYPOLOGY_CATALOG: Dict[str, Dict[str, Any]] = {
    "investment_scam": {
        "title": "Investment Scam / Task-Based Fraud",
        "description": "Multi-victim fund funneling into collection clusters followed by rapid consolidation sweeps.",
        "on_chain_signature": "Many inbound transfers into collection wallet, followed by batch consolidation to VASP.",
        "evidence_checklist": [
            "Victim deposit transaction receipt and bank-to-crypto on-ramp records",
            "Clustered collection addresses and deposit aggregator node records",
            "Consolidation hop transaction hashes leading to receiving exchange",
            "Attributed exchange/VASP deposit address identifier",
        ],
        "recommended_request_type": "Emergency Preservation Notice & VASP Freeze Request",
        "responsible_party": "I4C Cyber Cell / Investigating Officer",
    },
    "sextortion": {
        "title": "Sextortion / Coercive Extortion",
        "description": "Direct, one-off extortion payments to dedicated burner address followed by fast single-path exit.",
        "on_chain_signature": "Small-to-medium single inbound transfer to a solitary wallet with rapid onward relay.",
        "evidence_checklist": [
            "Extortion communication transcript and target wallet demand notice",
            "Single victim payment transaction hash and block timestamp",
            "Relay hop ledger tracing funds to final identifiable cashout point",
            "Last observed destination endpoint and exchange user ID disclosure request",
        ],
        "recommended_request_type": "Expedited VASP KYC Disclosure & Log Preservation",
        "responsible_party": "District Cyber Police Station",
    },
    "ransomware": {
        "title": "Ransomware & Cyber Extortion",
        "description": "High-value extortion payment split via complex fragmentation and directed toward mixers or sanction lists.",
        "on_chain_signature": "Large single payment, aggressive amount fragmentation, and interaction with privacy protocols or mixers.",
        "evidence_checklist": [
            "Incident response ledger and threat actor ransom note",
            "Proof of ransom payment transaction hash",
            "Branching fragmentation ledger and mixer ingress addresses",
            "OFAC / Sanction list match citations for receiving clusters",
        ],
        "recommended_request_type": "Inter-Agency Cyber Alert & High-Priority VASP Asset Block",
        "responsible_party": "Central Cyber Crime Agency / State Special Cell",
    },
    "phishing": {
        "title": "Phishing / Wallet Drainer / Account Takeover",
        "description": "Unauthorized drain of victim wallet through malicious approvals, signatures, or credential theft.",
        "on_chain_signature": "Sudden anomalous outflow of total balance from victim address to drainer contract or address.",
        "evidence_checklist": [
            "Victim original wallet address and proof of non-custodial custody",
            "Malicious transaction signature / drainer contract call hash",
            "Intermediate mule addresses used for immediate layering",
            "Destination VASP deposit identification for cashout intercept",
        ],
        "recommended_request_type": "Urgent Outflow Reversal / Intermediary Freeze Notice",
        "responsible_party": "Investigating Officer / Cyber Cell",
    },
    "other": {
        "title": "General Cryptocurrency Fraud",
        "description": "Suspicious cryptocurrency fund movement requiring comprehensive multi-hop attribution.",
        "on_chain_signature": "General multi-hop transfer graph without dedicated category signature match.",
        "evidence_checklist": [
            "Formal FIR or NCRP cyber crime acknowledgment slip",
            "Victim on-chain transfer hash and timestamp",
            "Multi-hop fund trail ledger with confidence assessments",
        ],
        "recommended_request_type": "Standard Section 91 CrPC/BNSS Information Request",
        "responsible_party": "Investigating Officer",
    },
}


class RecoveryPathEngine:
    """Classifies cases into fraud typologies and attaches pre-packaged evidence bundles."""

    def classify_case(
        self,
        complaint_category: Optional[str] = None,
        reported_amount: Optional[float] = None,
        paths: Optional[List[TracePath]] = None,
        matched_endpoints: Optional[List[EndpointMatchResult]] = None,
        investigator_override: Optional[str] = None,
    ) -> TypologyProfile:
        # 1. Manual Investigator Override
        if investigator_override and investigator_override.lower() in TYPOLOGY_CATALOG:
            key = investigator_override.lower()
            data = TYPOLOGY_CATALOG[key]
            return TypologyProfile(
                typology_id=key,
                title=data["title"],
                description=data["description"],
                confidence=1.0,
                on_chain_signature=data["on_chain_signature"],
                evidence_checklist=data["evidence_checklist"],
                recommended_request_type=data["recommended_request_type"],
                responsible_party=data["responsible_party"],
                override_applied=True,
            )

        # 2. Check Complaint Category String
        cat_lower = (complaint_category or "").strip().lower()
        if any(w in cat_lower for w in ["investment", "task", "job", "part-time", "trading scam", "ponzi"]):
            return self._build_profile("investment_scam", confidence=0.92)
        if any(w in cat_lower for w in ["sextortion", "blackmail", "nude", "coercion", "threat", "extortion", "leak", "photo"]):
            return self._build_profile("sextortion", confidence=0.95)
        if any(w in cat_lower for w in ["ransomware", "ransom", "decrypt", "lockbit", "encrypt"]):
            return self._build_profile("ransomware", confidence=0.95)
        if any(w in cat_lower for w in ["phish", "drain", "unauthorized", "stolen", "hack", "takeover", "compromised"]):
            return self._build_profile("phishing", confidence=0.90)

        # 3. Analyze On-Chain Flow Signatures
        paths = paths or []
        endpoints = matched_endpoints or []

        has_mixer = any(
            e.is_matched and e.label and e.label.entity_category == EntityCategory.MIXER
            for e in endpoints
        )
        total_hops = max((p.hop_count for p in paths), default=1)
        path_count = len(paths)

        # Large amount + mixer or high fragmentation -> ransomware
        amt = reported_amount or 0.0
        if amt >= 5.0 and has_mixer:
            return self._build_profile("ransomware", confidence=0.85)

        # Multiple paths converging or consolidating -> investment scam
        if path_count >= 3:
            return self._build_profile("investment_scam", confidence=0.80)

        # Small amount (< 1.5 ETH) with direct hop to exchange or quick exit -> sextortion
        if 0.0 < amt <= 1.5 and total_hops <= 2 and not has_mixer:
            return self._build_profile("sextortion", confidence=0.75)

        # Sudden multi-hop layering -> phishing
        if total_hops >= 3:
            return self._build_profile("phishing", confidence=0.70)

        return self._build_profile("other", confidence=0.60)

    def _build_profile(self, key: str, confidence: float) -> TypologyProfile:
        data = TYPOLOGY_CATALOG.get(key, TYPOLOGY_CATALOG["other"])
        return TypologyProfile(
            typology_id=key,
            title=data["title"],
            description=data["description"],
            confidence=round(confidence, 2),
            on_chain_signature=data["on_chain_signature"],
            evidence_checklist=data["evidence_checklist"],
            recommended_request_type=data["recommended_request_type"],
            responsible_party=data["responsible_party"],
            override_applied=False,
        )


global_typology_engine = RecoveryPathEngine()
