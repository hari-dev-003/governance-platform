"""Authentication: login (OAuth2 password), me, and admin user management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_only
from app.core.database import get_db
from app.core.security import (
    create_access_token, get_current_user, hash_password, verify_password,
)
from app.models.identity import Organization, User
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])

ROLES = ("admin", "data_steward", "viewer", "ai_risk_officer")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    user_id: str
    org_id: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    org_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class CreateUserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = None
    role: str = "viewer"


@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == form.username))).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(form.password, user.password_hash) \
            or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    user.last_login = datetime.now(timezone.utc)
    token = create_access_token(subject=str(user.id), role=user.role, org_id=str(user.org_id))
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="user.login",
                       resource_type="user", resource_id=str(user.id), resource_name=user.email)
    return TokenOut(access_token=token, role=user.role, username=user.email,
                    user_id=str(user.id), org_id=str(user.org_id))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), user: User = Depends(admin_only)):
    rows = (await db.execute(select(User).where(User.org_id == user.org_id))).scalars().all()
    return list(rows)


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(payload: CreateUserIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(admin_only)):
    if payload.role not in ROLES:
        raise HTTPException(400, f"role must be one of {ROLES}")
    exists = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "email already exists")
    new = User(org_id=user.org_id, email=payload.email, full_name=payload.full_name,
               password_hash=hash_password(payload.password), role=payload.role)
    db.add(new)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="user.created",
                       resource_type="user", resource_id=str(new.id), resource_name=new.email)
    return new
