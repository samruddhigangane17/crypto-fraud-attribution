"""Complaint submission pipeline and victim-safe views."""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status

import backend.api.investigations as inv
from backend.audit.logger import global_audit_logger
from backend.tracing.graph import FlowGraphBuilder
from backend.tracing.analysis import WalletRelationshipAnalyzer
from backend.tracing.tracer import MultiHopTracer
from backend.tracing.validation import is_demo_address, resolve_chain_and_address
from backend.victim import ratelimit
from backend.victim.content import NEXT_STEPS_AFTER_SUBMIT, STAGE_LABEL, STAGES
from backend.victim.otp import dev_mode
from backend.victim.safety import USER_MESSAGE, check_text
from backend.victim.store import VictimStore, now_iso

logger = logging.getLogger("crypto_attribution.victim.service")

PRELIMINARY_MAX_HOPS = 2
FREE_TEXT_FIELDS = ("platform_detail", "story")
REQUIRED_FIELDS = ("fraud_type", "incident_time", "amount_lost", "asset", "payment_method",
                   "scammer_wallet", "platform", "story")

_TX_EVM = re.compile(r"^0x[0-9a-fA-F]{64}$")
_TX_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


# ---- CAPTCHA --------------------------------------------------------------------------------
class CaptchaVerifier:
    """Cloudflare Turnstile / hCaptcha server-side check (CAPTCHA_PROVIDER, CAPTCHA_SECRET)."""

    def verify(self, token: Optional[str], ip: str) -> bool:
        secret = os.getenv("CAPTCHA_SECRET", "").strip()
        if not secret:
            if dev_mode():
                return True  # local development only
            raise HTTPException(status_code=503, detail="Filing is temporarily unavailable.")
        if not token:
            return False
        url = ("https://hcaptcha.com/siteverify" if os.getenv("CAPTCHA_PROVIDER", "").lower() == "hcaptcha"
               else "https://challenges.cloudflare.com/turnstile/v0/siteverify")
        try:
            res = httpx.post(url, data={"secret": secret, "response": token, "remoteip": ip}, timeout=8.0)
            return bool(res.json().get("success"))
        except Exception as e:  # noqa: BLE001
            logger.error("CAPTCHA verification failed to run: %s", e)
            raise HTTPException(status_code=503, detail="Filing is temporarily unavailable.")


captcha_verifier = CaptchaVerifier()


# ---- text safety ----------------------------------------------------------------------------
def reject_unsafe_text(*values: Optional[str]) -> None:
    for v in values:
        if check_text(v):
            raise HTTPException(status_code=422, detail={"code": "SENSITIVE_DATA", "message": USER_MESSAGE})


# ---- views (whitelist: victims never see risk, clusters, attribution, notes, case ids) --------
def complaint_view(c: dict, evidence_count: int = 0) -> Dict[str, Any]:
    return {
        "complaint_id": c["id"],
        "ack_id": c.get("ack_id"),
        "status": c["status"],
        "stage": STAGE_LABEL.get(c.get("lifecycle", "draft"), "Received"),
        "fraud_type": c.get("fraud_type"),
        "incident_time": c.get("incident_time"),
        "amount_lost": c.get("amount_lost"),
        "asset": c.get("asset"),
        "payment_method": c.get("payment_method"),
        "scammer_wallet": c.get("scammer_wallet"),
        "chain": c.get("chain"),
        "tx_hash": c.get("tx_hash"),
        "platform": c.get("platform"),
        "platform_detail": c.get("platform_detail"),
        "story": c.get("story"),
        "submitted_at": c.get("submitted_at"),
        "created_at": c.get("created_at"),
        "updated_at": c.get("updated_at"),
        "evidence_count": evidence_count,
    }


