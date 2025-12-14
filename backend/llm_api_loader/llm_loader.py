from __future__ import annotations

import os
from typing import Any, Dict, List


class _SimpleResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    def __str__(self) -> str:
        return self.output_text


class QwenClient:
    def __init__(self) -> None:
        self.model_name = os.getenv("MODEL_NAME", "qwen3-vl-plus")
        self._dashscope = None

        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            raise ImportError("DASHSCOPE_API_KEY not set")

        try:
            import dashscope  # type: ignore

            os.environ.setdefault("DASHSCOPE_API_KEY", api_key)
            try:
                setattr(dashscope, "api_key", api_key)
            except Exception:
                pass
            self._dashscope = dashscope
        except Exception as e:
            raise ImportError("dashscope SDK not installed. Run `pip install dashscope`.") from e

    @staticmethod
    def build_image_text_messages(img_b64: str, prompt: str) -> List[Dict[str, Any]]:
        data_url = f"data:image/png;base64,{img_b64}"
        return [
            {
                "role": "user",
                "content": [
                    {"image": data_url},
                    {"text": prompt},
                ],
            }
        ]

    def _multimodal_call(self, messages: List[Dict[str, Any]], stream: bool) -> Any:
        assert self._dashscope is not None
        ds = self._dashscope

        for attr in ("MultiModalConversation", "MultiModal"):
            cls = getattr(ds, attr, None)
            if cls and hasattr(cls, "call"):
                kwargs: Dict[str, Any] = {"model": self.model_name, "messages": messages, "stream": stream}
                def _maybe_float(name: str) -> None:
                    v = os.getenv(name)
                    if v:
                        try:
                            kwargs[name.lower()] = float(v)
                        except Exception:
                            pass
                def _maybe_int(name: str) -> None:
                    v = os.getenv(name)
                    if v:
                        try:
                            kwargs[name.lower()] = int(v)
                        except Exception:
                            pass
                _maybe_float("LLM_TEMPERATURE")
                _maybe_float("LLM_TOP_P")
                _maybe_int("LLM_SEED")
                _maybe_int("LLM_MAX_TOKENS")

                try:
                    return cls.call(**kwargs)
                except Exception:
                    return cls.call(model=self.model_name, messages=messages, stream=stream)

        gen = getattr(ds, "Generation", None)
        if gen and hasattr(gen, "call"):
            text_parts: List[str] = []
            for m in messages:
                content = m.get("content") or []
                for part in content:
                    if isinstance(part, dict) and part.get("text"):
                        text_parts.append(str(part["text"]))
            prompt = "\n".join(text_parts).strip() or "Describe the image."
            try:
                return gen.call(model=self.model_name, prompt=prompt)
            except Exception:
                return gen.call(self.model_name, prompt)

        raise ImportError("dashscope SDK missing multimodal interface")

    def multimodal(self, messages: List[Dict[str, Any]], stream: bool = False) -> Any:
        return self._multimodal_call(messages, stream=stream)

    def generate(self, prompt: str) -> Any:
        msgs = [{"role": "user", "content": [{"text": prompt}]}]
        res = self._multimodal_call(msgs, stream=False)

        try:
            text = None
            for attr in ("output_text", "text", "message", "content"):
                text = getattr(res, attr, None)
                if isinstance(text, str) and text.strip():
                    return _SimpleResponse(text)
        except Exception:
            pass

        try:
            if isinstance(res, dict):
                out = res.get("output") or {}
                if isinstance(out, dict) and isinstance(out.get("text"), str):
                    return _SimpleResponse(str(out["text"]))
                choices = res.get("choices") or []
                if choices:
                    c0 = choices[0]
                    message = c0.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return _SimpleResponse(content)
        except Exception:
            pass

        return _SimpleResponse(str(res))


def load_llm_client() -> QwenClient:
    provider = (os.getenv("LLM_PROVIDER") or "qwen").strip().lower()
    if provider in ("qwen", "dashscope", "qwen-vl", "qwen-vl-plus"):
        return QwenClient()
    raise ImportError(f"Unsupported LLM_PROVIDER: {provider!r}")
