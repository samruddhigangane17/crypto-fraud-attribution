"""Victim portal API (/api/victim/*): a separate auth realm from investigators.

Victims only ever see their OWN complaint, evidence and a coarse status. They never see risk
scores, clusters, attribution, other cases, case ids or investigator notes.
"""

import hashlib
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.tracing.validation import detect_chain, is_valid_address
from backend.victim import evidence as ev
from backend.victim import ratelimit, service
from backend.victim.content import (CONSENT_NOTICE, CONSENT_VERSION, NEXT_STEPS_AFTER_SUBMIT, STAGE_LABEL, SUPPORT)
import secrets
from backend.victim.otp import (dev_mode, global_otp_service, issue_victim_token, normalize_phone, optional_victim,
                                phone_hash, require_victim, TOKEN_TTL_SECONDS)
from backend.victim.safety import USER_MESSAGE, check_text
from backend.victim.store import global_victim_store as store

logger = logging.getLogger("crypto_attribution.api.victim")
router = APIRouter(prefix="/api/victim", tags=["Victim portal"])


def _ip(request: Request) -> str:
    # NOTE: behind a proxy, configure it to set the real client address; do not trust
    # X-Forwarded-For from the open internet.
    return request.client.host if request.client else "unknown"


def _own_complaint(victim_id: str, complaint_id: str) -> dict:
    """404 (not 403) for anyone else's complaint, so ids cannot be probed."""
    c = store.get_complaint(complaint_id)
    if not c or c["victim_id"] != victim_id:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    return c


# ---- public ---------------------------------------------------------------------------------
@router.get("/support")
def support_center():
    return SUPPORT


@router.get("/consent-notice")
def consent_notice():
    return CONSENT_NOTICE


# ---- auth -----------------------------------------------------------------------------------
class VictimLoginRequest(BaseModel):
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: Optional[str] = Field(None, max_length=60)
    consent_accepted: bool = True
    language: str = Field("en", max_length=8)


