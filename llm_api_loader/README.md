# LLM API Loader Template

A minimal, copy-friendly template to load and use an LLM client.
This template references `config.py` and `llm_client.py` patterns from the root
of this repository, but is self-contained for reuse elsewhere.

## Features
- Centralized configuration via env/.env with safe defaults
- Provider switch via `LLM_PROVIDER` (currently supports `qwen`/DashScope)
- Lazy SDK import with clear errors if the SDK is missing
- Helpers for text generation and multimodal messages

## Quick Start
1. Install the provider SDK (for Qwen/DashScope):
   
   ```bash
   pip install dashscope python-dotenv
   ```

2. Set environment variables (or a `.env`):
   
   ```bash
   export LLM_PROVIDER=qwen
   export DASHSCOPE_API_KEY=your_api_key
   export DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1
   export MODEL_NAME=qwen3-vl-plus
   ```

3. Try the example:
   
   ```bash
   python llm-templates/llm_api_loader/example_usage.py
   ```

## Files
- `llm_config.py`: Template config for provider/model/API key.
- `llm_loader.py`: Unified loader that returns a provider-specific client.
- `example_usage.py`: Minimal usage example for text and multimodal calls.

## Extend Providers
You can add more providers by:
- Creating a new class implementing `LLMClientProtocol` (see `llm_loader.py`).
- Referencing env vars in `llm_config.py` and wiring them in `load_llm_client`.