def status_view(c: dict, open_requests: int) -> Dict[str, Any]:
    history_list = c.get("history") or []
    reached = {h["stage"]: h["at"] for h in history_list}
    # Ensure submitted and received are marked if complaint is submitted or has ack_id
    if c.get("status") in ("submitted", "Complaint Received", "received") or c.get("ack_id"):
        if "submitted" not in reached:
            reached["submitted"] = c.get("submitted_at") or c.get("created_at")
        if "received" not in reached:
            reached["received"] = c.get("submitted_at") or c.get("created_at")
    if "under_verification" in reached and "verified" not in reached:
        reached["verified"] = reached["under_verification"]
    if "verified" in reached and "under_verification" not in reached:
        reached["under_verification"] = reached["verified"]
    if "in_progress" in reached:
        if "verified" not in reached:
            reached["verified"] = reached["in_progress"]
        if "under_verification" not in reached:
            reached["under_verification"] = reached["in_progress"]
    if "action_taken" in reached or "closed" in reached:
        if "in_progress" not in reached:
            reached["in_progress"] = reached.get("action_taken") or reached.get("closed")
        if "verified" not in reached:
            reached["verified"] = reached["in_progress"]

    lifecycle_val = c.get("lifecycle", "received")
    current_label = STAGE_LABEL.get(lifecycle_val, "Received")
    # Clean public human label for citizen tracker
    human_stage = "Complaint Received" if lifecycle_val == "received" else (
        "Under Verification" if lifecycle_val in ("under_verification", "verified") else (
            "Investigation in Progress" if lifecycle_val == "in_progress" else (
                "Action Taken" if lifecycle_val in ("action_taken", "with_officer") else (
                    "Closed" if lifecycle_val == "closed" else current_label
                )
            )
        )
    )
    timeline = [{"key": k, "label": label, "reached": k in reached, "at": reached.get(k)} for k, label in STAGES]
    return {
        "complaint_id": c["id"],
        "ack_id": c.get("ack_id"),
        "stage": current_label,
        "current_stage": human_stage,
        "lifecycle": lifecycle_val,
        "timeline": timeline,
        "open_requests": open_requests,
        "updated_at": c.get("updated_at"),
    }


# ---- submission -----------------------------------------------------------------------------
def validate_for_submit(c: dict) -> tuple[str, str]:
    missing = [f for f in REQUIRED_FIELDS if c.get(f) in (None, "")]
    if missing:
        raise HTTPException(status_code=422, detail={"code": "MISSING_FIELDS", "fields": missing})
    try:
        chain, wallet = resolve_chain_and_address("auto", c["scammer_wallet"])
    except ValueError as err:
        raise HTTPException(status_code=422, detail={"code": "BAD_WALLET", "message": str(err)})
    if is_demo_address(wallet) and not dev_mode():
        raise HTTPException(status_code=422, detail={"code": "BAD_WALLET", "message": "Enter a real wallet address."})
    tx = (c.get("tx_hash") or "").strip()
    if tx:
        ok = bool(_TX_EVM.match(tx)) if chain in ("ethereum", "bsc") else bool(_TX_HEX.match(tx))
        if not ok:
            raise HTTPException(status_code=422, detail={"code": "BAD_TX_HASH",
                                                         "message": "That transaction hash does not look right."})
    return chain, wallet


def _find_existing_case(chain: str, wallet: str) -> Optional[Dict[str, Any]]:
    key = wallet.lower() if chain in ("ethereum", "bsc") else wallet
    for case in list(inv._INVESTIGATIONS.values()):
        addr = case.get("reported_address", "")
        if case.get("chain") == chain and (addr.lower() if chain in ("ethereum", "bsc") else addr) == key:
            return case
    return None


def _create_case(ack_id: str, chain: str, wallet: str, c: dict) -> Dict[str, Any]:
    import uuid
    case_id = str(uuid.uuid4())
    now = now_iso()
    case = {
        "id": case_id, "case_id": case_id, "complaint_ref": ack_id, "chain": chain,
        "reported_address": wallet, "amount": float(c["amount_lost"]), "asset": c.get("asset"),
        "timestamp": c.get("incident_time") or now, "status": "Reported", "created_at": now,
        "graph": None, "paths": None, "analysis": None, "data_source": None, "notice": None,
        # victim-portal markers: keep unverified victim data out of public listings
        "source": "victim_portal", "source_verified": False,
        "verification": "victim_reported_unverified", "preliminary": False, "victim_report_count": 1,
    }
    inv._INVESTIGATIONS[case_id] = case
    inv._store.persist_case(case)
    return case


