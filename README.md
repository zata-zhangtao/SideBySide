SideBySide — English Study (FastAPI + React)

What’s included
- backend/ (FastAPI + SQLModel + JWT)
- frontend/ (Vite + React + TS)
- llm_api_loader/ (optional LLM enrichment utilities already present)

Run backend
- `pip install -r backend/requirements.txt`
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `backend/`

Run frontend
- `npm install` in `frontend/`
- `npm run dev` (opens http://localhost:5173)

Docker Compose
- Copy `.env.example` to `.env` and adjust values as needed.
- Dev (auto-uses `docker-compose.override.yml`):
  - `docker compose up --build` then open http://localhost:5173
  - Backend: http://localhost:8000 (CORS allows 5173)
- Prod (compose base + prod override):
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
  - Open http://localhost (Nginx serves frontend; `/api` is proxied to backend)
  - Configure strong `SECRET_KEY` in `.env`; Postgres creds via `POSTGRES_*`.

Core features
- Async check‑in sessions (two users), left/right progress and scoring
- Upload custom wordlists (CSV/JSON)
- Points for correct answers; show correct answer + example on mistakes
- Friends, leaderboard (weekly/all‑time), weekly study report
- “Wrongbook” for reviewing incorrect words

Notes
- LLM is optional; if configured, it enriches example sentences when missing.
