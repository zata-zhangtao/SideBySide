Test copies of LLM-related modules

This folder includes standalone copies of the LLM integration so you can
run tests from `backend/` without relying on repository-root imports.

Included files:
- vision_to_words.py (copy of backend/app/services/vision_to_words.py)
- llm_enrich.py (copy of backend/app/services/llm_enrich.py)
- llm_api_loader/ (copy of top-level provider loader)

Notes:
- `conftest.py` prepends this directory to `sys.path` so `import llm_api_loader`
  resolves to the test-local copy in this folder.
- Set env vars before running tests:
  - LLM_PROVIDER=qwen
  - DASHSCOPE_API_KEY=... (required)
  - MODEL_NAME=qwen3-vl-plus (recommended for vision)
  - Optional: LLM_TEMPERATURE, LLM_TOP_P, LLM_SEED, LLM_MAX_TOKENS
  - Optional: LLM_VISION_PROMPT to override the default extraction prompt
  - Optional: LLM_DEBUG=1 to print raw LLM output

Example (from repo root):
  cd backend
  pytest -q

