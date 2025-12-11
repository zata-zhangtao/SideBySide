from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import Attempt, StudySession, User


router = APIRouter()


@router.get("/reports/weekly")
def weekly_report(user2_username: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    user1 = user
    user2 = db.exec(select(User).where(User.username == user2_username)).first()
    if not user2:
        raise HTTPException(status_code=404, detail="User2 not found")

    since = datetime.utcnow() - timedelta(days=7)
    # Collect attempts in last 7 days for both users
    rows = db.exec(select(Attempt).where(Attempt.created_at >= since, Attempt.user_id.in_([user1.id, user2.id]))).all()

    def summary(uid: int) -> dict[str, Any]:
        attempts = [r for r in rows if r.user_id == uid]
        total = len(attempts)
        correct = sum(1 for r in attempts if r.correct)
        points = sum(r.points for r in attempts)
        accuracy = (correct / total) if total else 0.0
        # mastered words: correct >= 2 on same word in the week (rough proxy)
        from collections import defaultdict

        hits = defaultdict(int)
        for r in attempts:
            if r.correct:
                hits[r.word_id] += 1
        mastered = sum(1 for _, c in hits.items() if c >= 2)
        return {"total": total, "correct": correct, "accuracy": accuracy, "points": points, "mastered": mastered}

    return {
        "since": since.isoformat(),
        "user1": {"id": user1.id, "username": user1.username, **summary(user1.id)},
        "user2": {"id": user2.id, "username": user2.username, **summary(user2.id)},
    }

