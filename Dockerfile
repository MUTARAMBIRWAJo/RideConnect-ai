FROM python:3.11-slim

WORKDIR /app

# System packages:
#   curl     — used by Docker HEALTHCHECK
#   libpq-dev + gcc — required to compile psycopg2-binary on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

# Persistent directories (overridden by Docker volumes in production)
RUN mkdir -p logs models

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8001/ || exit 1

# Worker count is configurable for horizontal scaling scenarios.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001} --workers ${UVICORN_WORKERS:-2}"]
