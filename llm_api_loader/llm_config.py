"""
LLM configuration template.

Reads values from environment (with optional `.env`) and exposes a stable API
that can be used by the LLM loader without coupling to any specific project.

Env vars:
- LLM_PROVIDER: which provider to use (default: "qwen")
- DASHSCOPE_API_KEY: API key for DashScope/Qwen
- DASHSCOPE_BASE_URL: Base URL for DashScope (default provided)
- MODEL_NAME: Default model name (default provided)
- ENABLE_THINKING: Enable reasoning/thinking mode (true/false)
- THINKING_BUDGET: Budget for thinking tokens (int)
"""

from __future__ import annotations

import os
from typing import Any, Dict

try:
    from dotenv import load_dotenv
except Exception:
    # Optional dependency; ignore if not installed
    def load_dotenv(*args: Any, **kwargs: Any) -> None:  # type: ignore
        return None


load_dotenv()


class LLMConfig:
    # Defaults
    DEFAULT_PROVIDER = "qwen"
    DEFAULT_MODEL = "qwen3-vl-plus"
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
    DEFAULT_ENABLE_THINKING = True
    DEFAULT_THINKING_BUDGET = 50

    # Env names
    ENV_PROVIDER = "LLM_PROVIDER"
    ENV_API_KEY = "DASHSCOPE_API_KEY"
    ENV_BASE_URL = "DASHSCOPE_BASE_URL"
    ENV_MODEL = "MODEL_NAME"
    ENV_ENABLE_THINKING = "ENABLE_THINKING"
    ENV_THINKING_BUDGET = "THINKING_BUDGET"

    @classmethod
    def get_provider(cls) -> str:
        return os.getenv(cls.ENV_PROVIDER, cls.DEFAULT_PROVIDER).strip().lower()

    @classmethod
    def get_api_key(cls) -> str:
        api_key = os.getenv(cls.ENV_API_KEY)
        if api_key:
            return api_key
        raise ValueError("Missing DASHSCOPE_API_KEY for provider 'qwen'")

    @classmethod
    def get_base_url(cls) -> str:
        return os.getenv(cls.ENV_BASE_URL, cls.DEFAULT_BASE_URL)

    @classmethod
    def get_model_name(cls) -> str:
        return os.getenv(cls.ENV_MODEL, cls.DEFAULT_MODEL)

    @classmethod
    def get_enable_thinking(cls) -> bool:
        raw = os.getenv(cls.ENV_ENABLE_THINKING)
        if raw is None:
            return bool(cls.DEFAULT_ENABLE_THINKING)
        return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

    @classmethod
    def get_thinking_budget(cls) -> int:
        raw = os.getenv(cls.ENV_THINKING_BUDGET)
        if not raw:
            return int(cls.DEFAULT_THINKING_BUDGET)
        try:
            return int(raw)
        except Exception:
            return int(cls.DEFAULT_THINKING_BUDGET)

    @classmethod
    def as_dict(cls) -> Dict[str, Any]:
        return {
            "provider": cls.get_provider(),
            "model_name": cls.get_model_name(),
            "base_url": cls.get_base_url(),
            "enable_thinking": cls.get_enable_thinking(),
            "thinking_budget": cls.get_thinking_budget(),
        }


__all__ = ["LLMConfig"]
