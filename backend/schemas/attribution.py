"""Attribution schemas for known exchange/VASP labels and endpoint matching."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EntityCategory(str, Enum):
    EXCHANGE_VASP = "exchange_vasp"
    MIXER = "mixer"
    BRIDGE = "bridge"
    DEFI_PROTOCOL = "defi_protocol"
    SCAM_FRAUD = "scam_fraud"
    SANCTIONED = "sanctioned"
    HIGH_RISK = "high_risk"
    MERCHANT_PAYMENT = "merchant_payment"
    UNKNOWN = "unknown"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"                     # Official regulatory list, verified exchange hot wallet, attested
    UNVERIFIED_COMMUNITY = "unverified_community" # Public tags, user submissions, crowd reports
    HEURISTIC_CLUSTER = "heuristic_cluster"       # Inferred via wallet co-spending or peeling heuristics


class AddressLabel(BaseModel):
    id: str = Field(..., description="Unique UUID for this address label record")
    chain: str = Field(..., description="Target chain, e.g. ethereum, bitcoin, tron, bsc")
    address: str = Field(..., description="Crypto address (normalized lowercase for EVM)")
    entity_name: str = Field(..., description="Entity or service name, e.g. Binance, Tornado.Cash")
    entity_category: EntityCategory = Field(..., description="Classification category")
    source: str = Field(..., description="Data provenance source name, e.g. OFAC SDN, Etherscan Public, Chain Registry")
    source_url: Optional[str] = Field(None, description="URL or reference citation for the source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in label accuracy from 0.0 to 1.0")
    verified_at: Optional[str] = Field(None, description="Timestamp when label was verified")
    verification_status: VerificationStatus = Field(default=VerificationStatus.VERIFIED)
    notes: Optional[str] = Field(None, description="Investigative context or description")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AddressLabelCreate(BaseModel):
    chain: str
    address: str
    entity_name: str
    entity_category: EntityCategory
    source: str
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verification_status: VerificationStatus = Field(default=VerificationStatus.VERIFIED)
    notes: Optional[str] = None


class EndpointMatchResult(BaseModel):
    chain: str
    address: str
    is_matched: bool
    label: Optional[AddressLabel] = None
    match_type: str = Field(..., description="EXACT, HEURISTIC, or UNKNOWN")
    hop_distance: Optional[int] = Field(None, description="Hop distance from reported source address")
    associated_tx_hash: Optional[str] = Field(None, description="Tx hash leading to this endpoint")
    investigative_note: str = Field(
        default="A labeled exchange endpoint does not prove who owns the receiving wallet or who controlled the funds. "
                "A transaction path is observed evidence; claims about identity, intent, or the continuity of particular "
                "funds may require additional evidence."
    )
