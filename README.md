SideBySide — English Study (FastAPI + React)

What’s included
- backend/ (FastAPI + SQLModel + JWT)
- frontend/ (Vite + React + TS)
- backend/llm_api_loader/ (optional LLM integration for enrichment)

Run backend
- `pip install -r backend/requirements.txt`
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `backend/`

Run frontend
- `npm install` in `frontend/`
- `npm run dev` (opens http://localhost:5173)

Docker Compose
Three environment configurations are provided:
- **Development** (`.env.dev`): SQLite + DEBUG logging + hot-reload
- **Production** (`.env.prod`): PostgreSQL + JSON logging + optimized
- **Test** (`.env.test`): In-memory DB + fast tests

Dev (auto-uses `docker-compose.override.yml`):
```bash
docker compose --env-file .env.dev up
# Or: cp .env.dev .env && docker compose up
```
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

Prod (compose base + prod override):
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d
```
- ⚠️ **Before production:** Update `SECRET_KEY`, `POSTGRES_PASSWORD`, `DASHSCOPE_API_KEY` in `.env.prod`
- Frontend: http://localhost (Nginx serves static files; `/api` proxied to backend)

Test:
```bash
docker compose --env-file .env.test up
```

Core features
- Async check‑in sessions (two users), left/right progress and scoring
- Upload custom wordlists (CSV/JSON)
- Points for correct answers; show correct answer + example on mistakes
- Friends, leaderboard (weekly/all‑time), weekly study report
- “Wrongbook” for reviewing incorrect words

Logging
Unified logging system with environment-based configuration:
- **Development**: DEBUG level, colored text output, console only
- **Production**: INFO level, JSON format, rotated log files
- **Request tracking**: Automatic request_id, user_id, session_id in all logs
- **LLM monitoring**: Built-in decorators for tracking LLM calls and performance

Configure via environment variables:
```env
LOG_LEVEL=DEBUG          # DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_FORMAT=text          # text (colored) | json (for log aggregation)
LOG_FILE_PATH=           # Optional: /app/logs/app.log
LOG_ROTATION_SIZE=10485760   # 10MB
LOG_ROTATION_COUNT=5     # Keep 5 backup files
```

View logs:
```bash
# Development
docker compose logs -f backend

# Production (JSON formatted)
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend | jq
```

Notes
- LLM is optional; if configured, it enriches example sentences when missing.
