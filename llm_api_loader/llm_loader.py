"""
Unified LLM loader template (provider-agnostic entry point).

Currently supports `qwen` (DashScope). Designed to be extended with more
providers by implementing the LLMClientProtocol and wiring them in
`load_llm_client`.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Protocol, Union
import logging

# Support both package and direct-script execution.
try:  # Preferred when used as a package
    from .llm_config import LLMConfig
except ImportError:  # Fallback when running files directly
    from llm_config import LLMConfig  # type: ignore


class LLMClientProtocol(Protocol):
    def multimodal(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        *,
        stream: bool = True,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterable[Any]:
        ...

    def generate(
        self,
        prompt_or_messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        *,
        stream: bool = False,
        incremental_output: bool = False,
        **kwargs: Any,
    ) -> Any:
        ...


class QwenClient(LLMClientProtocol):
    """Minimal DashScope/Qwen client using lazy SDK import."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or LLMConfig.get_api_key()
        self.base_url = base_url or LLMConfig.get_base_url()
        self.default_model = default_model or LLMConfig.get_model_name()
        self._initialized = False
        self._sdk = None

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            import dashscope  # type: ignore
            from dashscope import MultiModalConversation, Generation  # type: ignore
        except Exception as e:  # pragma: no cover - import guard
            raise ImportError(
                "DashScope SDK not installed. Install with: pip install dashscope"
            ) from e

        dashscope.api_key = self.api_key
        if hasattr(dashscope, "base_http_api_url"):
            dashscope.base_http_api_url = self.base_url  # type: ignore[attr-defined]

        self._sdk = {
            "dashscope": dashscope,
            "MultiModalConversation": MultiModalConversation,
            "Generation": Generation,
        }
        logging.info(
            "DashScope initialized (model=%s, base_url=%s)",
            self.default_model,
            self.base_url,
        )
        self._initialized = True

    def multimodal(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        *,
        stream: bool = True,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterable[Any]:
        self._ensure_initialized()

        params: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
        }
        if enable_thinking:
            params["enable_thinking"] = True
            if thinking_budget is not None:
                params["thinking_budget"] = int(thinking_budget)
        params.update(kwargs)

        return self._sdk["MultiModalConversation"].call(**params)  # type: ignore[index]

    def generate(
        self,
        prompt_or_messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        *,
        stream: bool = False,
        incremental_output: bool = False,
        **kwargs: Any,
    ) -> Any:
        self._ensure_initialized()

        if isinstance(prompt_or_messages, str):
            messages = [{"role": "user", "content": prompt_or_messages}]
        else:
            messages = prompt_or_messages

        params: Dict[str, Any] = {
            "model": model or "qwen-plus",
            "messages": messages,
            "stream": stream,
            "incremental_output": incremental_output,
        }
        params.update(kwargs)
        return self._sdk["Generation"].call(**params)  # type: ignore[index]

    @staticmethod
    def build_image_text_messages(image_base64: str, text: str) -> List[Dict[str, Any]]:
        data_url = f"data:image/png;base64,{image_base64}"
        return [
            {
                "role": "user",
                "content": [
                    {"image": data_url},
                    {"text": text},
                ],
            }
        ]


def load_llm_client(provider: Optional[str] = None) -> LLMClientProtocol:
    """Return a provider-specific LLM client based on configuration."""
    use = (provider or LLMConfig.get_provider()).lower()
    if use == "qwen":
        return QwenClient()
    raise ValueError(f"Unsupported LLM provider: {use}")


__all__ = [
    "LLMClientProtocol",
    "QwenClient",
    "load_llm_client",
]
