"""Victim authentication realm: phone OTP -> short-lived victim-only JWT.

This realm is completely separate from investigator auth (Supabase):
  * victim tokens are signed with VICTIM_JWT_SECRET and carry aud="victim-portal"
  * investigator tokens carry aud="authenticated" and are rejected here
  * victim tokens are rejected by `require_authorized_investigator` (wrong audience/secret)

Phone numbers are never stored in plain text: only an HMAC hash (for lookup) and the last 4
digits (for display). OTPs are stored only as HMACs and expire after 5 minutes / 5 attempts.
"""

import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
from typing import Callable, Dict, Optional, Protocol

import jwt
from fastapi import Header, HTTPException, status

logger = logging.getLogger("crypto_attribution.victim.otp")

AUDIENCE = "victim-portal"
ISSUER = "crypto-fraud-attribution"
TOKEN_TTL_SECONDS = 2 * 3600
OTP_TTL_SECONDS = 5 * 60
MAX_OTP_ATTEMPTS = 5

_EPHEMERAL: Dict[str, str] = {}


def dev_mode() -> bool:
    return os.getenv("VICTIM_DEV_MODE", "").strip().lower() in ("1", "true", "yes")


def _config_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if dev_mode():  # throw-away per-process secret, never used in production
        return _EPHEMERAL.setdefault(name, secrets.token_hex(32))
    raise _config_error(f"Victim portal is not configured on the server ({name} is not set).")


def jwt_secret() -> str:
    return _secret("VICTIM_JWT_SECRET")


def pepper() -> str:
    return _secret("VICTIM_PHONE_PEPPER")


# ---- phone helpers --------------------------------------------------------------------------
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_IN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def normalize_phone(raw: str) -> str:
    """Return E.164 or raise ValueError. Accepts 10-digit Indian mobiles and +country numbers."""
    p = re.sub(r"[\s\-().]", "", raw or "")
    if p.startswith("00"):
        p = "+" + p[2:]
    if _IN_MOBILE.match(p):
        p = "+91" + p
    elif re.match(r"^91[6-9]\d{9}$", p):
        p = "+" + p
    if not _E164.match(p):
        raise ValueError("Enter a valid mobile number, e.g. 98XXXXXXXX or +91 98XXXXXXXX.")
    return p


def phone_hash(e164: str) -> str:
    return hmac.new(pepper().encode(), e164.encode(), hashlib.sha256).hexdigest()


# ---- OTP delivery ---------------------------------------------------------------------------
class OtpSender(Protocol):
    def send(self, e164_phone: str, code: str) -> None: ...


class ConsoleOtpSender:
    """Development sender: prints the code to the server console. Replace with an SMS provider."""

    def send(self, e164_phone: str, code: str) -> None:
        print(f"[victim-otp] OTP for ***{e164_phone[-4:]}: {code}")  # noqa: T201


class OtpService:
    def __init__(self, sender: Optional[OtpSender] = None, clock: Callable[[], float] = time.time):
        self.sender: OtpSender = sender or ConsoleOtpSender()
        self._clock = clock
        self._pending: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def _code_mac(self, phash: str, code: str) -> str:
        return hmac.new(pepper().encode(), f"{phash}:{code}".encode(), hashlib.sha256).hexdigest()

    def issue(self, e164_phone: str) -> str:
        """Create + send a fresh OTP. Returns the code (callers only expose it in dev mode)."""
        phash = phone_hash(e164_phone)
        code = f"{secrets.randbelow(10**6):06d}"
        with self._lock:
            self._pending[phash] = {
                "mac": self._code_mac(phash, code),
                "expires": self._clock() + OTP_TTL_SECONDS,
                "attempts": 0,
            }
        self.sender.send(e164_phone, code)
        return code

    def verify(self, e164_phone: str, code: str) -> bool:
        phash = phone_hash(e164_phone)
        with self._lock:
            rec = self._pending.get(phash)
            if not rec or self._clock() > rec["expires"]:
                self._pending.pop(phash, None)
                return False
            rec["attempts"] += 1
            if rec["attempts"] > MAX_OTP_ATTEMPTS:
                self._pending.pop(phash, None)
                return False
            ok = hmac.compare_digest(rec["mac"], self._code_mac(phash, str(code or "")))
            if ok:
                self._pending.pop(phash, None)  # one-time use
            return ok

    def reset(self) -> None:
        with self._lock:
            self._pending.clear()


global_otp_service = OtpService()


# ---- victim JWT -----------------------------------------------------------------------------
def issue_victim_token(victim_id: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": victim_id, "aud": AUDIENCE, "iss": ISSUER, "realm": "victim", "iat": now, "exp": now + ttl},
        jwt_secret(),
        algorithm="HS256",
    )


def require_victim(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: returns the victim_id from a valid victim-realm token."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization:
        raise unauthorized
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise unauthorized
    try:
        payload = jwt.decode(parts[1], jwt_secret(), algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER)
    except jwt.PyJWTError:
        raise unauthorized
    if payload.get("realm") != "victim" or not payload.get("sub"):
        raise unauthorized
    return str(payload["sub"])


def optional_victim(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """FastAPI dependency: returns the victim_id if valid Bearer token provided, else None."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    try:
        payload = jwt.decode(parts[1], jwt_secret(), algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER)
        if payload.get("realm") == "victim" and payload.get("sub"):
            return str(payload["sub"])
    except jwt.PyJWTError:
        return None
    return None
