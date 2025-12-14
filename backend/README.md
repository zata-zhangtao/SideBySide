SideBySide Backend (FastAPI)

Quick start
- Create a virtualenv and install deps: `pip install -r backend/requirements.txt`
- Run the API (dev):
  - Recommended (compose): `docker compose up -d backend`
  - Local: from `backend/` folder:
    - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- API base: `http://localhost:8000/api`
- CORS allows frontend at `http://localhost:5173` by default.

Features
- Users: register/login (JWT), friends
- Wordlists: upload CSV/JSON, manage words
- Sessions: async quiz sessions (two users), scoreboard, attempts
  - Bidirectional quizzing: definition → term (中→英) and term → definition (英→中)
  - `GET /api/sessions/{id}/next_word?direction=zh2en|en2zh|random` (default random)
  - `POST /api/sessions/{id}/attempts?word_id=..&answer=..&direction=zh2en|en2zh`
- Points: +10 for correct, 0 for incorrect
- Wrongbook: list of words either user answered wrong
- Leaderboard: weekly and all‑time points
- Weekly report: compare two users over the last 7 days

Env
- `DATABASE_URL` (default: `sqlite:///./backend/data.db`)
- `SECRET_KEY` (default insecure dev key; set in prod!)
- `CORS_ORIGINS` comma separated origins (default: http://localhost:5173)
- Optional LLM (for example sentences when missing):
  - See `backend/llm_api_loader/` and set provider envs accordingly.
  - For 图片建库 (image → wordlist), install provider SDK and set envs:
    - `pip install dashscope python-dotenv`
    - Env: `LLM_PROVIDER=qwen`, `DASHSCOPE_API_KEY=...`, optional `MODEL_NAME=qwen3-vl-plus`
    - Endpoint: `POST /api/wordlists/from_image` (multipart: `name`, `file`)
  - When running from `backend/`, the `llm_api_loader` package is available by default.

Wordlist upload
- CSV headers supported: `term,definition,example` (case‑insensitive). Extra columns ignored.
- JSON supported: array of objects with those keys.
 - Image supported (LLM required): `POST /api/wordlists/from_image`

Notes
- This is a minimal scaffold to get core async flows working first.
- Sync/real‑time will be added via WebSockets in a follow‑up.
