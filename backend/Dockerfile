# Multi-stage build: Python backend (FastAPI + SQLAlchemy)
FROM python:3.14-slim AS builder

WORKDIR /build

# Copy requirements first for layer caching
COPY requirements.txt .

# pip 镜像源可注入：国内本地构建传
# --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# CI 不传则留空，pip 走官方源，行为不变
ARG PIP_INDEX_URL=""
RUN pip install --no-cache-dir --user ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r requirements.txt

# Runtime stage
FROM python:3.14-slim

WORKDIR /app

# Copy only the user's pip cache from builder (lightweight)
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code and migration assets
COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Expose backend port
EXPOSE 8001

# Liveness only; deploy smoke uses /api/health (readiness + DB)
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/health/live').read()"

# Run Alembic to head, then start the server. Pre-release volumes must be
# wiped (docker compose down -v) before first deploy on the v1 chain.
# Seeding stays manual:
#   docker compose exec backend python -m app.seed
CMD ["sh", "-c", "python -m app.bootstrap_db && exec uvicorn app.main:app --host 0.0.0.0 --port 8001"]
