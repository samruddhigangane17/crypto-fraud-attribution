"""Investigator side of the victim portal: the intake queue (/api/v1/intake*).

Everything here needs an authorised investigator. Victim-reported data stays "unverified"
until an officer verifies it; only then does full tracing, attribution and alerting start.
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

import backend.api.investigations as inv
from backend.api.auth import require_authorized_investigator
from backend.audit.logger import global_audit_logger
from backend.victim import evidence as ev
from backend.victim.content import STAGE_LABEL
from backend.victim.store import global_victim_store as store

logger = logging.getLogger("crypto_attribution.api.intake")
router = APIRouter(prefix="/api/v1", tags=["Victim intake (investigator)"])

TAG = "Victim-reported (unverified)"
OFFICER_STAGES = {"with_officer", "action_taken", "closed"}


def _officer(user: dict) -> str:
    return str(user.get("user_id") or "investigator")


def _complaint(complaint_id: str) -> dict:
    c = store.get_complaint(complaint_id)
    if not c:
        for comp in store.complaints.values():
            if comp.get("case_id") == complaint_id or comp.get("ack_id") == complaint_id or comp.get("id") == complaint_id:
                c = comp
                break
    if not c or (c.get("status") not in ("submitted", "Complaint Received", "received") and not c.get("ack_id")):
        raise HTTPException(status_code=404, detail="Complaint not found.")
    return c


def _row(c: dict, detail: bool = False) -> dict:
    case = inv._INVESTIGATIONS.get(c.get("case_id") or "", {})
    paths = case.get("paths") or []
    victim = store.get_victim(c.get("victim_id"))
    pseudonym = (victim.get("display_name") if victim else None) or f"Citizen ***{(victim.get('phone_last4') if victim else 'xxxx')}"
    lifecycle_val = c.get("lifecycle") or "received"
    current_human = (
        "Complaint Received" if lifecycle_val == "received" else (
            "Under Verification" if lifecycle_val in ("under_verification", "verified") else (
                "Investigation in Progress" if lifecycle_val == "in_progress" else (
                    "Action Taken" if lifecycle_val in ("action_taken", "with_officer") else (
                        "Closed" if lifecycle_val == "closed" else STAGE_LABEL.get(lifecycle_val, lifecycle_val)
                    )
                )
            )
        )
    )
    out = {
        "id": c.get("ack_id") or c["id"],
        "complaint_id": c["id"], "ack_id": c["ack_id"], "case_id": c.get("case_id"),
        "victim_pseudonym": pseudonym,
        "tag": TAG if c.get("verification") != "verified" else "Victim-reported (verified by officer)",
        "verification": c.get("verification"),
        "is_verified": c.get("verification") == "verified",
        "stage": lifecycle_val,
        "lifecycle": lifecycle_val,
        "status": current_human,
        "current_stage": current_human,
        "source": "victim_portal",
        "chain": c.get("chain"),
        "address": c.get("scammer_wallet"),
        "scammer_wallet": c.get("scammer_wallet"),
        "amount": f"{c.get('amount_lost')} {c.get('asset')}" if c.get("amount_lost") else "0",
        "amount_lost": c.get("amount_lost"), "asset": c.get("asset"),
        "typology": (c.get("fraud_type") or "other").replace("_", " ").title(),
        "fraud_type": c.get("fraud_type"), "platform": c.get("platform"),
        "story": c.get("story"),
        "timestamp": c.get("submitted_at") or c.get("incident_time") or c.get("created_at"),
        "incident_time": c.get("incident_time"), "submitted_at": c.get("submitted_at"),
        "evidence_count": len({e["file_id"] for e in store.evidence_for_complaint(c["id"])}),
        # investigator-only: how many separate victims reported this same wallet
        "reports_for_wallet": len(store.complaints_for_wallet(c["chain"], c["scammer_wallet"])),
        "preliminary_trace": {
            "done": bool(case.get("preliminary")) or case.get("status") == "completed",
            "paths": len(paths), "max_hops": max((p.hop_count for p in paths), default=0),
            "data_source": case.get("data_source"), "notice": case.get("notice"),
        },
    }
    if detail:
        out.update({"story": c.get("story"), "platform_detail": c.get("platform_detail"),
                    "payment_method": c.get("payment_method"), "tx_hash": c.get("tx_hash"),
                    "history": c.get("history"),
                    "evidence": [{"file_id": e["file_id"], "version": e["version"], "filename": e["filename"],
                                  "mime": e["mime"], "size_bytes": e["size_bytes"], "sha256": e["sha256"],
                                  "restricted": e["restricted"], "uploaded_at": e["uploaded_at"]}
                                 for e in store.evidence_for_complaint(c["id"])],
                    "requests": store.requests_for(c["id"])})
    return out


@router.get("/intake-queue")
def intake_queue(stage: Optional[str] = None, user: dict = Depends(require_authorized_investigator)):
    rows = []
    seen = set()
    for c in sorted(store.submitted_complaints(), key=lambda x: x.get("submitted_at") or x.get("created_at") or "", reverse=True):
        if stage and stage.lower() not in ("all", "") and c.get("lifecycle") != stage:
            continue
        store.log_pii_access(c, "investigator", _officer(user), "viewed your complaint in the review queue")
        r = _row(c)
        rows.append(r)
        if c.get("id"):
            seen.add(c["id"])
        if c.get("ack_id"):
            seen.add(c["ack_id"])
        if c.get("case_id"):
            seen.add(c["case_id"])

    # Check for cases in investigation store with source == 'victim_portal'
    for cid, case in list(inv._INVESTIGATIONS.items()):
        if case.get("source") == "victim_portal" and cid not in seen and case.get("complaint_ref") not in seen:
            rows.append({
                "id": case.get("complaint_ref") or cid,
                "complaint_id": cid,
                "ack_id": case.get("complaint_ref") or f"ACK-{cid[:8]}",
                "case_id": cid,
                "victim_pseudonym": "Citizen Reporter",
                "tag": TAG if not case.get("source_verified") else "Victim-reported (verified by officer)",
                "verification": "verified" if case.get("source_verified") else "unverified",
                "is_verified": bool(case.get("source_verified")),
                "stage": "in_progress" if case.get("source_verified") else "received",
                "lifecycle": "in_progress" if case.get("source_verified") else "received",
                "status": "Investigation in Progress" if case.get("source_verified") else "Complaint Received",
                "current_stage": "Investigation in Progress" if case.get("source_verified") else "Complaint Received",
                "source": "victim_portal",
                "chain": case.get("chain"),
                "address": case.get("reported_address"),
                "scammer_wallet": case.get("reported_address"),
                "amount": f"{case.get('amount', 0)} {case.get('asset', 'USDT')}",
                "amount_lost": case.get("amount", 0),
                "asset": case.get("asset", "USDT"),
                "typology": (case.get("complaint_category") or "Crypto Fraud").replace("_", " ").title(),
                "fraud_type": case.get("complaint_category") or "other",
                "platform": "online",
                "story": case.get("story") or "Citizen complaint registered via victim portal.",
                "timestamp": case.get("timestamp") or case.get("created_at"),
                "evidence_count": 0,
                "reports_for_wallet": 1,
                "preliminary_trace": {
                    "done": bool(case.get("preliminary")) or case.get("status") == "completed",
                    "paths": len(case.get("paths") or []),
                    "max_hops": max((p.hop_count for p in (case.get("paths") or [])), default=0),
                    "data_source": case.get("data_source"),
                    "notice": case.get("notice"),
                },
            })
            seen.add(cid)
    return rows


@router.get("/intake/{complaint_id}")
def intake_detail(complaint_id: str, user: dict = Depends(require_authorized_investigator)):
    c = _complaint(complaint_id)
    store.log_pii_access(c, "investigator", _officer(user), "opened your full complaint")
    return _row(c, detail=True)


def _run_full_pipeline(case_id: str, complaint_id: str) -> None:
    from backend.api.v1.cases import CaseCreateOptions, _execute_case_pipeline
    c = store.get_complaint(complaint_id)
    case = inv._INVESTIGATIONS.get(case_id)
    if not c or not case:
        return
    try:
        _execute_case_pipeline(
            case_id=case_id, chain=case["chain"], reported_address=case["reported_address"],
            options=CaseCreateOptions(), complaint_category=c.get("fraud_type"),
            reported_amount=float(c.get("amount_lost") or 0.0),
        )
        store.set_lifecycle(complaint_id, "in_progress")
        store.notify(c["victim_id"], complaint_id)
    except Exception:  # noqa: BLE001
        logger.exception("Full pipeline failed for complaint %s", complaint_id)


@router.post("/intake/{complaint_id}/verify", status_code=status.HTTP_202_ACCEPTED)
def verify_complaint(complaint_id: str, background: BackgroundTasks,
                     user: dict = Depends(require_authorized_investigator)):
    c = _complaint(complaint_id)
    if c.get("verification") == "verified":
        return {"status": "already_verified", "stage": c.get("lifecycle")}
    if c.get("verification") == "rejected":
        raise HTTPException(status_code=409, detail="This complaint was closed as not actionable.")
    case = inv._INVESTIGATIONS.get(c.get("case_id") or "")
    if case is None:
        raise HTTPException(status_code=409, detail="The linked case is not loaded; try again shortly.")

    store.update_complaint(complaint_id, verification="verified", verified_by=_officer(user))
    store.set_lifecycle(complaint_id, "verified")
    case["source_verified"] = True
    case["verification"] = "verified"
    inv._store.persist_case(case)
    store.notify(c["victim_id"], complaint_id)
    global_audit_logger.log_event(event="victim_complaint_verified", actor=_officer(user),
                                  case_id=case["id"], parameters={"ack_id": c["ack_id"]},
                                  data_source="victim_portal")
    if case.get("status") != "completed":  # full tracing, attribution, alerts, recovery clock
        background.add_task(_run_full_pipeline, case["id"], complaint_id)
    else:
        store.set_lifecycle(complaint_id, "in_progress")
    return {"status": "verified", "stage": "verified", "full_investigation": "started"}


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/intake/{complaint_id}/reject")
def reject_complaint(complaint_id: str, body: RejectBody,
                     user: dict = Depends(require_authorized_investigator)):
    """Close a complaint as not actionable. Creates no alert and sends no external notice."""
    c = _complaint(complaint_id)
    if c.get("verification") == "verified":
        raise HTTPException(status_code=409, detail="A verified complaint cannot be rejected.")
    store.update_complaint(complaint_id, verification="rejected", rejected_reason=body.reason,
                           verified_by=_officer(user))
    store.set_lifecycle(complaint_id, "closed")
    store.notify(c["victim_id"], complaint_id)
    global_audit_logger.log_event(event="victim_complaint_rejected", actor=_officer(user),
                                  case_id=c.get("case_id"), parameters={"ack_id": c["ack_id"]},
                                  data_source="victim_portal")
    return {"status": "closed"}


class StageBody(BaseModel):
    stage: str


@router.post("/intake/{complaint_id}/stage")
def set_stage(complaint_id: str, body: StageBody, user: dict = Depends(require_authorized_investigator)):
    c = _complaint(complaint_id)
    if body.stage not in OFFICER_STAGES:
        raise HTTPException(status_code=422, detail=f"Stage must be one of {sorted(OFFICER_STAGES)}.")
    if c.get("verification") != "verified":
        raise HTTPException(status_code=409, detail="Verify the complaint before changing its stage.")
    store.set_lifecycle(complaint_id, body.stage)
    store.notify(c["victim_id"], complaint_id)
    return {"stage": body.stage}


class StatusUpdateBody(BaseModel):
    status: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None


@router.patch("/intake/{complaint_id}/status")
@router.post("/intake/{complaint_id}/status")
def update_intake_status(complaint_id: str, body: StatusUpdateBody,
                         background: BackgroundTasks,
                         user: dict = Depends(require_authorized_investigator)):
    """Update complaint lifecycle stage from investigator console."""
    c = _complaint(complaint_id)
    raw_stage = (body.stage or body.status or "").strip().lower()

    stage_map = {
        "complaint submitted": "submitted",
        "submitted": "submitted",
        "complaint received": "received",
        "received": "received",
        "under verification": "under_verification",
        "under_verification": "under_verification",
        "verified": "verified",
        "investigation in progress": "in_progress",
        "in progress": "in_progress",
        "in_progress": "in_progress",
        "action taken": "action_taken",
        "action_taken": "action_taken",
        "with officer": "with_officer",
        "with_officer": "with_officer",
        "closed": "closed",
        "resolved": "closed",
        "rejected": "closed",
    }

    lifecycle_val = stage_map.get(raw_stage, raw_stage)
    if not lifecycle_val:
        raise HTTPException(status_code=422, detail="Valid stage or status required.")

    case = inv._INVESTIGATIONS.get(c.get("case_id") or "")

    if lifecycle_val in ("under_verification", "verified"):
        store.update_complaint(c["id"], verification="verified" if lifecycle_val == "verified" else "under_verification", verified_by=_officer(user))
        if case:
            case["status"] = "Under Verification"
            inv._store.persist_case(case)
    elif lifecycle_val == "in_progress":
        store.update_complaint(c["id"], verification="verified", verified_by=_officer(user))
        if case:
            case["source_verified"] = True
            case["verification"] = "verified"
            case["status"] = "completed"
            background.add_task(_run_full_pipeline, case["id"], c["id"])
            inv._store.persist_case(case)
    elif lifecycle_val in ("action_taken", "with_officer"):
        store.update_complaint(c["id"], verification="verified", verified_by=_officer(user))
        if case:
            case["status"] = "Action Taken"
            inv._store.persist_case(case)
    elif lifecycle_val == "closed":
        if c.get("verification") != "verified":
            store.update_complaint(c["id"], verification="rejected", verified_by=_officer(user))
        else:
            store.update_complaint(c["id"], verified_by=_officer(user))
        if case:
            case["status"] = "closed"
            inv._store.persist_case(case)

    store.set_lifecycle(c["id"], lifecycle_val)
    store.notify(c["victim_id"], c["id"])

    global_audit_logger.log_event(
        event="victim_complaint_status_updated",
        actor=_officer(user),
        case_id=c.get("case_id"),
        parameters={"ack_id": c.get("ack_id"), "stage": lifecycle_val},
        data_source="victim_portal",
    )

    human_stage = (
        "Complaint Received" if lifecycle_val == "received" else (
            "Under Verification" if lifecycle_val in ("under_verification", "verified") else (
                "Investigation in Progress" if lifecycle_val == "in_progress" else (
                    "Action Taken" if lifecycle_val in ("action_taken", "with_officer") else (
                        "Closed" if lifecycle_val == "closed" else STAGE_LABEL.get(lifecycle_val, lifecycle_val)
                    )
                )
            )
        )
    )

    return {
        "status": "success",
        "complaint_id": c["id"],
        "ack_id": c.get("ack_id"),
        "case_id": c.get("case_id"),
        "stage": lifecycle_val,
        "current_stage": human_stage,
    }


class RequestBody(BaseModel):
    text: str = Field(..., min_length=3, max_length=500)


@router.post("/intake/{complaint_id}/requests", status_code=status.HTTP_201_CREATED)
def ask_victim(complaint_id: str, body: RequestBody, user: dict = Depends(require_authorized_investigator)):
    """Ask the victim for more proof. The victim reads this text, so keep internal notes out of it."""
    c = _complaint(complaint_id)
    row = store.add_request(complaint_id, body.text, _officer(user))
    store.notify(c["victim_id"], complaint_id)
    return {"request_id": row["id"]}


@router.get("/intake/{complaint_id}/evidence/{file_id}/download")
def officer_download(complaint_id: str, file_id: str, version: Optional[int] = None,
                     user: dict = Depends(require_authorized_investigator)):
    c = _complaint(complaint_id)
    files = [e for e in store.evidence_for_complaint(complaint_id) if e["file_id"] == file_id
             and (version is None or e["version"] == version)]
    if not files:
        raise HTTPException(status_code=404, detail="File not found.")
    e = files[-1]
    store.log_pii_access(c, "investigator", _officer(user), f"downloaded an evidence file ({e['filename']})", 0)
    store.append_custody(file_id, e["version"], "accessed_by_officer", f"officer:{_officer(user)}", e["sha256"])
    return Response(content=ev.global_blob_store.read(e["blob_path"]), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{e["filename"]}"',
                             "X-Content-Type-Options": "nosniff"})
