# =========================================================================
# Stage 1: Build & Dependency Resolution
# =========================================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build prerequisites for C-extensions (asyncpg, bcrypt, pgvector)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml to resolve abstract dependencies
COPY pyproject.toml .

# Install dependencies into dedicated prefix /install
RUN pip install --prefix=/install --no-warn-script-location .

# =========================================================================
# Stage 2: Minimal Production Runtime (< 512MB RAM Footprint)
# =========================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages:/app"

WORKDIR /app

# Install minimal runtime shared libraries (libpq for PostgreSQL connectivity)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels and packages from builder stage
COPY --from=builder /install /install

# Create unprivileged system user for container isolation
RUN addgroup --system --gid 10001 appgroup && \
    adduser --system --uid 10001 --ingroup appgroup --no-create-home appuser

# Copy application source code, reference data, and administrative scripts
COPY src/ /app/src/
COPY data/ /app/data/
COPY scripts/ /app/scripts/

# Adjust file ownership to unprivileged user
RUN chown -R appuser:appgroup /app

# Switch to non-root execution
USER appuser

# Expose default HTTP port
EXPOSE 8000

# Zero-dependency container healthcheck using Python standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Launch production server with dynamic cloud PORT binding
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
