#!/bin/bash
# Run Django Tests Locally (WITHOUT Docker)
# Usage: ./bin/run-tests.sh
#
# WHEN TO USE:
#   - Quick local development iterations
#   - Testing specific test cases
#   - When you already have PostgreSQL and Redis running locally
#
# FOR CI-LIKE TESTING WITH DOCKER:
#   Use: docker compose -f docker-compose.test.yml up test --abort-on-container-exit
#
# IMPORTANT: Requires PostgreSQL and Redis to be running:
#   docker compose up -d db redis

set -e

echo "🧪 Running Django tests locally (without Docker)..."
echo "💡 For Docker-based testing: docker compose -f docker-compose.test.yml up test"
echo ""

# Navigate to app directory
cd "$(dirname "$0")/../app" || exit 1

# Set defaults matching docker-compose.test.yml
# NOTE: These are ONLY used when running outside Docker
export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-test-secret-key-for-testing-only}"
export ENCRYPTION_KEY="${ENCRYPTION_KEY:-test-32-byte-encryption-key-for-testing}"
export DB_ENGINE="${DB_ENGINE:-django.db.backends.postgresql}"
export DB_NAME="${DB_NAME:-test_db}"
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-postgres}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"

# Check if services are running
echo "⚠️  Checking if PostgreSQL and Redis are accessible..."
if ! nc -z localhost 5432 2>/dev/null; then
    echo "❌ PostgreSQL is not running on localhost:5432"
    echo "   Start it with: docker compose up -d db"
    exit 1
fi
if ! nc -z localhost 6379 2>/dev/null; then
    echo "❌ Redis is not running on localhost:6379"
    echo "   Start it with: docker compose up -d redis"
    exit 1
fi
echo "✅ Services are accessible"
echo ""
# Note: Dependencies are installed by CI workflow (ci.yml). For local use,
# ensure you have a virtualenv with dev and testing extras installed, e.g.
# python -m pip install -e '.[dev,testing]'

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate --noinput || {
    echo "❌ Migration failed"
    exit 1
}

# Run tests
echo "🧪 Running pytest..."
pytest tests/ -vv --tb=short --cov-report=xml:../build/coverage.xml || {
    echo "❌ Tests failed"
    exit 1
}

echo ""
echo "✅ All tests passed!"
