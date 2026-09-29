from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies import get_current_user, require_roles
from src.core.config import Settings, get_settings
from src.core.security import create_access_token, hash_password, verify_password
from src.db.models.user import User, UserRole
from src.db.session import get_db
from src.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new enterprise user account",
)
async def register_user(
    payload: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Creates a new user record within the specified tenant boundary."""
    # 1. Check for existing user in the same tenant
    query = select(User).where(
        User.tenant_id == payload.tenant_id,
        User.email == payload.email,
    )
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' already exists in tenant '{payload.tenant_id}'.",
        )

    # 2. Hash password and insert record
    new_user = User(
        tenant_id=payload.tenant_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate credentials and issue JWT access token",
)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Validates user credentials and issues a signed JWT access token."""
    query = select(User).where(
        User.tenant_id == payload.tenant_id,
        User.email == payload.email,
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # Generic error message to prevent user enumeration attacks
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or disabled.",
        )

    # Issue signed JWT with subject and enterprise claims
    token_claims = {
        "sub": str(user.id),
        "tenant_id": user.tenant_id,
        "role": user.role.value,
        "email": user.email,
    }
    access_token = create_access_token(data=token_claims)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Returns the authenticated user context extracted from the JWT token."""
    return current_user


@router.get(
    "/admin-only",
    status_code=status.HTTP_200_OK,
    summary="Restricted test endpoint requiring ADMIN role",
)
async def admin_only_endpoint(
    current_user: Annotated[User, Depends(require_roles([UserRole.ADMIN]))],
) -> dict[str, str]:
    """Demonstrates RBAC enforcement: Rejects non-admin users with HTTP 403."""
    return {
        "message": "Access granted: You are authorized as an Admin.",
        "user_email": current_user.email,
        "role": current_user.role.value,
    }
