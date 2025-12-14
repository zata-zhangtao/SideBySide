"""
单词本路由模块 (Wordlist Router Module)

本模块提供单词本管理的所有 API 端点，包括：
This module provides all API endpoints for wordlist management, including:

1. 创建和查询单词本 (Create and query wordlists)
2. 上传json/csv文件导入单词 (Upload json/csv files to import words)
3. 从图片提取单词（使用 LLM） (Extract words from images using LLM)
4. 预览功能（在保存前查看提取结果） (Preview functionality before saving)
5. 批量保存单词 (Batch save words)
6. 批量图片处理（Batch image processing）
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_db
from ..models import User, Word, WordList
from ..utils.parser import sniff_and_parse
from ..services.agents import extract_vocabulary_from_image


router = APIRouter()


# 内存存储批处理任务状态 (In-memory storage for batch processing task status)
# 生产环境应该使用 Redis 等持久化存储
# For production, use Redis or other persistent storage
batch_tasks: Dict[str, Dict[str, Any]] = {}


class WordInput(BaseModel):
    """
    单词输入模型 (Word Input Model)

    用于批量保存单词时的输入数据格式
    Used for input data format when batch saving words
    """
    term: str  # 单词/术语 (term/vocabulary)
    definition: str | None = None  # 释义/定义 (definition)
    example: str | None = None  # 例句 (example sentence)


@router.post("/wordlists")
def create_wordlist(
    name: str = Form(...),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    创建新的单词本 (Create a new wordlist)

    接收单词本名称和描述，创建一个空的单词本
    Accepts wordlist name and description, creates an empty wordlist

    Args:
        name: 单词本名称 (wordlist name)
        description: 单词本描述（可选） (wordlist description, optional)

    Returns:
        包含 id, name, description 的字典 (dict with id, name, description)
    """
    wl = WordList(name=name, description=description, owner_id=user.id)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return {"id": wl.id, "name": wl.name, "description": wl.description}


