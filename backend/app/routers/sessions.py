from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import Attempt, StudySession, User, Word, WordList
from ..services.llm_enrich import try_generate_example


router = APIRouter()


@router.post("/sessions")
def create_session(
    wordlist_id: int,
    friend_username: str,
    type: str = "async",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    wl = db.get(WordList, wordlist_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found or not owned by user")
    friend = db.exec(select(User).where(User.username == friend_username)).first()
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    sess = StudySession(type=type, wordlist_id=wl.id, created_by=user.id, user_a_id=user.id, user_b_id=friend.id)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return {"id": sess.id, "type": sess.type, "status": sess.status}


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    wl = db.get(WordList, sess.wordlist_id)
    ua = db.get(User, sess.user_a_id)
    ub = db.get(User, sess.user_b_id)
    return {
        "id": sess.id,
        "type": sess.type,
        "status": sess.status,
        "wordlist": {"id": wl.id, "name": wl.name} if wl else None,
        "participants": [
            {"id": sess.user_a_id, "username": ua.username if ua else str(sess.user_a_id)},
            {"id": sess.user_b_id, "username": ub.username if ub else str(sess.user_b_id)},
        ],
    }


@router.get("/sessions/{session_id}/next_word")
def next_word(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    import random

    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    # Fetch words in the list
    words = db.exec(select(Word).where(Word.list_id == sess.wordlist_id)).all()
    if not words:
        raise HTTPException(status_code=400, detail="No words in the list")
    # Simple random selection; could exclude recently correct items in future
    w = random.choice(words)
    return {"word_id": w.id, "term": w.term, "definition": w.definition}


@router.post("/sessions/{session_id}/attempts")
def submit_attempt(
    session_id: int,
    word_id: int,
    answer: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    word = db.get(Word, word_id)
    if not word or word.list_id != sess.wordlist_id:
        raise HTTPException(status_code=404, detail="Word not found")

    normalized_ans = (answer or "").strip().lower()
    correct = normalized_ans == (word.term or "").strip().lower()
    points = 10 if correct else 0
    att = Attempt(session_id=sess.id, user_id=user.id, word_id=word.id, answer_text=answer, correct=bool(correct), points=points)
    db.add(att)
    db.commit()
    db.refresh(att)

    example = word.example
    if not example and not correct:
        example = try_generate_example(word.term, word.definition) or None

    return {
        "attempt_id": att.id,
        "correct": correct,
        "points_awarded": points,
        "correct_answer": word.term,
        "definition": word.definition,
        "example": example,
    }


@router.get("/sessions/{session_id}/scoreboard")
def scoreboard(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = db.exec(select(Attempt).where(Attempt.session_id == sess.id)).all()
    scores: dict[int, int] = defaultdict(int)
    corrects: dict[int, int] = defaultdict(int)
    totals: dict[int, int] = defaultdict(int)
    for r in rows:
        scores[r.user_id] += r.points
        totals[r.user_id] += 1
        if r.correct:
            corrects[r.user_id] += 1
    return {
        "scores": dict(scores),
        "accuracy": {uid: (corrects[uid] / totals[uid] if totals[uid] else 0.0) for uid in [sess.user_a_id, sess.user_b_id]},
        "totals": dict(totals),
    }


@router.get("/sessions/{session_id}/progress")
def progress(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    # Alias for scoreboard plus last activity
    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = db.exec(select(Attempt).where(Attempt.session_id == sess.id)).all()
    last_by_user: dict[int, datetime | None] = {sess.user_a_id: None, sess.user_b_id: None}
    for r in rows:
        last = last_by_user.get(r.user_id)
        if not last or r.created_at > last:
            last_by_user[r.user_id] = r.created_at
    board = scoreboard(session_id, db=db, user=user)
    board.update({"last_activity": {str(k): (v.isoformat() if v else None) for k, v in last_by_user.items()}})
    return board


@router.get("/sessions/{session_id}/wrongbook")
def wrongbook(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = db.exec(select(Attempt).where(Attempt.session_id == sess.id, Attempt.correct == False)).all()  # noqa: E712
    # Aggregate by word
    wrong_by_word: dict[int, set[int]] = defaultdict(set)
    for r in rows:
        wrong_by_word[r.word_id].add(r.user_id)
    out = []
    for wid, userset in wrong_by_word.items():
        w = db.get(Word, wid)
        if not w:
            continue
        out.append({
            "word_id": w.id,
            "term": w.term,
            "definition": w.definition,
            "example": w.example,
            "wrong_by": list(userset),
        })
    return out
