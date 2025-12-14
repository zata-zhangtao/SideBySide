"""
会话与抽背单词路由模块 (Sessions & Quiz Router Module)

本模块集中提供学习会话（StudySession）与双向抽背练习相关的 API：
This module provides APIs for study sessions and bi‑directional drills:

1. 创建会话（指定词库与好友）(Create session with wordlist and friend)
2. 查询会话详情（参与者与词库摘要）(Get session details: participants and list summary)
3. 抽取下一题（方向 zh2en/en2zh/random，缺释义自动回退）
   Draw next item (direction zh2en/en2zh/random, fallback when definition missing)
4. 提交作答并判分（中→英严格匹配；英→中宽松包含；可补充例句）
   Submit attempt and grade (strict zh→en; lenient en→zh; example enrichment)
5. 积分榜与正确率统计（两位参与者）(Scoreboard and accuracy for both participants)
6. 进度总览（积分统计 + 最近活动时间）(Progress: scoreboard plus last activity)
7. 错题本汇总（按单词聚合答错用户）(Wrongbook aggregated by word and users)

典型场景：两位用户进行异步抽背练习，前端逐题请求“下一题”并提交作答，结合积分/进度与错题本复习。
Typical usage: two users practice asynchronously; the frontend fetches next items and submits answers, while showing scores/progress and reviewing wrong answers.

示例 Examples:

  - 获取题目 Get next item:
    curl -H "Authorization: Bearer <token>" \
      "http://localhost:8000/api/sessions/1/next_word?direction=random"

  - 提交作答 Submit attempt:
    curl -X POST -H "Authorization: Bearer <token>" \
      "http://localhost:8000/api/sessions/1/attempts?word_id=10&answer=ability&direction=zh2en"
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
import json
from sqlmodel import Session, select

from ..core.logging import get_logger
from ..deps import get_current_user, get_db
from ..models import Attempt, StudySession, User, Word, WordList
from ..services.agents import judge_definitions

# Initialize unified logger
_sess_logger = get_logger(__name__)

router = APIRouter()


@router.post("/sessions")
def create_session(
    wordlist_id: int,
    friend_username: str,
    type: str = "async",
    zh2en_ratio: int = 50,
    practice_ratio: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    创建一个新的学习会话（异步），并指定好友为对手。

    当前登录用户需为词库的拥有者，系统将以该词库为题源创建会话，并返回会话基本信息。

    Create a new (asynchronous) study session with a specified friend.

    The current user must own the target wordlist. A session is created using
    that list as the quiz source and basic session info is returned.

    Args:
      wordlist_id (int): 词库 ID，必须属于当前用户；Wordlist ID owned by current user.
      friend_username (str): 好友用户名；Username of the friend to invite.
      type (str): 会话类型，当前仅支持 "async"；Session type, currently "async" only.
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      dict[str, Any]: 包含会话 `id`、`type`、`status`；A dict with `id`, `type`, and `status`.

    Raises:
      HTTPException: 404 当词库不存在/不属于用户或好友不存在；
        404 if the wordlist is missing/not owned by user or the friend is not found.
    """
    wl = db.get(WordList, wordlist_id)
    if not wl or wl.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Wordlist not found or not owned by user")
    friend = db.exec(select(User).where(User.username == friend_username)).first()
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    # sanitize ratios into 0..100
    try:
        zh2en_ratio = int(zh2en_ratio)
    except Exception:
        zh2en_ratio = 50
    if zh2en_ratio < 0:
        zh2en_ratio = 0
    if zh2en_ratio > 100:
        zh2en_ratio = 100

    try:
        practice_ratio = int(practice_ratio)
    except Exception:
        practice_ratio = 100
    if practice_ratio < 0:
        practice_ratio = 0
    if practice_ratio > 100:
        practice_ratio = 100

    # Build practice pool if ratio < 100
    pool_ids: list[int] | None = None
    if practice_ratio < 100:
        rows = db.exec(select(Word).where(Word.list_id == wl.id)).all()
        total = len(rows)
        if total > 0:
            import random
            k = max(1, int(total * practice_ratio / 100)) if practice_ratio > 0 else 0
            if k > 0:
                pool = random.sample(rows, k if k <= total else total)
                pool_ids = [w.id for w in pool]

    sess = StudySession(
        type=type,
        wordlist_id=wl.id,
        created_by=user.id,
        user_a_id=user.id,
        user_b_id=friend.id,
        zh2en_ratio=zh2en_ratio,
        practice_ratio=practice_ratio,
        practice_pool=(json.dumps(pool_ids) if pool_ids is not None else None),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return {
        "id": sess.id,
        "type": sess.type,
        "status": sess.status,
        "zh2en_ratio": sess.zh2en_ratio,
        "practice_ratio": sess.practice_ratio,
        "practice_pool_size": len(pool_ids) if pool_ids is not None else None,
    }


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """
    获取会话详情，包括基础信息、参与者与词库摘要。

    仅会话参与者可访问。常用于进入会话后展示元信息与用户侧边栏。

    Retrieve session details including basic info, participants, and wordlist
    summary. Only participants of the session are authorized.

    Args:
      session_id (int): 会话 ID；Target session ID.
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      dict[str, Any]: 包含 `id`、`type`、`status`、`wordlist` 与 `participants`；
        A dict with `id`, `type`, `status`, `wordlist`, and `participants`.

    Raises:
      HTTPException: 404 当会话不存在或当前用户非参与者；
        404 if the session does not exist or user is not a participant.
    """
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
        "zh2en_ratio": getattr(sess, "zh2en_ratio", 50),
        "practice_ratio": getattr(sess, "practice_ratio", 100),
        "practice_pool_size": (len(json.loads(sess.practice_pool)) if getattr(sess, "practice_pool", None) else None),
        "wordlist": {"id": wl.id, "name": wl.name} if wl else None,
        "participants": [
            {"id": sess.user_a_id, "username": ua.username if ua else str(sess.user_a_id)},
            {"id": sess.user_b_id, "username": ub.username if ub else str(sess.user_b_id)},
        ],
    }


