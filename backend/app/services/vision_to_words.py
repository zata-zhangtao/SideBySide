from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, List
import os


def _extract_text_from_llm_result(res: Any) -> str:
    """Best-effort to get text from various SDK result shapes."""
    # Common attribute on DashScope results
    for attr in ("output_text", "text", "message", "content"):
        try:
            v = getattr(res, attr)
            if isinstance(v, str) and v.strip():
                return v
        except Exception:
            pass

    # Try dict-like
    try:
        if isinstance(res, dict):
            # dashscope sometimes places tokens at ['output']['text']
            out = res.get("output") or {}
            if isinstance(out, dict):
                text = out.get("text") or out.get("content")
                if isinstance(text, str) and text.strip():
                    return text
            # openai-like
            choices = res.get("choices") or []
            if choices:
                c0 = choices[0]
                message = c0.get("message") or {}
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content
    except Exception:
        pass

    # Fallback
    return str(res)


def extract_words_from_image(image_bytes: bytes) -> List[Dict[str, Any]]:
    """Use llm_api_loader multimodal client to extract vocabulary from an image.

    Returns a list of { term, definition?, example? } dicts.
    Raises ImportError if LLM client isn't available.
    """
    try:
        from llm_api_loader.llm_loader import load_llm_client, QwenClient  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError("llm_api_loader not available") from e

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Allow overriding the prompt via env for quick iteration
    env_prompt = os.getenv("LLM_VISION_PROMPT", "").strip()

    system_prompt = (
        "You are an expert at reading photos or scans of vocabulary notes. "
        "Your task is to extract English vocabulary items found in the image. "
        "Only output data, never explanations."
    )

    default_prompt = (
        "Extract English vocabulary items present in the image and return a JSON array ONLY (no prose, no code fences).\n"
        "Each item must be an object with keys: term (string), definition (optional string), example (optional string).\n"
        "Rules:\n"
        "- Return at most 50 items.\n"
        "- Prefer unique single-word terms; if a phrase clearly represents a term, include it.\n"
        "- Keep definitions short (<= 12 words).\n"
        "- If the image contains multiple languages, the term should be English.\n"
        "- If you are unsure of definitions or examples, omit them rather than guessing.\n"
        "- If nothing is found, return [].\n\n"
        "Example output:\n"
        "[\n  {\"term\": \"meticulous\", \"definition\": \"showing great attention to detail\", \"example\": \"She kept meticulous notes.\"},\n"
        "  {\"term\": \"serene\", \"definition\": \"calm, peaceful\"}\n]"
    )

    prompt = env_prompt or default_prompt

    client = load_llm_client()

    # Build messages for image + prompt
    try:
        build = getattr(client, "build_image_text_messages", None)
        if callable(build):
            messages = [{"role": "system", "content": [{"text": system_prompt}]}]  # type: ignore[assignment]
            messages += build(img_b64, prompt)  # type: ignore[misc]
        else:
            # Generic content payload
            data_url = f"data:image/png;base64,{img_b64}"
            messages = [
                {"role": "system", "content": [{"text": system_prompt}]},
                {"role": "user", "content": [{"image": data_url}, {"text": prompt}]},
            ]
    except Exception:
        data_url = f"data:image/png;base64,{img_b64}"
        messages = [
            {"role": "system", "content": [{"text": system_prompt}]},
            {"role": "user", "content": [{"image": data_url}, {"text": prompt}]},
        ]

    # Call multimodal without streaming for a single payload
    res = client.multimodal(messages, stream=False)
    text = _extract_text_from_llm_result(res)
    if not isinstance(text, str):
        try:
            text = json.dumps(text, ensure_ascii=False)
        except Exception:
            text = str(text)

    # Clean typical code-fence outputs
    try:
        text = text.strip()  # type: ignore[assignment]
    except Exception:
        text = str(text).strip()
    if os.getenv("LLM_DEBUG", "").lower() in ("1", "true", "yes"):  # pragma: no cover
        try:
            print("[vision_to_words] Raw LLM text:\n", text[:2000])
        except Exception:
            pass
    try:
        if isinstance(text, str) and text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\\n|```$", "", text, flags=re.MULTILINE).strip()
    except Exception:
        # Fall back to string representation
        t = str(text)
        if t.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\\n|```$", "", t, flags=re.MULTILINE).strip()

    # Try to extract a JSON array from the text, even if surrounded by prose
    def _parse_items_from_json_blob(blob: str) -> List[Dict[str, Any]]:
        try:
            data = json.loads(blob)
        except Exception:
            return []
        if isinstance(data, list):
            out: List[Dict[str, Any]] = []
            for it in data:
                if not isinstance(it, dict):
                    continue
                term = (it.get("term") or it.get("word") or "").strip()
                if not term:
                    continue
                definition = it.get("definition") or it.get("meaning")
                example = it.get("example") or it.get("sentence")
                out.append({
                    "term": str(term),
                    "definition": str(definition).strip() if isinstance(definition, str) and definition else None,
                    "example": str(example).strip() if isinstance(example, str) and example else None,
                })
            return out
        return []

    # 1) Direct JSON
    items = _parse_items_from_json_blob(text)
    if items:
        return items

    # 2) Try to find the first [...] block
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            blob = text[start : end + 1]
            items = _parse_items_from_json_blob(blob)
            if items:
                return items
    except Exception:
        pass

    # If not valid JSON array, try to salvage simple "term - def" lines
    items = []  # type: List[Dict[str, Any]]
    for line in text.splitlines():
        raw = line.strip()
        line = raw.strip("- •*\t ")
        if not line:
            continue
        # Skip very long lines (likely explanations)
        if len(line.split()) > 28:
            continue
        # Common patterns: "word - definition" or "word: definition"
        if " - " in line:
            term, definition = line.split(" - ", 1)
            if term.strip():
                items.append({"term": term.strip(), "definition": definition.strip()})
                continue
        if ": " in line:
            term, definition = line.split(": ", 1)
            if term.strip():
                items.append({"term": term.strip(), "definition": definition.strip()})
                continue
        # If the line looks like a single English word or short phrase, accept as term
        if re.fullmatch(r"[A-Za-z][A-Za-z\- ]{0,29}", line):
            items.append({"term": line.strip()})
    return items
