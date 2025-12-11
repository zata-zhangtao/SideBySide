SideBySide Backend (FastAPI)

Quick start
- Create a virtualenv and install deps: `pip install -r backend/requirements.txt`
- Run the API (dev): `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- API base: `http://localhost:8000/api`
- CORS allows frontend at `http://localhost:5173` by default.

Features
- Users: register/login (JWT), friends
- Wordlists: upload CSV/JSON, manage words
- Sessions: async quiz sessions (two users), scoreboard, attempts
- Points: +10 for correct, 0 for incorrect
- Wrongbook: list of words either user answered wrong
- Leaderboard: weekly and all‑time points
- Weekly report: compare two users over the last 7 days

Env
- `DATABASE_URL` (default: `sqlite:///./backend/data.db`)
- `SECRET_KEY` (default insecure dev key; set in prod!)
- `CORS_ORIGINS` comma separated origins (default: http://localhost:5173)
- Optional LLM (for example sentences when missing):
  - See `llm_api_loader/` and set provider envs accordingly.

Wordlist upload
- CSV headers supported: `term,definition,example` (case‑insensitive). Extra columns ignored.
- JSON supported: array of objects with those keys.

Notes
- This is a minimal scaffold to get core async flows working first.
- Sync/real‑time will be added via WebSockets in a follow‑up.

