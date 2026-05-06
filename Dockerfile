FROM python:3.12-slim

# Install curl for the health check
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# Install dependencies as a cached layer
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY --chown=appuser:appuser . .

# Persistent volume mount point for SQLite
RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

ENV DATABASE=/data/race_manager.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
