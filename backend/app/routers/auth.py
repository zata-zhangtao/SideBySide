from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..core.security import create_access_token, get_password_hash, verify_password
from ..deps import get_db
from ..models import User


router = APIRouter()


@router.post("/auth/register")
def register(
    username: str | None = None,
    password: str | None = None,
    email: str | None = None,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Accept either query params or JSON body: {"username","password","email"}
    if payload:
        username = payload.get("username") or username
        password = payload.get("password") or password
        email = payload.get("email") if payload.get("email") is not None else email
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")
    try:
        exists = db.exec(select(User).where(User.username == username)).first()
        if exists:
            raise HTTPException(status_code=400, detail="Username already exists")
        user = User(username=username, email=email, password_hash=get_password_hash(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=8))
        return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "username": user.username}}
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Register failed: {e}")


@router.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=8))
    return {"access_token": token, "token_type": "bearer"}
