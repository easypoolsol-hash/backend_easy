#!/bin/bash
# Code Quality Check Script
# Usage: ./bin/quality-check.sh
# Can be run locally or in CI

set -e

echo "🔍 Running code quality checks..."
echo ""

# Navigate to app directory
cd "$(dirname "$0")/../app" || exit 1

# Install dependencies if needed
if [ "${CI}" = "true" ]; then
    echo "📦 Installing dependencies..."
    python -m pip install --upgrade pip
    pip install -e .[dev,testing]
fi

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
