"""
Stateless Authentication Router for PitWall AI.
Sign-up, sign-in, and session persistence run on the frontend via Supabase Auth;
the backend exposes /api/auth/me to inspect the currently verified Bearer principal.
"""

from fastapi import APIRouter, Depends

from backend.app.auth.dependencies import UserResponse, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Return stateless user identity claims from verified Supabase Bearer JWT."""
    return current_user
