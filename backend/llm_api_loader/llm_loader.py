from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path to import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import get_logger

# Initialize logger for this module
logger = get_logger(__name__)


class _SimpleResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text

    def __str__(self) -> str:
        return self.output_text


class QwenClient:
    def __init__(self) -> None:
        self.model_name = os.getenv("MODEL_NAME", "qwen3-vl-plus")
        self._dashscope = None
        logger.info(f"Initializing QwenClient with model: {self.model_name}")

        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not api_key:
            logger.error("DASHSCOPE_API_KEY environment variable not set")
            raise ImportError("DASHSCOPE_API_KEY not set")

        try:
            import dashscope  # type: ignore

            os.environ.setdefault("DASHSCOPE_API_KEY", api_key)
            try:
                setattr(dashscope, "api_key", api_key)
            except Exception:
                pass
            self._dashscope = dashscope
            logger.info("QwenClient initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize dashscope SDK: {e}", exc_info=True)
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
        logger.debug(f"Making multimodal call with model: {self.model_name}, stream: {stream}")

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
                    logger.debug(f"Calling {attr}.call with kwargs: {list(kwargs.keys())}")
                    response = cls.call(**kwargs)
                    logger.debug(f"Multimodal call succeeded via {attr}")
                    return response
                except Exception as e:
                    logger.warning(f"Failed to call {attr} with kwargs, retrying with basic params: {e}")
                    return cls.call(model=self.model_name, messages=messages, stream=stream)

        gen = getattr(ds, "Generation", None)
        if gen and hasattr(gen, "call"):
            logger.debug("Falling back to Generation.call for multimodal request")
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

        logger.error("dashscope SDK missing multimodal interface")
        raise ImportError("dashscope SDK missing multimodal interface")

    def multimodal(self, messages: List[Dict[str, Any]], stream: bool = False) -> Any:
        return self._multimodal_call(messages, stream=stream)

    def generate(self, prompt: str) -> Any:
        logger.debug(f"Generating response for prompt (length: {len(prompt)})")
        msgs = [{"role": "user", "content": [{"text": prompt}]}]
        res = self._multimodal_call(msgs, stream=False)

        try:
            text = None
            for attr in ("output_text", "text", "message", "content"):
                text = getattr(res, attr, None)
                if isinstance(text, str) and text.strip():
                    logger.debug(f"Successfully extracted response text via attribute: {attr}")
                    return _SimpleResponse(text)
        except Exception as e:
            logger.debug(f"Failed to extract text from response attributes: {e}")

        try:
            if isinstance(res, dict):
                out = res.get("output") or {}
                if isinstance(out, dict) and isinstance(out.get("text"), str):
                    logger.debug("Successfully extracted response text from dict output")
                    return _SimpleResponse(str(out["text"]))
                choices = res.get("choices") or []
                if choices:
                    c0 = choices[0]
                    message = c0.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        logger.debug("Successfully extracted response text from choices")
                        return _SimpleResponse(content)
        except Exception as e:
            logger.debug(f"Failed to extract text from dict response: {e}")

        logger.warning("Falling back to str() conversion for response")
        return _SimpleResponse(str(res))


def load_llm_client() -> QwenClient:
    provider = (os.getenv("LLM_PROVIDER") or "qwen").strip().lower()
    logger.info(f"Loading LLM client for provider: {provider}")

    if provider in ("qwen", "dashscope", "qwen-vl", "qwen-vl-plus"):
        client = QwenClient()
        logger.info(f"LLM client loaded successfully: {provider}")
        return client

    logger.error(f"Unsupported LLM_PROVIDER: {provider}")
    raise ImportError(f"Unsupported LLM_PROVIDER: {provider!r}")
