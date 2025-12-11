from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import User, Word, WordList
from ..utils.parser import sniff_and_parse


router = APIRouter()


@router.post("/wordlists")
def create_wordlist(
    name: str = Form(...),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    wl = WordList(name=name, description=description, owner_id=user.id)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return {"id": wl.id, "name": wl.name, "description": wl.description}


@router.get("/wordlists")
def list_wordlists(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    rows = db.exec(select(WordList).where(WordList.owner_id == user.id)).all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.post("/wordlists/{list_id}/upload")
async def upload_words(
    list_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    wl = db.get(WordList, list_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found")

    data = await file.read()
    rows = sniff_and_parse(data, file.filename)
    created = 0
    for r in rows:
        term = (r.get("term") or "").strip()
        if not term:
            continue
        definition = (r.get("definition") or None) or None
        example = (r.get("example") or None) or None
        w = Word(list_id=wl.id, term=term, definition=definition, example=example)
        db.add(w)
        created += 1
    db.commit()
    return {"message": f"Imported {created} words"}


@router.get("/wordlists/{list_id}/words")
def get_words(list_id: int, limit: int = 100, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    wl = db.get(WordList, list_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found")
    rows = db.exec(select(Word).where(Word.list_id == wl.id).offset(offset).limit(limit)).all()
    return [{"id": w.id, "term": w.term, "definition": w.definition, "example": w.example} for w in rows]

