from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, List


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
    prompt = (
        "You are an assistant that reads an image containing vocabulary notes or lists. "
        "Extract English vocabulary items. Return STRICT JSON array only, no prose, no code fences.\n"
        "Each item: {\"term\": string, \"definition\": string (optional), \"example\": string (optional)}.\n"
        "Keep definitions short (<= 12 words). If nothing found, return []."
    )

    client = load_llm_client()

    # Build messages for image + prompt
    try:
        build = getattr(client, "build_image_text_messages", None)
        if callable(build):
            messages = build(img_b64, prompt)  # type: ignore[misc]
        else:
            # Generic content payload
            data_url = f"data:image/png;base64,{img_b64}"
            messages = [{"role": "user", "content": [{"image": data_url}, {"text": prompt}]}]
    except Exception:
        data_url = f"data:image/png;base64,{img_b64}"
        messages = [{"role": "user", "content": [{"image": data_url}, {"text": prompt}]}]

    # Call multimodal without streaming for a single payload
    res = client.multimodal(messages, stream=False)
    text = _extract_text_from_llm_result(res)

    # Clean typical code-fence outputs
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\\n|```$", "", text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(text)
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
    except Exception:
        pass

    # If not valid JSON array, try to salvage simple "term - def" lines
    items: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip("- •*\t ")
        if not line or len(line.split()) > 20:
            continue
        if " - " in line:
            term, definition = line.split(" - ", 1)
            items.append({"term": term.strip(), "definition": definition.strip()})
    return items

