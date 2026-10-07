"""Freeze-Point Finder & Stablecoin Issuer Registry (Advisory & Statutory).

USP 1: Freeze-Point Finder (Exchange + Stablecoin-Issuer Freeze)
Identifies immediately freezable endpoints across two major enforcement vectors:
1. Centralized Exchange (VASP) Deposit Wallets -> Account Freeze / Custody Lock
2. Stablecoin Issuer Blacklist Mechanisms -> On-Chain Smart Contract Blacklist
   - Tether (USDT): addBlackList(address) [0x0ecb93c0] / isBlackListed [0xe47d6060]
     Freezable by: Tether (T3 Financial Crime Unit)
   - Circle (USDC): blacklist(address) [0xf9f92be4] / isBlacklisted [0xfe575a87]
     Freezable by: Circle Consortium
3. Unhosted wallets containing native assets (ETH, BTC, TRX, MATIC) or DAI -> Freezable by: none
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


# Known Smart Contract ABI Function Selectors
SELECTOR_ADD_BLACKLIST_TETHER = "0x0ecb93c0"  # addBlackList(address)
SELECTOR_IS_BLACKLISTED_TETHER = "0xe47d6060"  # isBlackListed(address)
SELECTOR_REMOVE_BLACKLIST_TETHER = "0xe4997dc5"  # removeBlackList(address)

SELECTOR_BLACKLIST_CIRCLE = "0xf9f92be4"  # blacklist(address)
SELECTOR_IS_BLACKLISTED_CIRCLE = "0xfe575a87"  # isBlacklisted(address)
SELECTOR_UNBLACKLIST_CIRCLE = "0x848a60a7"  # unBlacklist(address)

KNOWN_FREEZE_SELECTORS = {
    SELECTOR_ADD_BLACKLIST_TETHER: {
        "function": "addBlackList(address)",
        "issuer": "Tether",
        "description": "Tether USDT Smart Contract on-chain account freeze",
    },
    SELECTOR_IS_BLACKLISTED_TETHER: {
        "function": "isBlackListed(address)",
        "issuer": "Tether",
        "description": "Tether USDT Blacklist status query",
    },
    SELECTOR_BLACKLIST_CIRCLE: {
        "function": "blacklist(address)",
        "issuer": "Circle",
        "description": "Circle USDC Smart Contract on-chain account freeze",
    },
    SELECTOR_IS_BLACKLISTED_CIRCLE: {
        "function": "isBlacklisted(address)",
        "issuer": "Circle",
        "description": "Circle USDC Blacklist status query",
    },
}

# Multi-chain registry of major stablecoin contracts
STABLECOIN_REGISTRY: Dict[str, Dict[str, Dict[str, str]]] = {
    "USDT": {
        "ethereum": {
            "contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "issuer": "Tether (T3 Financial Crime Unit)",
            "selector": SELECTOR_ADD_BLACKLIST_TETHER,
            "standard": "ERC-20",
        },
        "tron": {
            "contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            "issuer": "Tether (T3 Financial Crime Unit)",
            "selector": SELECTOR_ADD_BLACKLIST_TETHER,
            "standard": "TRC-20",
        },
        "polygon": {
            "contract": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "issuer": "Tether (T3 Financial Crime Unit)",
            "selector": SELECTOR_ADD_BLACKLIST_TETHER,
            "standard": "ERC-20",
        },
        "bsc": {
            "contract": "0x55d398326f99059fF775485246999027B3197955",
            "issuer": "Tether (T3 Financial Crime Unit)",
            "selector": SELECTOR_ADD_BLACKLIST_TETHER,
            "standard": "BEP-20",
        },
        "arbitrum": {
            "contract": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
            "issuer": "Tether (T3 Financial Crime Unit)",
            "selector": SELECTOR_ADD_BLACKLIST_TETHER,
            "standard": "ERC-20",
        },
    },
    "USDC": {
        "ethereum": {
            "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "issuer": "Circle Consortium",
            "selector": SELECTOR_BLACKLIST_CIRCLE,
            "standard": "ERC-20",
        },
        "polygon": {
            "contract": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
            "issuer": "Circle Consortium",
            "selector": SELECTOR_BLACKLIST_CIRCLE,
            "standard": "ERC-20",
        },
        "arbitrum": {
            "contract": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            "issuer": "Circle Consortium",
            "selector": SELECTOR_BLACKLIST_CIRCLE,
            "standard": "ERC-20",
        },
        "bsc": {
            "contract": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "issuer": "Circle Consortium",
            "selector": SELECTOR_BLACKLIST_CIRCLE,
            "standard": "BEP-20",
        },
        "tron": {
            "contract": "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8",
            "issuer": "Circle Consortium",
            "selector": SELECTOR_BLACKLIST_CIRCLE,
            "standard": "TRC-20",
        },
    },
}

# Directory of Law Enforcement Response Portals & Compliance Contacts
VASP_CONTACT_PORTALS: Dict[str, str] = {
    "binance": "compliance-cr@binance.com | LE Portal: https://www.binance.com/en/support/law-enforcement",
    "coindcx": "compliance@coindcx.com | lawenforcement@coindcx.com",
    "wazirx": "nodalofficer@wazirx.com | compliance@wazirx.com",
    "kucoin": "compliance@kucoin.com | https://www.kucoin.com/law-enforcement",
    "bybit": "compliance@bybit.com | lawenforcement@bybit.com",
    "okx": "compliance@okx.com | https://www.okx.com/law-enforcement",
    "coinbase": "lawenforcement@coinbase.com | Portal: https://www.coinbase.com/legal/law-enforcement",
    "kraken": "compliance@kraken.com | https://www.kraken.com/legal/law-enforcement",
    "bitfinex": "compliance@bitfinex.com",
    "htx": "compliance@htx.com",
}

ISSUER_CONTACT_PORTALS: Dict[str, str] = {
    "Tether": "t3fcu@tether.to | Law Enforcement Portal: https://tether.to/en/compliance/",
    "Circle": "legal@circle.com | Law Enforcement Portal: https://www.circle.com/en/legal/law-enforcement-request",
    "none": "N/A - Decentralized / Unhosted Native Asset",
}

# Native unfreezable or decentralized tokens
UNFREEZABLE_ASSETS = {"ETH", "BTC", "TRX", "MATIC", "POL", "BNB", "SOL", "AVAX", "DAI", "MKR", "UNI"}

REGISTRY_VERSION = "2026.1-USP1-VASP-STABLECOIN-v1.4"


@dataclass
class FreezePointIntelligence:
    freezable_by: str  # "Exchange" | "Tether" | "Circle" | "Exchange + Tether" | "Exchange + Circle" | "none"
    freeze_mechanism: str  # "VASP Account Freeze" | "Smart Contract Blacklist (addBlackList)" | "None (Unhosted Native Asset)"
    issuer_contact_portal: str
    actionability_tier: str  # "Act Now" | "Act Soon" | "Monitor"
    why_this_tier: str
    confidence_gate_passed: bool
    token_contract: Optional[str] = None
    blacklist_selector: Optional[str] = None
    chain: Optional[str] = None
    target_entity: Optional[str] = None
    registry_version: str = REGISTRY_VERSION


class FreezePointFinder:
    """Detects immediately freezable digital assets and maps enforcement channels."""

    CONFIDENCE_THRESHOLD = 0.75  # 75% minimum confidence gate

    def __init__(self):
        self.stablecoins = STABLECOIN_REGISTRY
        self.vasp_portals = VASP_CONTACT_PORTALS
        self.issuer_portals = ISSUER_CONTACT_PORTALS

    def match_contract_by_address(self, contract_address: str) -> Optional[Tuple[str, str, Dict[str, str]]]:
        """Matches a token contract address against the stablecoin registry.
        
        Returns: (symbol, chain, entry_dict) or None
        """
        if not contract_address:
            return None
        addr_clean = contract_address.strip().lower()
        for symbol, chain_dict in self.stablecoins.items():
            for chain, info in chain_dict.items():
                if info.get("contract", "").strip().lower() == addr_clean:
                    return symbol, chain, info
        return None

    def match_selector(self, selector: str) -> Optional[Dict[str, str]]:
        """Matches a 4-byte smart contract selector."""
        if not selector:
            return None
        sel_clean = selector.strip().lower()
        return KNOWN_FREEZE_SELECTORS.get(sel_clean)

    def lookup_vasp_portal(self, entity_name: str) -> str:
        """Finds official LE portal or email for a named VASP."""
        if not entity_name:
            return "compliance-requests@vasp-network.int"
        name_lower = entity_name.lower()
        for k, portal in self.vasp_portals.items():
            if k in name_lower:
                return portal
        return f"compliance-desk@{name_lower.replace(' ', '')}.com | Designated LEA Officer Portal"

    def evaluate_endpoint(
        self,
        address: str,
        asset: str = "ETH",
        chain: str = "ethereum",
        entity_category: str = "NON_CUSTODIAL_WALLET",
        entity_name: str = "Unattributed Wallet",
        confidence: float = 0.20,
        hours_elapsed: float = 0.0,
        has_onward_transfer: bool = False,
        contract_address: Optional[str] = None,
        calldata_selector: Optional[str] = None,
    ) -> FreezePointIntelligence:
        """Evaluates an endpoint/destination for freezability, mechanism, and actionability."""
        asset_upper = (asset or "ETH").strip().upper()
        chain_lower = (chain or "ethereum").strip().lower()

        # Check if contract address directly matches a stablecoin
        matched_contract_info = None
        if contract_address:
            match_res = self.match_contract_by_address(contract_address)
            if match_res:
                asset_upper = match_res[0]
                chain_lower = match_res[1]
                matched_contract_info = match_res[2]

        is_vasp = False
        cat_str = str(entity_category).lower()
        if "exchange" in cat_str or "vasp" in cat_str or "exchange_vasp" in cat_str:
            is_vasp = True

        # Check stablecoin details
        is_usdt = asset_upper in ("USDT", "TETHER")
        is_usdc = asset_upper in ("USDC", "CIRCLE")

        # Resolve contract address if not explicitly passed
        token_contract = None
        blacklist_selector = None
        if is_usdt:
            chain_entry = self.stablecoins["USDT"].get(chain_lower) or self.stablecoins["USDT"]["ethereum"]
            token_contract = chain_entry["contract"]
            blacklist_selector = chain_entry["selector"]
        elif is_usdc:
            chain_entry = self.stablecoins["USDC"].get(chain_lower) or self.stablecoins["USDC"]["ethereum"]
            token_contract = chain_entry["contract"]
            blacklist_selector = chain_entry["selector"]

        # Check calldata selector if supplied
        if calldata_selector:
            matched_sel = self.match_selector(calldata_selector)
            if matched_sel:
                blacklist_selector = calldata_selector
                if matched_sel["issuer"] == "Tether":
                    is_usdt = True
                elif matched_sel["issuer"] == "Circle":
                    is_usdc = True

        # Determine freezable_by and freeze_mechanism
        if is_vasp and is_usdt:
            freezable_by = "Exchange + Tether"
            freeze_mechanism = "VASP Account Freeze + Smart Contract Blacklist (addBlackList)"
            vasp_portal = self.lookup_vasp_portal(entity_name)
            issuer_contact_portal = f"VASP: {vasp_portal} | Tether: {self.issuer_portals['Tether']}"
            target_entity = f"{entity_name} + Tether (T3 FCU)"
        elif is_vasp and is_usdc:
            freezable_by = "Exchange + Circle"
            freeze_mechanism = "VASP Account Freeze + Smart Contract Blacklist (blacklist)"
            vasp_portal = self.lookup_vasp_portal(entity_name)
            issuer_contact_portal = f"VASP: {vasp_portal} | Circle: {self.issuer_portals['Circle']}"
            target_entity = f"{entity_name} + Circle Consortium"
        elif is_vasp:
            freezable_by = "Exchange"
            freeze_mechanism = "VASP Account Freeze"
            issuer_contact_portal = self.lookup_vasp_portal(entity_name)
            target_entity = entity_name
        elif is_usdt:
            freezable_by = "Tether"
            freeze_mechanism = "Smart Contract Blacklist (addBlackList)"
            issuer_contact_portal = self.issuer_portals["Tether"]
            target_entity = "Tether (T3 Financial Crime Unit)"
        elif is_usdc:
            freezable_by = "Circle"
            freeze_mechanism = "Smart Contract Blacklist (blacklist)"
            issuer_contact_portal = self.issuer_portals["Circle"]
            target_entity = "Circle Consortium"
        else:
            freezable_by = "none"
            freeze_mechanism = "None (Unhosted Native Asset)"
            issuer_contact_portal = self.issuer_portals["none"]
            target_entity = "Unhosted Autonomous Wallet"

        # Confidence Gate Check: >= 75% confidence AND must be freezable
        confidence_gate_passed = (confidence >= self.CONFIDENCE_THRESHOLD) and (freezable_by != "none")

        # Determine actionability_tier and why_this_tier
        if freezable_by != "none" and not has_onward_transfer and hours_elapsed <= 72.0:
            if confidence >= self.CONFIDENCE_THRESHOLD:
                actionability_tier = "Act Now"
                if is_vasp and (is_usdt or is_usdc):
                    why_this_tier = (
                        f"Prime Recovery Target: Verified {entity_name} deposit containing freezable {asset_upper}. "
                        f"Both internal VASP account freeze and on-chain issuer blacklist available immediately."
                    )
                elif is_vasp:
                    why_this_tier = (
                        f"Critical VASP Freeze Point: Terminal deposit cluster at {entity_name} with "
                        f"{round(confidence * 100)}% attribution confidence. Emergency preservation notice can seize funds before liquidation."
                    )
                else:
                    why_this_tier = (
                        f"On-Chain Freeze Point: Suspect address holds unspent {asset_upper} on {chain_lower.title()}. "
                        f"{target_entity} can invoke {freeze_mechanism} to halt transfers."
                    )
            else:
                actionability_tier = "Act Soon"
                why_this_tier = (
                    f"Attribution confidence ({round(confidence * 100)}%) is below the statutory 75% threshold. "
                    f"Perform secondary cluster verification before serving formal legal notice."
                )
        elif freezable_by != "none" and not has_onward_transfer:
            actionability_tier = "Act Soon"
            why_this_tier = (
                f"Funds arrived ~{round(hours_elapsed, 1)}h ago without observed onward movement. "
                f"Lapse in time increases sweep probability; issue urgent compliance hold."
            )
        elif freezable_by != "none" and has_onward_transfer:
            actionability_tier = "Monitor"
            why_this_tier = (
                f"Onward movement observed from this address. Target has already routed funds downstream; "
                f"focus tracing on terminal peel hops."
            )
        else:
            actionability_tier = "Monitor"
            why_this_tier = (
                f"Asset is decentralized/native ({asset_upper}) in an unhosted wallet. "
                f"No central issuer or custodian exists to execute a smart contract freeze; monitor for VASP off-ramp."
            )

        return FreezePointIntelligence(
            freezable_by=freezable_by,
            freeze_mechanism=freeze_mechanism,
            issuer_contact_portal=issuer_contact_portal,
            actionability_tier=actionability_tier,
            why_this_tier=why_this_tier,
            confidence_gate_passed=confidence_gate_passed,
            token_contract=token_contract,
            blacklist_selector=blacklist_selector,
            chain=chain_lower,
            target_entity=target_entity,
            registry_version=REGISTRY_VERSION,
        )

    def generate_trace_snapshot_sha256(self, case_id: str, payload_data: Dict[str, Any]) -> str:
        """Computes a verifiable SHA-256 fingerprint over the trace snapshot and registry version."""
        canonical_str = json.dumps(
            {
                "case_id": case_id,
                "registry_version": REGISTRY_VERSION,
                "payload": payload_data,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


global_freeze_point_finder = FreezePointFinder()
