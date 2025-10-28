#!/bin/bash
# Helper script to run commands in virtual environment
# Usage: bash scripts/run_in_venv.sh <command> [args...]

# Load test environment variables if .env.test exists
if [ -f ".env.test" ]; then
    set -a  # Export all variables
    source .env.test
    set +a
fi

# Try to find and use the virtual environment Python
if [ -f ".venv/Scripts/python" ]; then
    # Windows venv
    .venv/Scripts/python "$@"
elif [ -f ".venv/bin/python" ]; then
    # Unix venv
    .venv/bin/python "$@"
elif [ -f "venv/Scripts/python" ]; then
    # Windows venv (alternate name)
    venv/Scripts/python "$@"
elif [ -f "venv/bin/python" ]; then
    # Unix venv (alternate name)
    venv/bin/python "$@"
else
    # Fallback to system python (will likely fail with missing deps)
    echo "⚠️  Warning: Virtual environment not found, using system Python"
    python "$@"
fi
