#!/bin/bash
# Code Quality Check Script
# Usage: ./bin/quality-check.sh
# Can be run locally or in CI

set -e

echo "🔍 Running code quality checks..."
echo ""

# Get project root directory
PROJECT_ROOT="$(dirname "$0")/.."
cd "${PROJECT_ROOT}" || exit 1

# Install dependencies if needed
if [ "${CI}" = "true" ]; then
    echo "📦 Installing linting dependencies..."
    python -m pip install --upgrade pip
    # Just install the linting tools directly, don't need full package install
    pip install --no-cache-dir ruff>=0.6.0 mypy>=1.8.0 django-stubs>=5.0.0
fi

# Navigate to app directory for linting
cd app || exit 1

# Run Ruff linting
echo "🧹 Running Ruff linting..."
ruff check . || {
    echo "❌ Ruff linting failed"
    exit 1
}

# Run MyPy type checking
echo "🔍 Running MyPy type checking..."
mypy . --config-file ../config/mypy.ini --no-incremental || {
    echo "❌ MyPy type checking failed"
    exit 1
}

echo ""
echo "✅ All code quality checks passed!"
