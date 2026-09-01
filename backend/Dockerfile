# Multi-stage build: Python backend (FastAPI + SQLAlchemy)
FROM python:3.14-slim AS builder

WORKDIR /build

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.14-slim

WORKDIR /app

# Copy only the user's pip cache from builder (lightweight)
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY app/ ./app/

# Expose backend port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health').read()"

# Seed database and start server.
# Seeding is NOT automatic: with a persistent PostgreSQL the seed script would
# wipe real data on every restart. Tables are created on app startup
# (Base.metadata.create_all); load demo data explicitly with
#   docker compose exec backend python -m app.seed
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
