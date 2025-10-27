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
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Upgrade pip first (cached layer)
RUN pip install --upgrade pip setuptools wheel

# Copy dependency files first (for better caching)
# This layer only changes when dependencies change
COPY pyproject.toml ./

# Parse pyproject.toml and install dependencies
RUN python -c "import tomllib; import subprocess; import sys; data = tomllib.load(open('pyproject.toml', 'rb')); deps = data.get('project', {}).get('dependencies', []); subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir'] + deps, check=True) if deps else None"

# Install production runtime dependencies (ASGI for websockets)
RUN pip install gunicorn>=21.2.0 whitenoise>=6.6.0 daphne>=4.0.0

# =============================================================================
# Stage 2: Runtime image (minimal and secure)
# =============================================================================
FROM python:3.12-slim-bookworm AS runtime

# Install only runtime system dependencies
# LIGHTWEIGHT: Minimal deps - only what's absolutely needed
RUN apt-get update && apt-get install -y \
    curl \
    libglib2.0-0 \
    libgomp1 \
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

# Collect static files (REQUIRED for production)
RUN python manage.py collectstatic --noinput --clear

# Run database migrations (REQUIRED for production)
RUN python manage.py migrate --noinput

# Switch to non-root user for security
USER django

# Health check for ASGI application (supports both HTTP and WebSockets)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Use Daphne for ASGI/websocket support (required for real-time features)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "bus_kiosk_backend.asgi:application"]
