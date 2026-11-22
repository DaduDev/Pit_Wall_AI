"""
Authentication dependencies, JWT utilities, and password hashing for PitWall AI.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from backend.app.config import settings

security = HTTPBearer(auto_error=False)


class UserAccount(BaseModel):
    id: str
    email: str
    display_name: str
    password_hash: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str


# In-memory user store seeded with demo user
# Password: "Pitwall2024!"
DEMO_PASSWORD = "Pitwall2024!"
DEMO_SALT = bcrypt.gensalt()
DEMO_HASH = bcrypt.hashpw(DEMO_PASSWORD.encode("utf-8"), DEMO_SALT).decode("utf-8")

USERS_DB: Dict[str, UserAccount] = {
    "demo@pitwall.ai": UserAccount(
        id="usr_demo_pitwall_001",
        email="demo@pitwall.ai",
        display_name="Race Engineer Demo",
        password_hash=DEMO_HASH,
    )
}


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encodes JWT access token with expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserResponse:
    """Dependency that extracts and verifies current user from Bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    email: Optional[str] = payload.get("sub")
    if email is None or email not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or credentials invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = USERS_DB[email]
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)
