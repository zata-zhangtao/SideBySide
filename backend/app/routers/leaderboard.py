from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import Attempt, User


router = APIRouter()


@router.get("/leaderboard")
def leaderboard(period: str = "weekly", limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    since = None
    if period == "weekly":
        since = now - timedelta(days=7)
    elif period == "daily":
        since = now - timedelta(days=1)

    stmt = select(Attempt)
    if since:
        stmt = stmt.where(Attempt.created_at >= since)
    rows = db.exec(stmt).all()
    agg: dict[int, int] = {}
    for r in rows:
        agg[r.user_id] = agg.get(r.user_id, 0) + r.points
    # Sort and materialize
    top = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    users = db.exec(select(User).where(User.id.in_([uid for uid, _ in top]))).all() if top else []
    uname = {u.id: u.username for u in users}
    return [{"user_id": uid, "username": uname.get(uid, str(uid)), "points": pts} for uid, pts in top]

