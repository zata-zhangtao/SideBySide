from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class UserBase(SQLModel):
    username: str = Field(index=True)
    email: Optional[str] = Field(default=None, index=True)


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str


class Friendship(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    friend_id: int = Field(foreign_key="user.id")


class WordListBase(SQLModel):
    name: str
    description: Optional[str] = None


class WordList(WordListBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id")


class Word(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    list_id: int = Field(foreign_key="wordlist.id")
    term: str = Field(index=True)
    definition: Optional[str] = None
    example: Optional[str] = None


class SessionBase(SQLModel):
    type: str = Field(default="async")  # async/sync
    status: str = Field(default="active")  # active/completed


class StudySession(SessionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wordlist_id: int = Field(foreign_key="wordlist.id")
    created_by: int = Field(foreign_key="user.id")
    user_a_id: int = Field(foreign_key="user.id")
    user_b_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Percentage (0-100) of zh->en questions when direction is random
    zh2en_ratio: int = Field(default=50)


class Attempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="studysession.id")
    user_id: int = Field(foreign_key="user.id")
    word_id: int = Field(foreign_key="word.id")
    answer_text: Optional[str] = None
    correct: bool = Field(default=False)
    points: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
