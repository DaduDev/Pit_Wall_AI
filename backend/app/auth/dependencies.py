"""
Stateless Supabase Bearer JWT authentication dependencies for PitWall AI.

- Zero local user databases or hardcoded credentials.
- Verifies asymmetric Supabase JWTs (ES256/RS256/EdDSA) against
  `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` using a cached `PyJWKClient`
  executed off the async event loop (`asyncio.to_thread`).
- Supports optional `SUPABASE_JWT_SECRET` HS256 fallback for legacy HS256 tokens.
- Validates `audience="authenticated"`, expiration (`exp`), and subject (`sub`).
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.app.config import settings

security = HTTPBearer(auto_error=False)

_JWK_CLIENTS: Dict[str, jwt.PyJWKClient] = {}
_JWK_LOCK = threading.Lock()
_ASYMMETRIC_ALGS = ["ES256", "ES384", "ES512", "RS256", "RS384", "RS512", "PS256", "EdDSA"]
_SYMMETRIC_ALGS = ["HS256", "HS384", "HS512"]


class UserResponse(BaseModel):
    """Authenticated principal derived purely from verified Supabase JWT claims."""

    id: str
    email: str = ""
    display_name: str = ""
    role: str = "authenticated"


def _get_auth_settings() -> Dict[str, str]:
    """Resolve live Supabase JWT verification settings preferring process env."""
    supabase_url = (
        os.environ.get("SUPABASE_URL")
        or getattr(settings, "SUPABASE_URL", "")
        or ""
    ).strip().rstrip("/")
    jwt_secret = (
        os.environ.get("SUPABASE_JWT_SECRET")
        or getattr(settings, "SUPABASE_JWT_SECRET", "")
        or ""
    ).strip()
    audience = (
        os.environ.get("SUPABASE_JWT_AUDIENCE")
        or getattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
        or "authenticated"
    ).strip()
    return {
        "supabase_url": supabase_url,
        "jwt_secret": jwt_secret,
        "audience": audience,
    }


def _get_jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    """Return cached PyJWKClient instance for the Supabase project JWKS endpoint."""
    with _JWK_LOCK:
        client = _JWK_CLIENTS.get(jwks_url)
        if client is None:
            client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
            _JWK_CLIENTS[jwks_url] = client
        return client


def clear_jwk_cache() -> None:
    """Clear cached PyJWKClient instances (used in unit tests)."""
    with _JWK_LOCK:
        _JWK_CLIENTS.clear()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Synchronously decode and validate a Supabase Bearer JWT.
    Called off the async event loop via asyncio.to_thread inside get_current_user.
    """
    if not token or not token.strip():
        raise _unauthorized("Authentication credentials missing.")

    cfg = _get_auth_settings()
    supabase_url = cfg["supabase_url"]
    jwt_secret = cfg["jwt_secret"]
    audience = cfg["audience"]

    try:
        header = jwt.get_unverified_header(token)
        alg = str(header.get("alg") or "").upper()
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid authentication token.")

    try:
        if alg in _SYMMETRIC_ALGS:
            if not jwt_secret:
                raise _unauthorized("Invalid authentication token.")
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=[alg],
                audience=audience,
                options={"require": ["exp", "sub"]},
            )
        elif alg in _ASYMMETRIC_ALGS:
            if not supabase_url:
                raise _unauthorized("Authentication service URL is not configured.")
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            issuer = f"{supabase_url}/auth/v1"
            jwk_client = _get_jwk_client(jwks_url)
            signing_key = jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=_ASYMMETRIC_ALGS,
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "sub"]},
            )
        else:
            raise _unauthorized("Unsupported authentication token algorithm.")
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired. Please sign in again.")
    except jwt.InvalidAudienceError:
        raise _unauthorized("Invalid token audience.")
    except (jwt.PyJWKClientError, jwt.InvalidTokenError):
        raise _unauthorized("Invalid authentication token.")

    if not payload.get("sub"):
        raise _unauthorized("Invalid authentication token.")
    return payload


def user_from_claims(payload: Dict[str, Any]) -> UserResponse:
    """Build stateless UserResponse principal from verified Supabase JWT claims."""
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise _unauthorized("Invalid authentication token.")

    email = str(payload.get("email") or "").strip()
    meta = payload.get("user_metadata")
    meta_dict = meta if isinstance(meta, dict) else {}
    display_name = (
        str(
            meta_dict.get("display_name")
            or meta_dict.get("full_name")
            or (email.split("@")[0] if email else "Engineer")
        ).strip()
    )
    role = str(payload.get("role") or "authenticated").strip()
    return UserResponse(
        id=user_id,
        email=email,
        display_name=display_name or "Engineer",
        role=role,
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserResponse:
    """FastAPI dependency verifying Bearer JWT off the async event loop."""
    if not credentials or not credentials.credentials:
        raise _unauthorized("Authentication credentials missing.")

    payload = await asyncio.to_thread(decode_access_token, credentials.credentials)
    return user_from_claims(payload)
