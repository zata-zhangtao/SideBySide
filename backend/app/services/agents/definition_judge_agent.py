"""
Definition Similarity Judge Agent

用途 (Purpose):
- 判断用户给出的释义是否与单词本中的标准释义语义相近（而非逐字相同）
- 支持按“严格度”不同给出打分与判定（correct/partial/incorrect）
- 采用 DashScope 文本模型，一次批量评估多条记录，输出严格 JSON

输入 (Input):
- word_items: List[{ term: str, definition: str }] 作为参考答案
- user_answers: Dict[str, str] 或 List[{ term: str, answer: str }]
- strictness: "low" | "medium" | "high" (默认 medium)
- language: 输出语言，默认中文 "zh"

输出 (Output):
- List[{ term, reference_definition, user_answer, is_match, score, verdict, reason, missing_keywords }]

备注 (Notes):
- 模型名称从环境变量 TEXT_MODEL 读取，默认 qwen3-max-preview
- API Key 从环境变量 DASHSCOPE_API_KEY 读取
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, TypedDict

import dashscope

from app.core.logging import get_logger

# Optional LangSmith tracing (best-effort). Enable with env:
#   LANGSMITH_ENABLED=1 and provide LANGSMITH_API_KEY or LANGCHAIN_API_KEY
#   Optionally LANGCHAIN_TRACING_V2=1 and LANGCHAIN_PROJECT
try:  # lazy import to avoid hard dependency
    from langsmith.run_helpers import trace as _ls_trace  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _ls_trace = None  # type: ignore

# Initialize unified logger
_logger = get_logger(__name__)



TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen3-max-preview")


class JudgeResult(TypedDict, total=False):
    term: str
    reference_definition: str | None
    user_answer: str | None
    is_match: bool
    score: float
    verdict: str
    reason: str
    missing_keywords: List[str]


def _ensure_api_key() -> None:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")
    try:
        dashscope.api_key = api_key
    except Exception:
        # 某些环境无需显式设置属性
        pass


def _extract_text_from_response(response: Any) -> str:
    """与 images2words_agent 中逻辑一致的文本提取器（简化版）。"""
    for attr in ("output_text", "text", "message", "content"):
        try:
            v = getattr(response, attr, None)
            if isinstance(v, str) and v.strip():
                return v
        except Exception:
            pass

    try:
        if hasattr(response, "output"):
            output = response.output
            text = getattr(output, "text", None)
            if isinstance(text, str) and text.strip():
                return text
            choices = getattr(output, "choices", None)
            if choices:
                c0 = choices[0]
                msg = getattr(c0, "message", None)
                if msg is not None:
                    content = getattr(msg, "content", None)
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and isinstance(item.get("text"), str):
                                t = item["text"].strip()
                                if t:
                                    return t
                    elif isinstance(content, str) and content.strip():
                        return content
    except Exception:
        pass

    try:
        if isinstance(response, dict):
            out = response.get("output") or {}
            if isinstance(out, dict):
                if isinstance(out.get("text"), str):
                    return str(out["text"]).strip()
                if isinstance(out.get("content"), str):
                    return str(out["content"]).strip()
                if out.get("choices"):
                    c0 = out["choices"][0]
                    if isinstance(c0, dict):
                        message = c0.get("message") or {}
                        content = message.get("content")
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and isinstance(item.get("text"), str):
                                    t = item["text"].strip()
                                    if t:
                                        return t
                        elif isinstance(content, str) and content.strip():
                            return content
            if response.get("choices"):
                c0 = response["choices"][0]
                if isinstance(c0, dict):
                    message = c0.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
    except Exception:
        pass

    return str(response)


def _normalize_inputs(
    word_items: List[Dict[str, Any]],
    user_answers: Dict[str, str] | List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """规范化输入为 [{ term, reference_definition, user_answer }]。"""
    # 建立 term -> reference_definition
    ref: Dict[str, str] = {}
    for item in word_items or []:
        term = str((item.get("term") or "")).strip()
        if not term:
            continue
        definition = item.get("definition")
        if isinstance(definition, str):
            ref[term] = definition.strip()
        elif definition is None:
            ref[term] = ""
        else:
            ref[term] = str(definition)

    # 解析 user_answers
    ans: Dict[str, str] = {}
    if isinstance(user_answers, dict):
        for k, v in user_answers.items():
            term = str(k).strip()
            if not term:
                continue
            ans[term] = (v or "").strip() if isinstance(v, str) else str(v)
    else:
        for it in user_answers or []:
            term = str((it.get("term") or "")).strip()
            if not term:
                continue
            answer = it.get("answer")
            ans[term] = (answer or "").strip() if isinstance(answer, str) else str(answer)

    # 合并为评估列表
    merged: List[Dict[str, str]] = []
    for term, ref_def in ref.items():
        merged.append({
            "term": term,
            "reference_definition": ref_def,
            "user_answer": ans.get(term, ""),
        })
    return merged


def _build_prompt(items: List[Dict[str, str]], strictness: str = "medium", language: str = "zh") -> str:
    # 评分与判定标准（中文）
    strictness = (strictness or "medium").lower()
    if strictness not in ("low", "medium", "high"):
        strictness = "medium"

    lang = (language or "zh").lower()
    zh = lang.startswith("zh")

    rules_cn = f"""
