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

# Note: Dependencies should be installed by CI before calling this script
# For local use, ensure you have ruff, mypy, and django-stubs installed

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
