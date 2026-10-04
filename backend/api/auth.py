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

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def require_authorized_investigator(
    authorization: Optional[str] = Header(
        None,
        description="Bearer token issued by Supabase Auth (coordinated with Member 3)",
    ),
) -> dict:
    """Investigator authorization dependency.

    In production/Phase 2: Validates Supabase JWT signature using SUPABASE_JWT_SECRET.
    In development/prototype: If SUPABASE_JWT_SECRET is unset, operates in token stub
    mode (verifying valid Bearer token structure), pending Member 3's Supabase Auth setup.
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

    # If Supabase JWT Secret is configured in .env, verify cryptographic signature
    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
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

    # Prototype / Development Stub Mode (when SUPABASE_JWT_SECRET is not configured)
    logger.debug("Operating in development auth stub mode (SUPABASE_JWT_SECRET not set).")
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
        "note": "Validated via development auth stub. Set SUPABASE_JWT_SECRET for production signature verification.",
    }
