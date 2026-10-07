"""Victim-portal data store: in-memory with best-effort write-through to Supabase.

Tables (see migrations/004_victim_portal.sql): victims, victim_consents, complaints,
victim_case_link, evidence_files, evidence_custody_log, case_messages, notifications,
pii_access_log. Victims and complaints are re-loaded from Supabase on a cache miss so the
portal keeps working after a server restart. A Supabase failure is logged, never raised.
"""

import hashlib
import logging
import secrets
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder

from backend.database.supabase_client import SupabaseClient, global_supabase_client

logger = logging.getLogger("crypto_attribution.victim.store")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wallet_key(chain: str, wallet: str) -> tuple:
    w = wallet.strip()
    return (chain.lower(), w.lower() if chain.lower() in ("ethereum", "bsc") else w)


class VictimStore:
    def __init__(self, supabase: Optional[SupabaseClient] = None):
        self.supabase = supabase or global_supabase_client
        self._lock = threading.RLock()
        self.victims: Dict[str, dict] = {}
        self.consents: List[dict] = []
        self.complaints: Dict[str, dict] = {}
        self.links: List[dict] = []
        self.evidence: Dict[str, dict] = {}            # record id -> row (one row per version)
        self._evidence_loaded: set = set()
        self.custody: List[dict] = []
        self._last_custody_hash: Optional[str] = None
        self.messages: List[dict] = []
        self.notifications: List[dict] = []
        self.pii_access: List[dict] = []

    # ---- persistence helpers ------------------------------------------------------------
    def _persist(self, table: str, row: dict) -> None:
        if not self.supabase.is_configured:
            return
        try:
            if not self.supabase.upsert_sync(table, jsonable_encoder(row), on_conflict="id"):
                logger.warning("Victim store: could not save a row to %s", table)
        except Exception as e:  # noqa: BLE001
            logger.error("Victim store: save to %s failed: %s", table, e)

    def _select(self, table: str, filters: Dict[str, str]) -> List[dict]:
        if not self.supabase.is_configured:
            return []
        try:
            return self.supabase.select_sync(table, filters) or []
        except Exception as e:  # noqa: BLE001
            logger.error("Victim store: read from %s failed: %s", table, e)
            return []

    # ---- victims ------------------------------------------------------------------------
    def find_victim_by_phone_hash(self, phash: str) -> Optional[dict]:
        with self._lock:
            for v in self.victims.values():
                if v["phone_hash"] == phash:
                    return v
        rows = self._select("victims", {"phone_hash": f"eq.{phash}"})
        if rows:
            with self._lock:
                self.victims[rows[0]["id"]] = rows[0]
            return rows[0]
        return None

    def create_victim(self, phash: str, last4: str, display_name: Optional[str], language: str) -> dict:
        row = {"id": str(uuid.uuid4()), "phone_hash": phash, "phone_last4": last4,
               "display_name": display_name, "language": language, "created_at": now_iso()}
        with self._lock:
            self.victims[row["id"]] = row
        self._persist("victims", row)
        return row

    def get_victim(self, victim_id: str) -> Optional[dict]:
        with self._lock:
            v = self.victims.get(victim_id)
        if v:
            return v
        rows = self._select("victims", {"id": f"eq.{victim_id}"})
        if rows:
            with self._lock:
                self.victims[victim_id] = rows[0]
            return rows[0]
        return None

    def add_consent(self, victim_id: str, notice_version: str, purpose_text: str) -> dict:
        row = {"id": str(uuid.uuid4()), "victim_id": victim_id, "notice_version": notice_version,
               "purpose_text": purpose_text, "accepted_at": now_iso()}
        with self._lock:
            self.consents.append(row)
        self._persist("victim_consents", row)
        return row

    def has_consent(self, victim_id: str, notice_version: str) -> bool:
        with self._lock:
            if any(c["victim_id"] == victim_id and c["notice_version"] == notice_version for c in self.consents):
                return True
        return bool(self._select("victim_consents",
                                 {"victim_id": f"eq.{victim_id}", "notice_version": f"eq.{notice_version}"}))

    # ---- complaints ---------------------------------------------------------------------
    def create_complaint(self, victim_id: str, fields: dict) -> dict:
        row = {"id": str(uuid.uuid4()), "victim_id": victim_id, "status": "draft", "lifecycle": "draft",
               "ack_id": None, "case_id": None, "verification": "unverified", "history": [],
               "created_at": now_iso(), "updated_at": now_iso(), **fields}
        with self._lock:
            self.complaints[row["id"]] = row
        self._persist("complaints", row)
        return row

    def get_complaint(self, complaint_id: str) -> Optional[dict]:
        with self._lock:
            if not complaint_id:
                return None
            cid_clean = str(complaint_id).strip()
            # 1. Exact or case-insensitive match by id
            c = self.complaints.get(cid_clean)
            if c:
                return c
            for comp in self.complaints.values():
                if comp.get("id") and comp["id"].lower() == cid_clean.lower():
                    return comp
            # 2. Check by ack_id in memory (case-insensitive and prefix-tolerant)
            for comp in self.complaints.values():
                ack = comp.get("ack_id")
                if ack:
                    if ack.lower() == cid_clean.lower():
                        return comp
                    if "-" in ack and "-" in cid_clean:
                        if ack.split("-", 1)[1].lower() == cid_clean.split("-", 1)[1].lower():
                            return comp
            # 3. Check by case_id
            for comp in self.complaints.values():
                case_id = comp.get("case_id")
                if case_id and case_id.lower() == cid_clean.lower():
                    return comp
        rows = self._select("complaints", {"id": f"eq.{complaint_id}"})
        if rows:
            with self._lock:
                self.complaints[complaint_id] = rows[0]
            return rows[0]
        if cid_clean:
            ack_rows = self._select("complaints", {"ack_id": f"eq.{cid_clean.upper()}"})
            if ack_rows:
                with self._lock:
                    self.complaints[ack_rows[0]["id"]] = ack_rows[0]
                return ack_rows[0]
        return None

    def update_complaint(self, complaint_id: str, **fields: Any) -> dict:
        with self._lock:
            c = self.complaints.get(complaint_id)
            if not c:
                cid_str = str(complaint_id).strip().lower()
                for comp in self.complaints.values():
                    if (comp.get("ack_id") and comp["ack_id"].strip().lower() == cid_str) or \
                       (comp.get("case_id") and comp["case_id"].strip().lower() == cid_str) or \
                       (comp.get("id") and comp["id"].strip().lower() == cid_str):
                        c = comp
                        complaint_id = comp["id"]
                        break
            if not c:
                return {}
            c.update(fields)
            c["updated_at"] = now_iso()
        self._persist("complaints", c)
        return c

    def set_lifecycle(self, complaint_id: str, stage: str) -> dict:
        with self._lock:
            c = self.complaints.get(complaint_id)
            if not c:
                cid_str = str(complaint_id).strip().lower()
                for comp in self.complaints.values():
                    if (comp.get("ack_id") and comp["ack_id"].strip().lower() == cid_str) or \
                       (comp.get("case_id") and comp["case_id"].strip().lower() == cid_str) or \
                       (comp.get("id") and comp["id"].strip().lower() == cid_str):
                        c = comp
                        complaint_id = comp["id"]
                        break
            if not c:
                return {}
            history = list(c.get("history") or [])
            if not history or history[-1]["stage"] != stage:
                history.append({"stage": stage, "at": now_iso()})
        return self.update_complaint(complaint_id, lifecycle=stage, history=history)

    def new_ack_id(self) -> str:
        with self._lock:
            existing = {c.get("ack_id") for c in self.complaints.values()}
        while True:
            ack = f"VC-{datetime.now(timezone.utc).year}-{secrets.token_hex(4).upper()}"
            if ack not in existing:
                return ack

    def list_complaints(self, victim_id: str) -> List[dict]:
        rows = self._select("complaints", {"victim_id": f"eq.{victim_id}"})
        with self._lock:
            for r in rows:
                self.complaints.setdefault(r["id"], r)
            mine = [c for c in self.complaints.values() if c["victim_id"] == victim_id]
        return sorted(mine, key=lambda c: c.get("created_at") or "", reverse=True)

    def submitted_complaints(self) -> List[dict]:
        with self._lock:
            return [c for c in self.complaints.values()
                    if c.get("status") in ("submitted", "Complaint Received", "received") or c.get("ack_id")]

    def find_own_submitted(self, victim_id: str, chain: str, wallet: str) -> Optional[dict]:
        key = _wallet_key(chain, wallet)
        for c in self.list_complaints(victim_id):
            if c.get("status") == "submitted" and c.get("chain") and _wallet_key(c["chain"], c["scammer_wallet"]) == key:
                return c
        return None

    def complaints_for_wallet(self, chain: str, wallet: str) -> List[dict]:
        key = _wallet_key(chain, wallet)
        return [c for c in self.submitted_complaints()
                if c.get("chain") and _wallet_key(c["chain"], c["scammer_wallet"]) == key]

    def link_case(self, victim_id: str, case_id: str, complaint_id: str, scope: str = "status_only") -> None:
        row = {"id": str(uuid.uuid4()), "victim_id": victim_id, "case_id": case_id,
               "complaint_id": complaint_id, "consent_scope": scope, "created_at": now_iso()}
        with self._lock:
            self.links.append(row)
        self._persist("victim_case_link", row)

    def hidden_case_ids(self) -> set:
        """Case ids that came from a victim and have not been verified by an officer yet."""
        with self._lock:
            complaints = list(self.complaints.values())
        hidden = {c["case_id"] for c in complaints
                  if c.get("case_id") and c.get("status") in ("submitted", "Complaint Received", "received") and c.get("verification") != "verified"}
        verified = {c["case_id"] for c in complaints if c.get("verification") == "verified"}
        for row in self._select("complaints", {"status": "in.(submitted,Complaint Received,received)", "verification": "neq.verified"}):
            if row.get("case_id"):
                hidden.add(row["case_id"])
        return hidden - verified

    # ---- evidence -----------------------------------------------------------------------
    def evidence_for_complaint(self, complaint_id: str) -> List[dict]:
        if complaint_id not in self._evidence_loaded:
            rows = self._select("evidence_files", {"complaint_id": f"eq.{complaint_id}"})
            with self._lock:
                for r in rows:
                    self.evidence.setdefault(r["id"], r)
                self._evidence_loaded.add(complaint_id)
        with self._lock:
            return sorted((e for e in self.evidence.values() if e["complaint_id"] == complaint_id),
                          key=lambda e: (e["file_id"], e["version"]))

    def add_evidence(self, row: dict) -> dict:
        with self._lock:
            self.evidence[row["id"]] = row
        self._persist("evidence_files", row)
        return row

    def append_custody(self, file_id: str, version: int, event: str, actor: str, sha256: str) -> dict:
        """Append-only, hash-chained custody entry (each entry commits to the previous one)."""
        with self._lock:
            if self._last_custody_hash is None and self.supabase.is_configured:
                last = self._select("evidence_custody_log", {"order": "at.desc", "limit": "1"})
                if last:
                    self._last_custody_hash = last[0].get("entry_hash")
            prev = self._last_custody_hash or "GENESIS"
            at = now_iso()
            entry_hash = hashlib.sha256(
                "|".join([prev, file_id, str(version), event, actor, sha256, at]).encode()).hexdigest()
            row = {"id": str(uuid.uuid4()), "file_id": file_id, "version": version, "event": event,
                   "actor": actor, "sha256": sha256, "at": at, "prev_hash": prev, "entry_hash": entry_hash}
            self.custody.append(row)
            self._last_custody_hash = entry_hash
        self._persist("evidence_custody_log", row)
        return row

    def custody_for_file(self, file_id: str) -> List[dict]:
        with self._lock:
            mem = [c for c in self.custody if c["file_id"] == file_id]
        return mem or self._select("evidence_custody_log", {"file_id": f"eq.{file_id}"})

    def custody_chain_intact(self) -> bool:
        with self._lock:
            prev = "GENESIS"
            for e in self.custody:
                expected = hashlib.sha256("|".join(
                    [prev, e["file_id"], str(e["version"]), e["event"], e["actor"], e["sha256"], e["at"]]
                ).encode()).hexdigest()
                if e["prev_hash"] != prev or e["entry_hash"] != expected:
                    return False
                prev = e["entry_hash"]
        return True

    # ---- officer requests / notifications / access log -------------------------------
    def add_request(self, complaint_id: str, text: str, officer: str) -> dict:
        row = {"id": str(uuid.uuid4()), "complaint_id": complaint_id, "kind": "request",
               "sender": "officer", "body": text, "status": "open", "created_at": now_iso(),
               "officer_ref": officer}
        with self._lock:
            self.messages.append(row)
        self._persist("case_messages", row)
        return row

    def requests_for(self, complaint_id: str) -> List[dict]:
        with self._lock:
            mem = [m for m in self.messages if m["complaint_id"] == complaint_id and m["kind"] == "request"]
        return mem or self._select("case_messages", {"complaint_id": f"eq.{complaint_id}", "kind": "eq.request"})

    def answer_request(self, request_id: str, complaint_id: str) -> None:
        with self._lock:
            for m in self.messages:
                if m["id"] == request_id and m["complaint_id"] == complaint_id:
                    m["status"] = "answered"
                    self._persist("case_messages", m)

    def notify(self, victim_id: str, complaint_id: str) -> None:
        # Deliberately generic: no details about the case ever go in a notification.
        row = {"id": str(uuid.uuid4()), "victim_id": victim_id, "complaint_id": complaint_id,
               "message": "Your case has an update", "created_at": now_iso(), "read": False}
        with self._lock:
            self.notifications.append(row)
        self._persist("notifications", row)

    def notifications_for(self, victim_id: str) -> List[dict]:
        with self._lock:
            mem = [n for n in self.notifications if n["victim_id"] == victim_id]
        rows = mem or self._select("notifications", {"victim_id": f"eq.{victim_id}"})
        return sorted(rows, key=lambda n: n["created_at"], reverse=True)

    def log_pii_access(self, complaint: dict, accessor_role: str, accessor_ref: str, action: str,
                       dedupe_seconds: int = 300) -> None:
        """Record that someone viewed victim data. Repeats within a few minutes are collapsed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            for e in reversed(self.pii_access[-200:]):
                if (e["complaint_id"] == complaint["id"] and e["accessor_ref"] == accessor_ref
                        and e["action"] == action
                        and (now - datetime.fromisoformat(e["at"])).total_seconds() < dedupe_seconds):
                    return
            row = {"id": str(uuid.uuid4()), "victim_id": complaint["victim_id"],
                   "complaint_id": complaint["id"], "accessor_role": accessor_role,
                   "accessor_ref": accessor_ref, "action": action, "at": now.isoformat()}
            self.pii_access.append(row)
        self._persist("pii_access_log", row)

    def pii_access_for(self, victim_id: str) -> List[dict]:
        with self._lock:
            mem = [e for e in self.pii_access if e["victim_id"] == victim_id]
        rows = mem or self._select("pii_access_log", {"victim_id": f"eq.{victim_id}"})
        return sorted(rows, key=lambda e: e["at"], reverse=True)

    def reset(self) -> None:
        with self._lock:
            self.__init__(self.supabase)


global_victim_store = VictimStore()
