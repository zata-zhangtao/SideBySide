from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import Friendship, User


router = APIRouter()


@router.get("/users/me")
def me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"id": user.id, "username": user.username, "email": user.email}


@router.post("/friends/add")
def add_friend(username: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    target = db.exec(select(User).where(User.username == username)).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")
    exists = db.exec(
        select(Friendship).where(Friendship.user_id == user.id, Friendship.friend_id == target.id)
    ).first()
    if exists:
        return {"message": "Already friends"}
    db.add(Friendship(user_id=user.id, friend_id=target.id))
    db.add(Friendship(user_id=target.id, friend_id=user.id))
    db.commit()
    return {"message": "Friend added"}


@router.get("/friends")
def list_friends(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    rows = db.exec(select(Friendship).where(Friendship.user_id == user.id)).all()
    ids = [r.friend_id for r in rows]
    friends = db.exec(select(User).where(User.id.in_(ids))).all() if ids else []
    return [{"id": f.id, "username": f.username} for f in friends]

