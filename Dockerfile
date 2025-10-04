# Multi-stage optimized Dockerfile for Bus Kiosk Backend
# Optimized for frequent rebuilds with maximum layer caching

# =============================================================================
# Stage 1: Build dependencies (cached when pyproject.toml doesn't change)
# =============================================================================
FROM python:3.11-slim AS builder

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

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip first (cached layer)
RUN pip install --upgrade pip setuptools wheel

# Copy dependency files first (for better caching)
# This layer only changes when dependencies change
COPY pyproject.toml ./

# Install Python dependencies in virtual environment
# Use --no-deps to avoid installing dependencies of dependencies twice
RUN pip install --no-deps -e .

# Install production runtime dependencies
RUN pip install gunicorn>=21.2.0 whitenoise>=6.6.0

# =============================================================================
# Stage 2: Runtime image (minimal and secure)
# =============================================================================
FROM python:3.11-slim AS runtime

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && groupadd -r django && useradd -r -g django django

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code (changes frequently, so placed after dependencies)
COPY --chown=django:django . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app

# Collect static files (optional, can be done at runtime)
# RUN python manage.py collectstatic --noinput --clear

# Switch to non-root user for security
USER django

# Health check with proper configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Use gunicorn for production (better than runserver)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "bus_kiosk_backend.wsgi:application"]