@router.get("/wordlists")
def list_wordlists(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    """
    获取当前用户的所有单词本 (Get all wordlists for current user)

    返回当前登录用户创建的所有单词本列表
    Returns a list of all wordlists created by the current logged-in user

    Returns:
        单词本列表，每项包含 id, name, description
        List of wordlists, each containing id, name, description
    """
    rows = db.exec(select(WordList).where(WordList.owner_id == user.id)).all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.post("/wordlists/{list_id}/upload")
async def upload_words(
    list_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    上传文件导入单词到指定单词本 (Upload file to import words to specified wordlist)

    支持多种文件格式（CSV, Excel, JSON 等），自动解析并导入单词
    Supports multiple file formats (CSV, Excel, JSON, etc.), automatically parses and imports words

    Args:
        list_id: 单词本 ID (wordlist ID)
        file: 上传的文件 (uploaded file)

    Returns:
        包含导入数量的消息 (message with import count)
    """
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
    """
    从图片创建单词本（使用 LLM 提取单词）
    Create a wordlist by extracting vocabulary from an uploaded image via LLM

    使用 LangGraph 多模态 AI 代理从图片中自动识别和提取单词、释义和例句
    Uses LangGraph multimodal AI agent to automatically recognize and extract words, definitions, and examples from images

    工作流程 (Workflow):
    1. 创建新的单词本 (Create new wordlist)
    2. 使用视觉模型分析图片提取单词 (Use vision model to analyze image and extract words)
    3. 使用文本模型补充释义和例句 (Use text model to supplement definitions and examples)
    4. 保存到数据库 (Save to database)

    需要配置 llm_api_loader (Requires llm_api_loader to be configured)
    详见 backend/README.md (See backend/README.md)

    Args:
        name: 单词本名称 (wordlist name)
        description: 单词本描述（可选）(wordlist description, optional)
        file: 上传的图片文件 (uploaded image file)

    Returns:
        包含单词本信息和提取数量的字典
        Dict containing wordlist info and extraction count
    """
    # Create list first
    wl = WordList(name=name, description=description, owner_id=user.id)
    db.add(wl)
    db.commit()
    db.refresh(wl)

    # Run extraction
    data = await file.read()
    try:
        rows = extract_vocabulary_from_image(data)
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
    """
    获取指定单词本中的单词列表 (Get words list from specified wordlist)

    支持分页查询单词本中的所有单词
    Supports paginated query of all words in the wordlist

    Args:
        list_id: 单词本 ID (wordlist ID)
        limit: 每页数量，默认 100 (items per page, default 100)
        offset: 偏移量，默认 0 (offset, default 0)

    Returns:
        单词列表，每项包含 id, term, definition, example
        List of words, each containing id, term, definition, example
    """
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
    """
    预览从图片提取的单词（不保存）(Preview words extracted from image without saving)

    使用 LLM 从图片中提取单词但不保存到数据库，用于预览功能
    Uses LLM to extract words from image but doesn't save to database, for preview functionality

    使用场景：用户上传图片后，可以先预览提取结果，确认后再选择保存到哪个单词本
    Use case: After user uploads image, they can preview extraction results before deciding which wordlist to save to

    需要配置 llm_api_loader (Requires llm_api_loader to be configured)
    详见 backend/README.md (See backend/README.md)

    Args:
        file: 上传的图片文件 (uploaded image file)

    Returns:
        提取的单词列表（未保存）List of extracted words (not saved)
    """
    data = await file.read()
    try:
        rows = extract_vocabulary_from_image(data)
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
    """
    预览文件中的单词（不保存）(Preview words from file without saving)

    从上传的文件中解析单词但不保存到数据库，用于预览功能
    Parses words from uploaded file but doesn't save to database, for preview functionality

    使用场景：用户上传文件后，可以先预览解析结果，确认后再保存
    Use case: After user uploads file, they can preview parsed results before saving

    Args:
        list_id: 单词本 ID（用于验证权限）(wordlist ID, for permission validation)
        file: 上传的文件（CSV, Excel, JSON 等）(uploaded file: CSV, Excel, JSON, etc.)

    Returns:
        解析的单词列表（未保存）List of parsed words (not saved)
    """
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
    """
    批量保存单词到指定单词本 (Batch save words to specified wordlist)

    接收一个单词列表（通常来自预览功能），批量保存到指定的单词本
    Accepts a list of words (usually from preview functionality), batch saves to specified wordlist

    使用场景：配合预览功能使用，用户确认预览结果后调用此接口保存
    Use case: Used with preview functionality, called after user confirms preview results

    Args:
        list_id: 单词本 ID (wordlist ID)
        words: 单词列表，每项包含 term, definition, example
               List of words, each containing term, definition, example

    Returns:
        包含保存数量的消息 (message with save count)
    """
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


async def _process_single_image(file_data: bytes, filename: str, index: int, task_id: str) -> Dict[str, Any]:
    """
    处理单张图片的辅助函数 (Helper function to process a single image)

    Args:
        file_data: 图片字节数据 (image byte data)
        filename: 文件名 (filename)
        index: 图片索引 (image index)
        task_id: 任务ID (task ID)

    Returns:
        处理结果字典 (processing result dict)
    """
    try:
        # 更新任务状态
        batch_tasks[task_id]["current_image"] = filename
        batch_tasks[task_id]["current_index"] = index

        # 提取词汇
        rows = await asyncio.to_thread(extract_vocabulary_from_image, file_data)

        # 处理结果
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

        # 更新完成状态
        batch_tasks[task_id]["completed"] += 1

        return {
            "filename": filename,
            "index": index,
            "status": "success",
            "words": result,
            "count": len(result)
        }
    except Exception as e:
        batch_tasks[task_id]["completed"] += 1
        batch_tasks[task_id]["errors"] += 1
        return {
            "filename": filename,
            "index": index,
            "status": "error",
            "error": str(e),
            "words": [],
            "count": 0
        }


@router.post("/wordlists/batch_preview_from_images")
async def batch_preview_from_images(
    files: List[UploadFile] = File(...),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    批量预览从多张图片提取的单词（不保存）(Batch preview words from multiple images without saving)

    支持同时处理多张图片，使用并行处理提高速度
    Supports processing multiple images simultaneously with parallel processing for better performance

    返回任务ID，可通过 /batch_status/{task_id} 查询处理进度
    Returns task ID, can query processing progress via /batch_status/{task_id}

    Args:
        files: 上传的图片文件列表 (list of uploaded image files)

    Returns:
        任务ID和初始状态 (task ID and initial status)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 images allowed per batch")

    # 生成任务ID
    task_id = str(uuid.uuid4())

    # 读取所有文件数据（在请求上下文中，文件仍然打开）
    # Read all file data while in request context (files are still open)
    file_data_list = []
    for file in files:
        file_data = await file.read()
        file_data_list.append((file_data, file.filename or f"image_{len(file_data_list)}"))

    # 初始化任务状态
    batch_tasks[task_id] = {
        "task_id": task_id,
        "total": len(files),
        "completed": 0,
        "errors": 0,
        "current_image": None,
        "current_index": 0,
        "status": "processing",
        "results": [],
        "started_at": datetime.now().isoformat(),
        "user_id": user.id
    }

    # 异步处理所有图片（传递已读取的字节数据）
    # Process all images asynchronously (pass pre-read byte data)
    asyncio.create_task(_process_batch(task_id, file_data_list))

    return {
        "task_id": task_id,
        "total": len(files),
        "status": "processing",
        "message": f"Started processing {len(files)} images"
    }


async def _process_batch(task_id: str, file_data_list: List[tuple[bytes, str]]) -> None:
    """
    后台处理批量图片的任务 (Background task to process batch of images)

    使用信号量限制并发数量，避免过载
    Uses semaphore to limit concurrency and avoid overload

    Args:
        task_id: 任务ID (task ID)
        file_data_list: 图片数据列表 [(bytes, filename), ...] (list of image data tuples)
    """
    # 限制并发数量（最多3个并发请求）
    semaphore = asyncio.Semaphore(3)

    async def process_with_semaphore(file_data: bytes, filename: str, index: int):
        async with semaphore:
            return await _process_single_image(file_data, filename, index, task_id)

    # 并行处理所有图片
    tasks = [process_with_semaphore(file_data, filename, i) for i, (file_data, filename) in enumerate(file_data_list)]
    results = await asyncio.gather(*tasks)

    # 更新最终状态
    batch_tasks[task_id]["results"] = results
    batch_tasks[task_id]["status"] = "completed"
    batch_tasks[task_id]["completed_at"] = datetime.now().isoformat()


@router.get("/wordlists/batch_status/{task_id}")
async def get_batch_status(
    task_id: str,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    查询批处理任务状态 (Query batch processing task status)

    返回任务的实时进度和结果
    Returns real-time progress and results of the task

    Args:
        task_id: 任务ID (task ID)

    Returns:
        任务状态信息 (task status information)
    """
    if task_id not in batch_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = batch_tasks[task_id]

    # 验证用户权限
    if task["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return task
