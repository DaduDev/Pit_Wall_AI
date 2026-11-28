FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    CACHE_DIR=/tmp/pitwall_cache \
    HOME=/home/user

WORKDIR /app

# Create non-root user (uid=1000 required by Hugging Face Spaces)
RUN useradd -m -u 1000 user

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code, embedded read-only DuckDB, corner metadata, and seeded research cache
COPY backend/ ./backend/
COPY data/f1_data.duckdb ./data/f1_data.duckdb
COPY data/corner_nicknames.json ./data/corner_nicknames.json
COPY data/research_cache/ ./data/research_cache/
COPY data/openf1_cache/ ./data/openf1_cache/

RUN mkdir -p /tmp/pitwall_cache/fastf1 /tmp/pitwall_cache/research_cache /tmp/pitwall_cache/openf1_cache /tmp/pitwall_cache/artifacts \
    && chown -R 1000:1000 /app /tmp/pitwall_cache

USER 1000

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
