# Multi-stage optimized Dockerfile for Bus Kiosk Backend
# Supports WebSockets via ASGI (Daphne) for real-time features
# Optimized for frequent rebuilds with maximum layer caching

# =============================================================================
# Stage 1: Build dependencies (cached when pyproject.toml doesn't change)
# =============================================================================
FROM python:3.12-slim-bookworm AS builder

# Set environment variables for better caching and performance
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install system build dependencies (minimal set for Python packages)
# WeasyPrint PDF generation dependencies added
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Upgrade pip first (cached layer)
RUN pip install --upgrade pip setuptools wheel

# Copy dependency files first (for better caching)
# This layer only changes when dependencies change
COPY pyproject.toml ./

# Parse pyproject.toml and install dependencies
RUN python -c "import tomllib; import subprocess; import sys; data = tomllib.load(open('pyproject.toml', 'rb')); deps = data.get('project', {}).get('dependencies', []); subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir'] + deps, check=True) if deps else None"

# Install optional ML dependencies for Docker/production
RUN python -c "import tomllib; import subprocess; import sys; data = tomllib.load(open('pyproject.toml', 'rb')); ml_deps = data.get('project', {}).get('optional-dependencies', {}).get('ml', []); subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir'] + ml_deps, check=True) if ml_deps else None"

# Install production runtime dependencies (ASGI for websockets)
RUN pip install gunicorn>=21.2.0 whitenoise>=6.6.0 daphne>=4.0.0

# =============================================================================
# Stage 2: Runtime image (minimal and secure)
# =============================================================================
FROM python:3.12-slim-bookworm AS runtime

# Install only runtime system dependencies
# LIGHTWEIGHT: Minimal deps - only what's absolutely needed
# WeasyPrint runtime dependencies added for PDF generation
RUN apt-get update && apt-get install -y \
    curl \
    libglib2.0-0 \
    libgomp1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi8 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && groupadd -r django && useradd -r -g django django

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy ML models directory first (required by application)
COPY --chown=django:django ml_models/ /app/ml_models/

# Copy application code (changes frequently, so placed after dependencies)
COPY --chown=django:django app/ .

# Create necessary directories with proper permissions
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app

# Set PYTHONPATH to include /app for ml_models
ENV PYTHONPATH=/app

# Collect static files (safe to do at build time)
RUN python manage.py collectstatic --noinput --clear

# DO NOT run migrations at build time - they should run at deployment time
# Migrations require database connectivity and should be part of deployment process

# Switch to non-root user for security
USER django

# Health check for ASGI application (uses liveness probe - always succeeds if server is up)
# This matches Cloud Run's startup probe behavior
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live/ || exit 1

# Expose port
EXPOSE 8000

# Create production-grade startup script with industry-standard resilience
USER root
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "🚀 Starting EasyPool Backend - Industry Standard Startup"\n\
echo "ℹ️  Application will start FIRST, then initialize database"\n\
\n\
# Download ML models from GCS (Cloud Run only)\n\
if [ -n "$K_SERVICE" ]; then\n\
    echo "📦 [ML-MODELS] Downloading face recognition models from GCS..."\n\
    python -c "from ml_models.model_loader import load_models_on_startup; load_models_on_startup()" || echo "⚠️  [ML-MODELS] Model download failed - face verification may not work"\n\
else\n\
    echo "📦 [ML-MODELS] Running locally - using local models"\n\
fi\n\
\n\
# Function to run database operations in background\n\
run_db_init() {\n\
    echo "📦 [BACKGROUND] Starting database initialization..."\n\
    \n\
    # Wait for database with exponential backoff (up to 2 minutes)\n\
    attempt=1\n\
    max_attempts=12\n\
    wait_time=5\n\
    \n\
    while [ $attempt -le $max_attempts ]; do\n\
        echo "⏳ [DB-INIT] Attempt $attempt/$max_attempts: Checking database connectivity..."\n\
        if python manage.py check --database default 2>/dev/null; then\n\
            echo "✅ [DB-INIT] Database connection established on attempt $attempt"\n\
            break\n\
        fi\n\
        \n\
        if [ $attempt -eq $max_attempts ]; then\n\
            echo "⚠️  [DB-INIT] Database connection failed after $max_attempts attempts"\n\
            echo "⚠️  [DB-INIT] Application will continue running, but migrations were not applied"\n\
            echo "⚠️  [DB-INIT] Check /health/ready/ endpoint for database status"\n\
            return 1\n\
        fi\n\
        \n\
        echo "⏳ [DB-INIT] Waiting ${wait_time}s before retry..."\n\
        sleep $wait_time\n\
        \n\
        # Exponential backoff (5s, 10s, 15s, 20s, max 30s)\n\
        wait_time=$((wait_time + 5))\n\
        if [ $wait_time -gt 30 ]; then\n\
            wait_time=30\n\
        fi\n\
        \n\
        attempt=$((attempt + 1))\n\
    done\n\
    \n\
    # Run migrations (idempotent - safe to run multiple times)\n\
    echo "📦 [DB-INIT] Running database migrations..."\n\
    if python manage.py migrate --noinput; then\n\
        echo "✅ [DB-INIT] Migrations completed successfully"\n\
    else\n\
        echo "⚠️  [DB-INIT] Migrations failed - check logs"\n\
        return 1\n\
    fi\n\
    \n\
    echo "✅ [DB-INIT] Database initialization complete"\n\
    \n\
    # Create bootstrap admin (singleton, atomic, waits for DB)\n\
    python manage.py ensure_bootstrap_admin || echo "[DB-INIT] Admin creation deferred"\n\
}\n\
\n\
# Start database initialization in background\n\
run_db_init &\n\
DB_INIT_PID=$!\n\
\n\
# Give database init a brief head start\n\
sleep 2\n\
\n\
# Ensure admin exists (retry every 10s for 2 min in background)\n\
(\n\
    for i in {1..12}; do\n\
        output=$(python manage.py ensure_bootstrap_admin 2>&1)\n\
        echo \"$output\"\n\
        if echo \"$output\" | grep -q SUCCESS; then\n\
            break\n\
        fi\n\
        sleep 10\n\
    done\n\
) &\n\
\n\
# Start the ASGI server IMMEDIATELY\n\
echo "✅ Application starting on port 8000"\n\
echo "🌐 Health: /health/live/ /health/ready/ /health/"\n\
echo "🔐 Admin: /admin/ (admin / admin)"\n\
echo "🚀 Starting Daphne..."\n\
exec daphne -b 0.0.0.0 -p 8000 bus_kiosk_backend.asgi:application' > /app/start.sh && \
    chmod +x /app/start.sh && \
    chown django:django /app/start.sh

USER django

# Use the startup script for runtime initialization
CMD ["/app/start.sh"]
