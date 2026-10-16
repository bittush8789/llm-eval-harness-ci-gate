# ==============================================================================
# Multi-stage Dockerfile for AI Evaluation & Regression Testing Platform
# Python 3.12-slim with non-root security context
# ==============================================================================

FROM python:3.12-slim AS builder

WORKDIR /build

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and build wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


# Final Runtime Stage
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime library dependencies (libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy built wheels from builder and install
COPY --from=builder /build/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application source code and configurations
COPY app/ app/
COPY datasets/ datasets/
COPY evaluation/ evaluation/
COPY migrations/ migrations/
COPY scripts/ scripts/
COPY alembic.ini .
COPY pyproject.toml .

# Ensure directory permissions for non-root user
RUN mkdir -p /app/reports && \
    chown -R appuser:appgroup /app

USER appuser

# Default port for FastAPI
EXPOSE 8000

# Default entrypoint starts the FastAPI API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