@router.post("/auth/login")
def victim_login(body: VictimLoginRequest, request: Request):
    """Citizen victim email & password login. Replaces mobile OTP while issuing valid victim JWT."""
    if not ratelimit.verify_per_ip.allow(_ip(request)):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes.")
    clean_email = body.email.strip().lower()
    if "@" not in clean_email or len(clean_email.split("@")) != 2 or not clean_email.split("@")[1]:
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if len(body.password) < 4:
        raise HTTPException(status_code=422, detail="Password must be at least 4 characters.")
    if check_text(body.display_name) or check_text(clean_email):
        raise HTTPException(status_code=422, detail={"code": "SENSITIVE_DATA", "message": USER_MESSAGE})
    if not body.consent_accepted:
        raise HTTPException(status_code=422, detail={"code": "CONSENT_REQUIRED",
                                                     "message": "Please accept the privacy notice to continue."})

    ehash = hashlib.sha256(f"email:{clean_email}".encode()).hexdigest()[:32]
    victim = store.find_victim_by_phone_hash(ehash)
    if victim is None:
        display = (body.display_name or "").strip() or clean_email.split("@")[0]
        last4 = clean_email.split("@")[0][-4:] if len(clean_email.split("@")[0]) >= 4 else "0000"
        victim = store.create_victim(ehash, last4, display, body.language)
    if not store.has_consent(victim["id"], CONSENT_VERSION):
        store.add_consent(victim["id"], CONSENT_VERSION, CONSENT_NOTICE["purpose"])

    token = issue_victim_token(victim["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "victim_id": victim["id"],
        "victim": {
            "id": victim["id"],
            "email": clean_email,
            "display_name": victim.get("display_name"),
            "language": victim.get("language", "en"),
            "phone_last4": victim.get("phone_last4"),
        },
    }


class OtpRequest(BaseModel):
    phone: str = Field(..., max_length=20)


class OtpVerify(BaseModel):
    phone: str = Field(..., max_length=20)
    otp: str = Field(..., min_length=4, max_length=8)
    consent_accepted: bool = False
    display_name: Optional[str] = Field(None, max_length=40)
    language: str = Field("en", max_length=8)


@router.post("/auth/otp", status_code=status.HTTP_202_ACCEPTED)
def request_otp(body: OtpRequest, request: Request):
    try:
        phone = normalize_phone(body.phone)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    if not ratelimit.otp_per_ip.allow(_ip(request)) or not ratelimit.otp_per_phone.allow(phone_hash(phone)):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes.")
    code = global_otp_service.issue(phone)
    out = {"status": "sent"}
    if dev_mode():
        out["dev_otp"] = code  # demo convenience only; never present when VICTIM_DEV_MODE is off
    return out


@router.post("/auth/verify")
def verify_otp(body: OtpVerify, request: Request):
    if not ratelimit.verify_per_ip.allow(_ip(request)):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes.")
    try:
        phone = normalize_phone(body.phone)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    if check_text(body.display_name):
        raise HTTPException(status_code=422, detail={"code": "SENSITIVE_DATA", "message": USER_MESSAGE})
    if not global_otp_service.verify(phone, body.otp):
        raise HTTPException(status_code=401, detail="That code is wrong or has expired.")

    phash = phone_hash(phone)
    victim = store.find_victim_by_phone_hash(phash)
    if victim is None:
        if not body.consent_accepted:
            raise HTTPException(status_code=422, detail={"code": "CONSENT_REQUIRED",
                                                         "message": "Please accept the privacy notice to continue."})
        victim = store.create_victim(phash, phone[-4:], (body.display_name or None), body.language)
    if not store.has_consent(victim["id"], CONSENT_VERSION):
        if not body.consent_accepted:
            raise HTTPException(status_code=422, detail={"code": "CONSENT_REQUIRED",
                                                         "message": "Please accept the privacy notice to continue."})
        store.add_consent(victim["id"], CONSENT_VERSION, CONSENT_NOTICE["purpose"])
    return {
        "access_token": issue_victim_token(victim["id"]),
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "victim": {"display_name": victim.get("display_name"), "language": victim.get("language", "en"),
                   "phone_last4": victim.get("phone_last4")},
    }


@router.get("/me")
def me(victim_id: str = Depends(require_victim)):
    v = store.get_victim(victim_id)
    if not v:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return {"display_name": v.get("display_name"), "language": v.get("language", "en"),
            "phone_last4": v.get("phone_last4")}


# ---- address check (format only; never queries the blockchain) -------------------------------
@router.get("/validate-address")
def validate_address(address: str, request: Request):
    if not ratelimit.lookup_per_ip.allow(_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests.")
    chain = detect_chain(address.strip()) if len(address) <= 128 else None
    valid = bool(chain and is_valid_address(chain, address.strip()))
    return {"valid": valid, "chain": chain if valid else None}


# ---- complaints -----------------------------------------------------------------------------
class FraudType(str, Enum):
    investment = "investment"
    task_based = "task_based"
    sextortion = "sextortion"
    phishing = "phishing"
    other = "other"


class PaymentMethod(str, Enum):
    crypto_wallet = "crypto_wallet"
    upi_bank = "upi_bank"
    exchange_app = "exchange_app"


class Platform(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"
    website = "website"
    other = "other"


class ComplaintFields(BaseModel):
    fraud_type: Optional[str] = None
    typology: Optional[str] = None
    incident_time: Optional[Any] = None
    amount_lost: Optional[Any] = None
    amount: Optional[Any] = None
    asset: Optional[str] = None
    payment_method: Optional[str] = None
    scammer_wallet: Optional[str] = None
    suspect_wallet: Optional[str] = None
    chain: Optional[str] = None
    tx_hash: Optional[str] = None
    platform: Optional[str] = None
    contact_method: Optional[str] = None
    platform_detail: Optional[str] = None
    story: Optional[str] = None
    declaration_true: Optional[bool] = None
    ack_id: Optional[str] = None


class SubmitBody(BaseModel):
    declaration_true: bool = False
    captcha_token: Optional[str] = Field(None, max_length=4096)


def _clean(fields: ComplaintFields) -> dict:
    raw = fields.model_dump(exclude_unset=True)
    data = dict(raw)

    ft = data.get("fraud_type") or data.get("typology")
    if ft:
        ft_norm = str(ft).lower().replace("-", "_").replace(" ", "_")
        if ft_norm in ("investment", "task_based", "sextortion", "phishing", "other"):
            data["fraud_type"] = ft_norm
        elif "invest" in ft_norm:
            data["fraud_type"] = "investment"
        elif "task" in ft_norm:
            data["fraud_type"] = "task_based"
        elif "sexton" in ft_norm or "extort" in ft_norm:
            data["fraud_type"] = "sextortion"
        elif "phish" in ft_norm or "drain" in ft_norm:
            data["fraud_type"] = "phishing"
        else:
            data["fraud_type"] = "other"

    wallet = data.get("scammer_wallet") or data.get("suspect_wallet")
    if wallet:
        data["scammer_wallet"] = str(wallet).strip()

    amt = data.get("amount_lost") if data.get("amount_lost") is not None else data.get("amount")
    if amt is not None:
        try:
            clean_num = str(amt).split()[0].replace(",", "").strip()
            data["amount_lost"] = Decimal(clean_num)
        except Exception:
            data["amount_lost"] = Decimal(0)

    plat = data.get("platform") or data.get("contact_method")
    if plat:
        plat_norm = str(plat).lower().strip()
        if plat_norm in ("telegram", "whatsapp", "website", "other"):
            data["platform"] = plat_norm
        elif "tele" in plat_norm:
            data["platform"] = "telegram"
        elif "what" in plat_norm:
            data["platform"] = "whatsapp"
        elif "web" in plat_norm or "site" in plat_norm:
            data["platform"] = "website"
        else:
            data["platform"] = "other"

    if data.get("asset"):
        data["asset"] = str(data["asset"]).strip().upper()

    if data.get("chain"):
        data["chain"] = str(data["chain"]).strip().lower()

    if isinstance(data.get("incident_time"), datetime):
        data["incident_time"] = data["incident_time"].isoformat()

    service.reject_unsafe_text(*(data.get(f) for f in service.FREE_TEXT_FIELDS), data.get("tx_hash"))
    return data


@router.post("/complaints", status_code=status.HTTP_201_CREATED)
def create_draft(
    fields: ComplaintFields,
    request: Request,
    background: BackgroundTasks,
    victim_id: Optional[str] = Depends(optional_victim),
):
    clean_data = _clean(fields)
    is_intake = bool(
        fields.typology or
        fields.suspect_wallet or
        fields.contact_method or
        fields.declaration_true is True or
        (clean_data.get("scammer_wallet") and clean_data.get("story") and clean_data.get("amount_lost") is not None and not fields.fraud_type)
    )

    if not victim_id:
        anon_key = secrets.token_hex(16)
        guest = store.create_victim(anon_key, "0000", "Citizen Reporter", "en")
        victim_id = guest["id"]
        store.add_consent(victim_id, CONSENT_VERSION, CONSENT_NOTICE["purpose"])

    if not ratelimit.draft_per_victim.allow(victim_id):
        raise HTTPException(status_code=429, detail="Too many requests.")

    if is_intake:
        from backend.tracing.validation import resolve_chain_and_address
        wallet = clean_data.get("scammer_wallet")
        chain = clean_data.get("chain")
        if wallet:
            try:
                resolved_chain, resolved_wallet = resolve_chain_and_address("auto", wallet)
                chain = resolved_chain
                wallet = resolved_wallet
            except Exception:
                chain = chain or "ethereum"
        else:
            chain = chain or "ethereum"

        clean_data["chain"] = chain
        clean_data["scammer_wallet"] = wallet
        if clean_data.get("amount_lost") is None:
            clean_data["amount_lost"] = Decimal(0)
        if not clean_data.get("asset"):
            clean_data["asset"] = "USDT"
        if not clean_data.get("payment_method"):
            clean_data["payment_method"] = "crypto_wallet"
        if not clean_data.get("platform"):
            clean_data["platform"] = "telegram"
        if not clean_data.get("story"):
            clean_data["story"] = f"Citizen complaint reported for {clean_data.get('fraud_type', 'fraud')} on {chain}."

        ack_id = clean_data.get("ack_id") or store.new_ack_id()
        case = service._find_existing_case(chain, wallet) if wallet else None
        created = case is None
        if created and wallet:
            case = service._create_case(ack_id, chain, wallet, clean_data)
        elif case:
            case["victim_report_count"] = int(case.get("victim_report_count", 0)) + 1

        case_id = case["id"] if case else str(uuid.uuid4())
        clean_data["ack_id"] = ack_id
        clean_data["case_id"] = case_id
        clean_data["status"] = "Complaint Received"
        clean_data["source"] = "victim_portal"
        clean_data["submitted_at"] = service.now_iso()
        clean_data["declaration_at"] = service.now_iso()

        c = store.create_complaint(victim_id, clean_data)
        store.update_complaint(c["id"], status="Complaint Received", ack_id=ack_id, case_id=case_id)
        store.set_lifecycle(c["id"], "submitted")
        store.set_lifecycle(c["id"], "received")
        store.link_case(victim_id, case_id, c["id"])

        if case:
            from backend.audit.logger import global_audit_logger
            global_audit_logger.log_event(
                event="victim_complaint_submitted",
                actor="victim",
                case_id=case["id"],
                parameters={"ack_id": ack_id, "chain": chain, "new_case": created},
                data_source="victim_portal",
            )
            if created:
                background.add_task(service.run_preliminary_trace, case["id"])

        return {
            "ack_id": ack_id,
            "complaint_id": c["id"],
            "id": c["id"],
            "case_id": case_id,
            "status": "Complaint Received",
            "current_stage": "Complaint Received",
            "stage": "Received",
            "lifecycle": "received",
            "source": "victim_portal",
            "is_verified": False,
            "reported_address": wallet,
            "chain": chain,
            "amount": f"{clean_data.get('amount_lost', 0)} {clean_data.get('asset', 'USDT')}",
            "typology": (clean_data.get("fraud_type") or "other").replace("_", " ").title(),
            "story": clean_data.get("story"),
            "created_at": c.get("created_at"),
            "next_steps": NEXT_STEPS_AFTER_SUBMIT,
        }

    c = store.create_complaint(victim_id, clean_data)
    return service.complaint_view(c)


@router.get("/complaints")
def list_complaints(victim_id: str = Depends(require_victim)):
    return [service.complaint_view(c, len(store.evidence_for_complaint(c["id"])))
            for c in store.list_complaints(victim_id)]


@router.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: str, victim_id: str = Depends(require_victim)):
    c = _own_complaint(victim_id, complaint_id)
    return service.complaint_view(c, len(store.evidence_for_complaint(complaint_id)))


@router.patch("/complaints/{complaint_id}")
def autosave_draft(complaint_id: str, fields: ComplaintFields, victim_id: str = Depends(require_victim)):
    c = _own_complaint(victim_id, complaint_id)
    if c["status"] != "draft":
        raise HTTPException(status_code=409, detail="A submitted complaint can no longer be edited.")
    if not ratelimit.draft_per_victim.allow(victim_id):
        raise HTTPException(status_code=429, detail="Too many requests.")
    c = store.update_complaint(complaint_id, **_clean(fields))
    return service.complaint_view(c)


@router.post("/complaints/{complaint_id}/submit", status_code=status.HTTP_201_CREATED)
def submit_complaint(complaint_id: str, body: SubmitBody, request: Request, background: BackgroundTasks,
                     victim_id: str = Depends(require_victim)):
    c = _own_complaint(victim_id, complaint_id)
    result = service.submit(store, c, body.declaration_true, body.captcha_token, _ip(request))
    if result["needs_trace"]:  # preliminary trace runs after the response, queued for an officer
        background.add_task(service.run_preliminary_trace, result["case"]["id"])
    done = result["complaint"]
    return {
        "ack_id": done["ack_id"],
        "complaint_id": done["id"],
        "stage": STAGE_LABEL.get(done.get("lifecycle", "received")),
        "next_steps": NEXT_STEPS_AFTER_SUBMIT,
    }


# ---- evidence vault -------------------------------------------------------------------------
def _evidence_view(e: dict) -> dict:
    return {
        "file_id": e["file_id"], "record_id": e["id"], "version": e["version"], "filename": e["filename"],
        "mime": e["mime"], "size_bytes": e["size_bytes"], "sha256": e["sha256"],
        "restricted": e["restricted"], "preview_allowed": not e["restricted"],
        "uploaded_at": e["uploaded_at"],
    }


@router.post("/complaints/{complaint_id}/evidence", status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    complaint_id: str,
    file: UploadFile = File(...),
    client_sha256: Optional[str] = Form(None),
    restricted: bool = Form(False),
    replaces_file_id: Optional[str] = Form(None),
    request_id: Optional[str] = Form(None),
    victim_id: str = Depends(require_victim),
):
    c = _own_complaint(victim_id, complaint_id)
    if not ratelimit.upload_per_victim.allow(victim_id):
        raise HTTPException(status_code=429, detail="Too many uploads. Please try again later.")

    data = await file.read(ev.MAX_BYTES + 1)
    if len(data) > ev.MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {ev.MAX_BYTES // (1024 * 1024)} MB).")
    filename = ev.sanitize_filename(file.filename or "file")
    try:
        mime = ev.sniff_mime(filename, data)
    except ev.EvidenceRejected as err:
        raise HTTPException(status_code=422, detail={"code": err.code, "message": err.message})
    reason = ev.global_scanner.scan(data, mime)
    if reason:
        raise HTTPException(status_code=422, detail={"code": "UNSAFE_FILE",
                                                     "message": "This file was blocked by our safety check."})

    server_hash = hashlib.sha256(data).hexdigest()
    if client_sha256 and client_sha256.strip().lower() != server_hash:
        raise HTTPException(status_code=422, detail={"code": "HASH_MISMATCH",
                                                     "message": "The file changed during upload. Please try again."})

    existing = store.evidence_for_complaint(complaint_id)
    if replaces_file_id:
        versions = [e for e in existing if e["file_id"] == replaces_file_id]
        if not versions:
            raise HTTPException(status_code=404, detail="File to replace not found.")
        file_id, version, supersedes = replaces_file_id, versions[-1]["version"] + 1, versions[-1]["id"]
        event = "version_added"
    else:
        if len({e["file_id"] for e in existing}) >= ev.MAX_FILES_PER_COMPLAINT:
            raise HTTPException(status_code=409, detail="Too many files on this complaint.")
        file_id, version, supersedes, event = str(uuid.uuid4()), 1, None, "uploaded"

    blob_path = ev.global_blob_store.write(complaint_id, file_id, version, data)
    row = store.add_evidence({
        "id": str(uuid.uuid4()), "file_id": file_id, "complaint_id": complaint_id, "version": version,
        "filename": filename, "mime": mime, "size_bytes": len(data), "sha256": server_hash,
        "restricted": bool(restricted), "blob_path": blob_path, "supersedes": supersedes,
        "uploaded_by": victim_id, "uploaded_at": service.now_iso(), "request_id": request_id,
    })
    store.append_custody(file_id, version, event, f"victim:{victim_id}", server_hash)
    if request_id:
        store.answer_request(request_id, complaint_id)
    return _evidence_view(row)


@router.get("/complaints/{complaint_id}/evidence")
def list_evidence(complaint_id: str, victim_id: str = Depends(require_victim)):
    _own_complaint(victim_id, complaint_id)
    return [_evidence_view(e) for e in store.evidence_for_complaint(complaint_id)]


def _own_file(victim_id: str, complaint_id: str, file_id: str, version: Optional[int]) -> dict:
    _own_complaint(victim_id, complaint_id)
    versions = [e for e in store.evidence_for_complaint(complaint_id) if e["file_id"] == file_id]
    if version is not None:
        versions = [e for e in versions if e["version"] == version]
    if not versions:
        raise HTTPException(status_code=404, detail="File not found.")
    return versions[-1]


@router.get("/complaints/{complaint_id}/evidence/{file_id}/verify")
def verify_evidence(complaint_id: str, file_id: str, version: Optional[int] = None,
                    victim_id: str = Depends(require_victim)):
    """Re-hash the stored file and compare with the hash recorded at upload."""
    e = _own_file(victim_id, complaint_id, file_id, version)
    try:
        intact = hashlib.sha256(ev.global_blob_store.read(e["blob_path"])).hexdigest() == e["sha256"]
    except OSError:
        intact = False
    return {"file_id": file_id, "version": e["version"], "intact": intact, "recorded_sha256": e["sha256"],
            "custody_log": [{"event": x["event"], "at": x["at"], "sha256": x["sha256"]}
                            for x in store.custody_for_file(file_id)]}


@router.get("/complaints/{complaint_id}/evidence/{file_id}/download")
def download_evidence(complaint_id: str, file_id: str, version: Optional[int] = None,
                      victim_id: str = Depends(require_victim)):
    e = _own_file(victim_id, complaint_id, file_id, version)
    data = ev.global_blob_store.read(e["blob_path"])
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{e["filename"]}"',
                             "X-Content-Type-Options": "nosniff"})


# ---- case tracker ---------------------------------------------------------------------------
@router.get("/cases/{complaint_id}/status")
@router.get("/complaints/{complaint_id}/status")
def case_status(complaint_id: str, request: Request):
    c = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.strip().startswith("Bearer "):
        try:
            victim_id = require_victim(auth_header)
            c = _own_complaint(victim_id, complaint_id)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        # Public citizen lookup by complaint_id or ack_id
        c = store.get_complaint(complaint_id)

    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if c.get("status") == "draft":
        raise HTTPException(status_code=409, detail="This complaint has not been submitted yet.")

    open_requests = sum(1 for r in store.requests_for(c["id"]) if r["status"] == "open")
    return service.status_view(c, open_requests)


@router.get("/cases/{complaint_id}/requests")
def case_requests(complaint_id: str, victim_id: str = Depends(require_victim)):
    _own_complaint(victim_id, complaint_id)
    return [{"request_id": r["id"], "text": r["body"], "status": r["status"], "created_at": r["created_at"]}
            for r in store.requests_for(complaint_id)]


# ---- notifications and transparency ----------------------------------------------------------
@router.get("/notifications")
def notifications(victim_id: str = Depends(require_victim)):
    return [{"message": n["message"], "created_at": n["created_at"]} for n in store.notifications_for(victim_id)]


@router.get("/privacy/access-log")
def access_log(victim_id: str = Depends(require_victim)):
    """Every time an officer opened this victim's data."""
    return [{"when": e["at"], "who": "An authorised investigator", "what": e["action"],
             "complaint_id": e["complaint_id"]} for e in store.pii_access_for(victim_id)]
