FROM ghcr.io/astral-sh/uv:python3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# System deps (keep minimal; uv image is Debian-based)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq5 \
  && rm -rf /var/lib/apt/lists/*

# Prefer uv.lock for reproducible installs; fall back to requirements.txt
COPY pyproject.toml uv.lock* /app/
COPY requirements.txt /app/requirements.txt
RUN if [ -f /app/uv.lock ]; then \
      (uv sync --frozen --no-dev --system) || (echo 'uv sync failed; falling back to requirements.txt' && uv pip install --system --no-cache -r /app/requirements.txt); \
    else \
      uv pip install --system --no-cache -r /app/requirements.txt; \
    fi

# Copy app source
COPY . /app

# Work in project dir with package at /app/app
WORKDIR /app

EXPOSE 8000

# Default command (can be overridden in compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
