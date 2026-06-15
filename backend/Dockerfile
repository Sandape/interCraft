FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install uv for fast, deterministic installs.
RUN pip install --no-cache-dir "uv>=0.4"

WORKDIR /app

# Copy project metadata first for layer caching.
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts

# Install dependencies (no dev deps in image; CI uses separate target).
RUN uv pip install --system --no-cache .

EXPOSE 8000

# Default to api; docker-compose overrides for worker service.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
