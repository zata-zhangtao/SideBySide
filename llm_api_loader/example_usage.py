from __future__ import annotations

"""
Example usage of the LLM loader template.

Make sure env vars are set, e.g.:

    export LLM_PROVIDER=qwen
    export DASHSCOPE_API_KEY=your_api_key
    export DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1
    export MODEL_NAME=qwen3-vl-plus

Then run:

    python llm-templates/llm_api_loader/example_usage.py
"""

import base64
from pathlib import Path

from llm_config import LLMConfig  # type: ignore
from llm_loader import load_llm_client  # type: ignore


def as_base64(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode("utf-8")


def main() -> None:
    cfg = LLMConfig.as_dict()
    print("Effective config (non-secret):", cfg)

    client = load_llm_client()

    # Text generation
    print("\n--- Text generation ---")
    res = client.generate("Say hello in one sentence.")
    print(res)

    # Multimodal (image + text), if you have an image
    # image_path = Path("some_image.png")
    # if image_path.exists():
    #     print("\n--- Multimodal ---")
    #     img_b64 = as_base64(image_path)
    #     messages = client.build_image_text_messages(img_b64, "Describe the image.")  # type: ignore[attr-defined]
    #     for event in client.multimodal(messages, stream=True):
    #         print(event)


if __name__ == "__main__":
    main()