@router.get("/sessions/{session_id}/next_word")
def next_word(
    session_id: int,
    direction: str | None = None,  # 'zh2en' | 'en2zh' | None
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    抽取下一题目，支持方向：中→英（zh2en）与英→中（en2zh）。

    若未指定方向或设为 random，则系统在两个方向间随机选择；当英→中缺少释义时将自动回退为中→英，确保题目可答。

    Draw the next quiz item with direction support: zh→en (definition→term)
    and en→zh (term→definition). If `direction` is omitted or `random`, a
    random direction is chosen; when en→zh lacks a definition, it falls back to
    zh→en to keep the item answerable.

    工作流 Workflow:
      1) 校验权限与会话有效性；2) 在会话词库中随机抽取一个单词；3) 判定/修正题目方向；4) 返回题目与方向。

    Args:
      session_id (int): 会话 ID；Target session ID.
      direction (str | None): 题目方向，可为 "zh2en"、"en2zh"、"random" 或留空；
        Quiz direction: "zh2en", "en2zh", "random", or None.
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      dict[str, Any]: 包含 `word_id`、`term`、`definition`、`direction`；
        A dict with `word_id`, `term`, `definition`, and `direction`.

    Raises:
      HTTPException: 404 当会话不存在或无权限；400 当词库为空；
        404 if the session is missing or unauthorized; 400 if the wordlist is empty.
    """
    import random

    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    # Fetch words in the list and apply practice pool if present
    words = db.exec(select(Word).where(Word.list_id == sess.wordlist_id)).all()
    pool_ids: list[int] | None = None
    if getattr(sess, "practice_pool", None):
        try:
            pool_ids = [int(x) for x in json.loads(sess.practice_pool)]
        except Exception:
            pool_ids = None
    if pool_ids is not None:
        words = [w for w in words if w.id in set(pool_ids)]
    if not words:
        raise HTTPException(status_code=400, detail="No words in the list")
    # Simple random selection; could exclude recently correct items in future
    w = random.choice(words)

    # Decide direction: use session ratio if not specified; fallback when missing data
    chosen = direction
    if not chosen or chosen == "random":
        ratio = getattr(sess, "zh2en_ratio", 50)
        try:
            ratio = int(ratio)
        except Exception:
            ratio = 50
        ratio = max(0, min(100, ratio))
        roll = random.randint(1, 100)
        chosen = "zh2en" if roll <= ratio else "en2zh"
    if chosen == "en2zh" and not ((w.definition or "").strip()):
        # If no definition, fallback to zh2en
        chosen = "zh2en"

    return {"word_id": w.id, "term": w.term, "definition": w.definition, "direction": chosen}


@router.post("/sessions/{session_id}/attempts")
def submit_attempt(
    session_id: int,
    word_id: int,
    answer: str,
    direction: str | None = None,  # 'zh2en' | 'en2zh'
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    提交一次作答并判分，支持中→英与英→中两种方向。

    中→英采用严格等价（统一大小写/空白/标点后比较）；英→中在去除空白/中英标点后，除严格等价外还接受“包含”匹配以容忍轻微差异。

    Submit an answer and grade it for either zh→en or en→zh.

    For zh→en, grading requires strict equality after normalization (lowercase,
    whitespace/punctuation removed). For en→zh, after normalization it accepts
    exact match or containment to allow minor phrasing variance.

    工作流 Workflow:
      1) 校验会话/单词与权限；2) 归一化答案及期望；3) 判定正误与积分；4) 必要时补充例句；5) 返回作答结果。

    Args:
      session_id (int): 会话 ID；Target session ID.
      word_id (int): 单词 ID，需属于该会话的词库；Word ID that belongs to the session's list.
      answer (str): 用户答案；User's answer text.
      direction (str | None): 作答方向 "zh2en" 或 "en2zh"（留空默认中→英）；
        Answer direction: "zh2en" or "en2zh" (defaults to zh2en if None).
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      dict[str, Any]:
        - `attempt_id`：作答记录 ID；Attempt ID.
        - `correct`：是否正确；Whether the answer is correct.
        - `points_awarded`：得分，正确 10 分；Points awarded, 10 when correct.
        - `correct_answer`：依据方向返回正确项（英→中返回中文释义，中→英返回英文单词）；
          The correct item per direction (definition for en→zh, term for zh→en).
        - `definition`：该词中文释义；Word definition (Chinese) if available.
        - `example`：例句（若无且回答错误，可能由 LLM 生成）；Example sentence if present or generated.

    Raises:
      HTTPException: 404 当会话不存在/无权限或单词不在会话词库中；
        404 if session unauthorized/missing or word does not belong to the list.
    """
    sess = db.get(StudySession, session_id)
    if not sess or user.id not in [sess.user_a_id, sess.user_b_id]:
        raise HTTPException(status_code=404, detail="Session not found")
    word = db.get(Word, word_id)
    if not word or word.list_id != sess.wordlist_id:
        raise HTTPException(status_code=404, detail="Word not found")

    def _norm_generic(s: str) -> str:
        # lowercase, strip spaces, remove common punctuations (both en/zh basic)
        import re

        s2 = (s or "").lower()
        # remove whitespace (incl. full-width)
        s2 = re.sub(r"[\s\u3000]+", "", s2)
        # remove basic punctuation (ascii + common zh)
        s2 = re.sub(r"[\.,;:!\?\-_'\"\(\)\[\]{}，。！？；、（）【】《》“”]+", "", s2)
        return s2

    # Default to zh2en for backward compatibility if not provided
    dir_eff = (direction or "zh2en").lower()
    normalized_ans = _norm_generic(answer or "")

    judge_detail = None  # will always attach later with a default
    if dir_eff == "en2zh":
        expected = _norm_generic(word.definition or "")
        # allow minor variance: treat as correct if equal or one contains the other
        correct = bool(expected) and (
            normalized_ans == expected or (
                normalized_ans and (normalized_ans in expected or expected in normalized_ans)
            )
        )
        # Optional semantic fallback via LLM
        def _truthy(name: str) -> bool:
            v = (os.getenv(name) or "").strip().lower()
            return v in ("1", "true", "yes", "on")

        use_llm = _truthy("USE_LLM_JUDGE_EN2ZH")
        has_ref = bool((word.definition or "").strip())
        if correct:
            judge_detail = {"used": False, "reason": "rule_based_correct"}
        elif not has_ref:
            judge_detail = {"used": False, "reason": "no_reference_definition"}
        elif not use_llm:
            judge_detail = {"used": False, "reason": "disabled"}
        else:
            try:
                strictness = (os.getenv("LLM_JUDGE_STRICTNESS") or "medium").strip().lower()
                treat_partial = _truthy("LLM_JUDGE_TREAT_PARTIAL_AS_CORRECT")
                items = [{"term": word.term, "definition": word.definition or ""}]
                answers = {word.term: answer or ""}
                judged = judge_definitions(items, answers, strictness=strictness, language="zh")
                if judged:
                    r0 = judged[0]
                    verdict = str(r0.get("verdict") or "").lower()
                    is_match = bool(r0.get("is_match"))
                    if is_match or verdict == "correct" or (treat_partial and verdict == "partial"):
                        correct = True
                    judge_detail = {
                        "used": True,
                        "strictness": strictness,
                        "verdict": verdict,
                        "score": r0.get("score"),
                        "reason": r0.get("reason"),
                        "missing_keywords": r0.get("missing_keywords"),
                    }
                    try:
                        _sess_logger.info(
                            f"LLM judge en2zh word_id={word.id} accepted={correct} verdict={verdict} score={r0.get('score')}"
                        )
                    except Exception:
                        pass
            except Exception:
                judge_detail = {"used": False, "error": "llm_judge_failed"}
                try:
                    _sess_logger.warning("LLM judge failed; using rule-based result")
                except Exception:
                    pass
    else:  # zh2en
        expected = _norm_generic(word.term or "")
        correct = bool(expected) and (normalized_ans == expected)
        # No semantic judge in this direction by design
        judge_detail = {"used": False, "reason": "direction_not_en2zh"}
    points = 10 if correct else 0
    att = Attempt(session_id=sess.id, user_id=user.id, word_id=word.id, answer_text=answer, correct=bool(correct), points=points)
    db.add(att)
    db.commit()
    db.refresh(att)

    example = word.example

    # In en2zh mode, reveal correct Chinese definition; otherwise show term
    out = {
        "attempt_id": att.id,
        "correct": correct,
        "points_awarded": points,
        "correct_answer": (word.definition if dir_eff == "en2zh" else word.term),
        "definition": word.definition,
        "example": example,
    }
    # Always attach judge_detail for client visibility
    try:
        out["judge_detail"] = judge_detail or {"used": False, "reason": "unknown"}
    except Exception:
        pass
    return out


