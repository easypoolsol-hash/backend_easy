#!/bin/bash
set -e

echo "🔄 Running database migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "🧪 Running tests..."
pytest tests/ -k "TestAPIEndpoints or TestAuthentication or TestDocumentationSecurity" \
  --maxfail=3 --tb=short -vv --cov=. --cov-report=xml:coverage.xml

echo "✅ All tests passed!"