def submit(store: VictimStore, c: dict, declaration: bool, captcha_token: Optional[str], ip: str) -> Dict[str, Any]:
    """Validate and submit a draft. Returns {complaint, case, needs_trace, created_case}."""
    if c["status"] == "submitted":
        return {"complaint": c, "case": None, "needs_trace": False, "created_case": False}
    if not declaration:
        raise HTTPException(status_code=422, detail={"code": "DECLARATION_REQUIRED",
                                                     "message": "Please confirm the information is true."})
    reject_unsafe_text(*(c.get(f) for f in FREE_TEXT_FIELDS))
    chain, wallet = validate_for_submit(c)

    # Same victim filing the same wallet again: return the original, create nothing new.
    existing_own = store.find_own_submitted(c["victim_id"], chain, wallet)
    if existing_own:
        return {"complaint": existing_own, "case": None, "needs_trace": False, "created_case": False}

    if not ratelimit.submit_per_victim.allow(c["victim_id"]) or not ratelimit.submit_per_ip.allow(ip):
        raise HTTPException(status_code=429, detail="Too many complaints filed. Please try again tomorrow.")
    if not captcha_verifier.verify(captcha_token, ip):
        raise HTTPException(status_code=400, detail={"code": "CAPTCHA_FAILED",
                                                     "message": "Please complete the verification and try again."})

    ack_id = store.new_ack_id()
    case = _find_existing_case(chain, wallet)
    created = case is None
    if created:
        case = _create_case(ack_id, chain, wallet, c)
    else:  # same wallet already known: link, never run a duplicate trace
        case["victim_report_count"] = int(case.get("victim_report_count", 0)) + 1

    c = store.update_complaint(c["id"], chain=chain, scammer_wallet=wallet, ack_id=ack_id, status="submitted",
                               submitted_at=now_iso(), case_id=case["id"], declaration_at=now_iso())
    store.set_lifecycle(c["id"], "submitted")
    store.set_lifecycle(c["id"], "received")
    store.link_case(c["victim_id"], case["id"], c["id"])

    global_audit_logger.log_event(
        event="victim_complaint_submitted", actor="victim", case_id=case["id"],
        parameters={"ack_id": ack_id, "chain": chain, "new_case": created},
        data_source="victim_portal",
    )
    return {"complaint": c, "case": case, "needs_trace": created, "created_case": created}


def run_preliminary_trace(case_id: str) -> None:
    """Shallow trace (2 hops). Deliberately NO risk score, alerts, recovery clock or VASP notice."""
    case = inv._INVESTIGATIONS.get(case_id)
    if not case or case.get("preliminary") or case.get("status") == "completed":
        return
    try:
        connector = inv._get_connector(case["chain"], case["reported_address"])
        labels = inv._exchange_labels(case["chain"])
        tracer = MultiHopTracer(
            connector=connector, max_hops=PRELIMINARY_MAX_HOPS, investigation_id=case_id,
            min_taint_share=0.05, target_addresses=set(labels),
        )
        paths = tracer.trace(case["reported_address"])
        case["paths"] = paths
        case["intermediate_addresses"] = sorted(tracer.intermediate_addresses)
        case["graph"] = FlowGraphBuilder.build_from_paths(
            paths, root_address=case["reported_address"], address_labels=labels).to_cytoscape()
        case["analysis"] = WalletRelationshipAnalyzer.from_paths(paths).get_summary()
        case["data_source"] = inv._data_source(connector)
        case["notice"] = None if paths else "No outgoing transfers found yet (preliminary 2-hop trace)."
        case["preliminary"] = True  # status stays "Reported" until an officer verifies
        inv._store.persist_trace(case)
    except Exception:  # noqa: BLE001 - the complaint is already safely queued for an officer
        logger.exception("Preliminary trace failed for case %s", case_id)