@router.get("/sessions/{session_id}/scoreboard")
def scoreboard(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    """
    获取会话积分榜与正确率统计。

    统计两位参与者的累计得分、答题总数与正确率，常用于练习过程中的侧边栏或结束后的总结页。

    Get the session scoreboard and accuracy stats for both participants.

    It aggregates total points, attempts, and accuracy per user, useful for
    in‑session sidebars and post‑session summaries.

    Args:
      session_id (int): 会话 ID；Target session ID.
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      dict[str, Any]:
        - `scores`：{user_id: points}；Total points per user.
        - `accuracy`：{user_id: 正确率(0~1)}；Accuracy ratio per user.
        - `totals`：{user_id: 答题总数}；Total attempts per user.

    Raises:
      HTTPException: 404 当会话不存在或无权限；
        404 if the session is missing or user is unauthorized.
    """
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
    """
    获取积分榜并附带最近活动时间，作为“进度”概要。

    在积分统计的基础上，补充两位参与者最近一次作答时间（ISO 字符串），可用于页面上报与继续练习提示。

    Get the scoreboard plus last activity timestamps as a progress summary.

    It augments scoreboard data with the most recent attempt time per user
    (ISO string), useful for reporting and prompting users to resume.

    Args:
      session_id (int): 会话 ID；Target session ID.
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      dict[str, Any]: `scoreboard` 字段合集并加入 `last_activity` 映射；
        The scoreboard dict extended with `last_activity` mapping.

    Raises:
      HTTPException: 404 当会话不存在或无权限；
        404 if the session is missing or user is unauthorized.
    """
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
    """
    获取会话的错题本（按单词聚合）。

    返回在本会话中答错过的单词列表及其被哪些用户答错，常用于针对性复习与回顾。

    Get the session wrongbook aggregated by word.

    Returns words that were answered incorrectly in this session, along with the
    user IDs who missed them. Useful for targeted reviews.

    Args:
      session_id (int): 会话 ID；Target session ID.
      db (Session): 数据库会话依赖；Database session dependency.
      user (User): 当前认证用户依赖；Current authenticated user dependency.

    Returns:
      list[dict[str, Any]]: 每项包含 `word_id`、`term`、`definition`、`example`、`wrong_by`；
        A list of dicts with `word_id`, `term`, `definition`, `example`, `wrong_by`.

    Raises:
      HTTPException: 404 当会话不存在或无权限；
        404 if the session is missing or user is unauthorized.
    """
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