你是一个严格而公正的词义评审助手，需要判断“用户释义”与“参考释义”是否语义等价或足够接近：

总体规则：
1) 接受同义表达、同义词、释义顺序不同、措辞不同，但语义一致算正确。
2) 只描述词性或过于笼统（如“好/坏/东西/人”）不给满分；若覆盖核心含义但细节略有缺失，可判为部分正确。
3) 如果用户释义与参考释义的主要语义不一致或指向错误概念，判为错误。
4) 若参考释义包含多个关键点，需覆盖关键点的主干语义；缺少关键点则降低分数。
5) 忽略标点、大小写和轻微的表达差异。

严格度：{strictness}
- low: 更宽松，合理近义和概括都可判正确，缺少非关键细节也可正确。
- medium: 平衡；需要覆盖核心语义，缺失关键点判部分正确。
- high: 严格；需要覆盖主要关键点，较多遗漏或泛化判部分正确或错误。

输出要求：仅输出 JSON 数组，不要任何说明或代码块。每个元素包含固定键：
- term: 单词
- reference_definition: 参考释义
- user_answer: 用户释义
- is_match: 布尔值（是否判定为语义匹配）
- score: 0~1 之间的小数（建议 0, 0.5, 1 三档，必要时可用 0.25/0.75）
- verdict: "correct" | "partial" | "incorrect"
- reason: 简要中文理由（{ '中文' if zh else 'in Chinese' }）
- missing_keywords: 若为 partial/incorrect，给出缺失的关键点词语列表；否则可为空数组
""".strip()

    preview = json.dumps(items, ensure_ascii=False, indent=2)
    return (
        rules_cn
        + "\n\n待评估数据(请原样按顺序评估)：\n"
        + preview
        + "\n\n请仅输出JSON数组，不要额外文本。"
    )


def judge_definitions(
    word_items: List[Dict[str, Any]],
    user_answers: Dict[str, str] | List[Dict[str, Any]],
    *,
    strictness: str = "medium",
    language: str = "zh",
) -> List[JudgeResult]:
    """
    批量判定用户释义与参考释义是否语义一致或接近（宽松/中等/严格）。

    返回每条 term 的打分与结论，格式稳定，便于前端渲染。
    """
    _ensure_api_key()
    items = _normalize_inputs(word_items, user_answers)
    if not items:
        return []

    prompt = _build_prompt(items, strictness=strictness, language=language)
    _logger.info(f"[judge] items={len(items)} strictness={strictness} lang={language}")
    if _logger.isEnabledFor(logging.DEBUG):
        _logger.debug(f"[judge] prompt preview (first 600 chars):\n{prompt[:600]}")

    # Determine if LangSmith tracing is enabled via env flags
    def _truthy(name: str) -> bool:
        v = (os.getenv(name) or "").strip().lower()
        return v in ("1", "true", "yes", "on")

    use_ls = _truthy("LANGSMITH_ENABLED") or _truthy("LANGCHAIN_TRACING_V2")

    try:
        # Optional tracing context
        _trace_cm = (_ls_trace("DefinitionJudge.batch", inputs={
            "strictness": strictness,
            "count": len(items),
        })) if (use_ls and _ls_trace is not None) else None

        if _trace_cm is not None:
            _logger.debug("[judge] LangSmith tracing enabled")
        ctx = _trace_cm if _trace_cm is not None else nullcontext()  # type: ignore
        with ctx as _run:
            response = dashscope.Generation.call(
                model=TEXT_MODEL,
                prompt=prompt,
            )

        text = _extract_text_from_response(response).strip()
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(f"[judge] raw text head: {text[:300]}")
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.MULTILINE)
            text = re.sub(r"```$", "", text, flags=re.MULTILINE)
        text = text.strip()

        data: List[Dict[str, Any]] = []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                data = parsed
        except json.JSONDecodeError:
            m = re.search(r"\[[\s\S]*\]", text)
            if m:
                try:
                    data = json.loads(m.group())
                except json.JSONDecodeError:
                    data = []

        results: List[JudgeResult] = []
        for it in data:
            if not isinstance(it, dict):
                continue
            term = str((it.get("term") or "")).strip()
            ref_def = (it.get("reference_definition") or "") if isinstance(it.get("reference_definition"), str) else str(it.get("reference_definition", ""))
            ans = (it.get("user_answer") or "") if isinstance(it.get("user_answer"), str) else str(it.get("user_answer", ""))
            is_match = bool(it.get("is_match"))
            verdict = str((it.get("verdict") or "")).strip() or ("correct" if is_match else "incorrect")
            try:
                score_val = float(it.get("score", 1.0 if is_match else 0.0))
            except Exception:
                score_val = 1.0 if is_match else 0.0
            reason = str((it.get("reason") or "")).strip()
            mk = it.get("missing_keywords")
            if isinstance(mk, list):
                missing_keywords = [str(x) for x in mk]
            else:
                missing_keywords = []

            if term:
                results.append(
                    JudgeResult(
                        term=term,
                        reference_definition=ref_def,
                        user_answer=ans,
                        is_match=is_match,
                        score=score_val,
                        verdict=verdict,
                        reason=reason,
                        missing_keywords=missing_keywords,
                    )
                )

        # 若模型返回为空，构造一个保底结果（全部 incorrect）
        if not results:
            for it in items:
                results.append(
                    JudgeResult(
                        term=it.get("term", ""),
                        reference_definition=it.get("reference_definition"),
                        user_answer=it.get("user_answer"),
                        is_match=False,
                        score=0.0,
                        verdict="incorrect",
                        reason="无法解析模型输出，默认判定为不匹配",
                        missing_keywords=[],
                    )
                )

        # Log summary
        try:
            preview = [
                {"term": r.get("term"), "verdict": r.get("verdict"), "score": r.get("score")}
                for r in results[:5]
            ]
            _logger.info(f"[judge] parsed {len(results)} results; preview: {preview}")
        except Exception:
            pass

        return results
    except Exception as e:
        # 发生异常时，所有项返回错误
        fallback: List[JudgeResult] = []
        for it in _normalize_inputs(word_items, user_answers):
            fallback.append(
                JudgeResult(
                    term=it.get("term", ""),
                    reference_definition=it.get("reference_definition"),
                    user_answer=it.get("user_answer"),
                    is_match=False,
                    score=0.0,
                    verdict="incorrect",
                    reason=f"评估失败: {e}",
                    missing_keywords=[],
                )
            )
        _logger.error(f"[judge] evaluation failed: {e}")
        return fallback


__all__ = ["judge_definitions", "JudgeResult"]

# Provide nullcontext for optional context manager without importing contextlib for older Pythons
try:
    from contextlib import nullcontext  # type: ignore
except Exception:  # pragma: no cover
    class nullcontext:  # type: ignore
        def __init__(self, enter_result=None):
            self.enter_result = enter_result
        def __enter__(self):
            return self.enter_result
        def __exit__(self, *exc):
            return False
