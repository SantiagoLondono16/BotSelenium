# ── Stage: runtime ────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr so logs
# appear immediately in docker logs / CI output.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies:
#   gcc + libpq-dev  — needed to compile asyncpg's C extension
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying source code so that this layer
# is cached on re-builds unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Run as a non-root user to limit the blast radius of any vulnerability.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Start-up sequence:
#   1. alembic upgrade head — applies any pending migrations
#   2. uvicorn              — starts the ASGI server
#
# The DB healthcheck in docker-compose.yml guarantees Postgres is ready
# before this container starts, so alembic can connect immediately.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
