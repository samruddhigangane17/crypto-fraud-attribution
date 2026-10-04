"""Investigator authentication and access control.

Coordinates with Member 3's Supabase Auth.
Validates Bearer token headers and ensures only authorized investigators
can modify state or access forensic evidence reports.
"""

import logging
import os
from typing import Optional
from fastapi import Header, HTTPException, status
import jwt

logger = logging.getLogger("crypto_attribution.auth")

def _jwt_secret() -> str:
    # Read at call time so tests and late-loaded .env files behave predictably.
    return os.getenv("SUPABASE_JWT_SECRET", "").strip()


def _dev_stub_allowed() -> bool:
    return os.getenv("ALLOW_DEV_AUTH_STUB", "").strip().lower() in ("1", "true", "yes")


def require_authorized_investigator(
    authorization: Optional[str] = Header(
        None,
        description="Bearer token issued by Supabase Auth (coordinated with Member 3)",
    ),
) -> dict:
    """Investigator authorization dependency.

    Validates the Supabase JWT signature using SUPABASE_JWT_SECRET. If the secret is unset the
    request is rejected (fail closed) unless ALLOW_DEV_AUTH_STUB=true is set explicitly for local
    development, in which case any well-formed Bearer token is accepted and marked unverified.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. This action requires an authorized investigator session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    secret = _jwt_secret()
    if secret:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",  # Supabase user access tokens carry aud="authenticated"
            )
            return {
                "user_id": payload.get("sub", "investigator"),
                "email": payload.get("email"),
                "role": payload.get("role", "investigator"),
                "token": token,
                "verified": True,
            }
        except jwt.PyJWTError as e:
            logger.warning(f"Invalid Supabase JWT signature: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid or expired investigator token: {e}",
            )

    if not _dev_stub_allowed():
        logger.error("SUPABASE_JWT_SECRET is not set and ALLOW_DEV_AUTH_STUB is not enabled; rejecting request.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on the server. Set SUPABASE_JWT_SECRET "
            "(or ALLOW_DEV_AUTH_STUB=true for local development only).",
        )

    logger.warning("Auth stub mode: accepting an UNVERIFIED token (ALLOW_DEV_AUTH_STUB=true).")
    if token.lower() in ["invalid", "revoked", "expired"] or len(token) < 8:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or revoked investigator credentials.",
        )

    return {
        "user_id": "dev-investigator-001",
        "role": "investigator",
        "token": token,
        "verified": False,
        "note": "Validated via development auth stub (ALLOW_DEV_AUTH_STUB=true). Set SUPABASE_JWT_SECRET for real verification.",
    }
