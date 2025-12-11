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

Core features
- Async check‑in sessions (two users), left/right progress and scoring
- Upload custom wordlists (CSV/JSON)
- Points for correct answers; show correct answer + example on mistakes
- Friends, leaderboard (weekly/all‑time), weekly study report
- “Wrongbook” for reviewing incorrect words

Notes
- LLM is optional; if configured, it enriches example sentences when missing.

