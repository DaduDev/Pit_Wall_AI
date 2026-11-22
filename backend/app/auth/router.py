"""
Authentication router for PitWall AI.
Handles registration, login, and token verification.
"""

import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from backend.app.auth.dependencies import (
    USERS_DB,
    UserAccount,
    UserResponse,
    create_access_token,
    hash_password,
    verify_password,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: UserResponse


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Registers a new user account."""
    if body.email in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    hashed_pw = hash_password(body.password)
    user = UserAccount(
        id=user_id,
        email=body.email,
        display_name=body.display_name,
        password_hash=hashed_pw,
    )
    USERS_DB[body.email] = user

    token = create_access_token({"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=86400,
        user=UserResponse(id=user.id, email=user.email, display_name=user.display_name),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticates an existing user and returns JWT access token."""
    user = USERS_DB.get(body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=86400,
        user=UserResponse(id=user.id, email=user.email, display_name=user.display_name),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Returns profile for currently authenticated user."""
    return current_user
