from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import User, Word, WordList
from ..utils.parser import sniff_and_parse
from ..services.vision_to_words import extract_words_from_image


router = APIRouter()


class WordInput(BaseModel):
    term: str
    definition: str | None = None
    example: str | None = None


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


@router.post("/wordlists/from_image")
async def create_from_image(
    name: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a wordlist by extracting vocabulary from an uploaded image via LLM.

    Requires llm_api_loader to be configured (see repo llm_api_loader/README.md).
    """
    # Create list first
    wl = WordList(name=name, description=description, owner_id=user.id)
    db.add(wl)
    db.commit()
    db.refresh(wl)

    # Run extraction
    data = await file.read()
    try:
        rows = extract_words_from_image(data)
    except ImportError:
        raise HTTPException(status_code=400, detail="LLM provider not configured. Install provider SDK and set env.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract words: {e}")

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

    return {"id": wl.id, "name": wl.name, "message": f"Extracted {created} items from image"}


@router.get("/wordlists/{list_id}/words")
def get_words(list_id: int, limit: int = 100, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    wl = db.get(WordList, list_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found")
    rows = db.exec(select(Word).where(Word.list_id == wl.id).offset(offset).limit(limit)).all()
    return [{"id": w.id, "term": w.term, "definition": w.definition, "example": w.example} for w in rows]


@router.post("/wordlists/preview_from_image")
async def preview_from_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Preview words extracted from an image without saving them.

    Requires llm_api_loader to be configured (see repo llm_api_loader/README.md).
    """
    data = await file.read()
    try:
        rows = extract_words_from_image(data)
    except ImportError:
        raise HTTPException(status_code=400, detail="LLM provider not configured. Install provider SDK and set env.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract words: {e}")

    # Return extracted words without saving
    result = []
    for r in rows:
        term = (r.get("term") or "").strip()
        if not term:
            continue
        result.append({
            "term": term,
            "definition": (r.get("definition") or None) or None,
            "example": (r.get("example") or None) or None,
        })

    return result


@router.post("/wordlists/{list_id}/preview_upload")
async def preview_upload(
    list_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Preview words from a file without saving them."""
    wl = db.get(WordList, list_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found")

    data = await file.read()
    rows = sniff_and_parse(data, file.filename)

    # Return parsed words without saving
    result = []
    for r in rows:
        term = (r.get("term") or "").strip()
        if not term:
            continue
        result.append({
            "term": term,
            "definition": (r.get("definition") or None) or None,
            "example": (r.get("example") or None) or None,
        })

    return result


@router.post("/wordlists/{list_id}/save_words")
async def save_words(
    list_id: int,
    words: List[WordInput] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Save a batch of words to a wordlist."""
    wl = db.get(WordList, list_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found")

    created = 0
    for word_input in words:
        term = word_input.term.strip()
        if not term:
            continue
        w = Word(
            list_id=wl.id,
            term=term,
            definition=word_input.definition,
            example=word_input.example
        )
        db.add(w)
        created += 1

    db.commit()
    return {"message": f"Saved {created} words", "count": created}
