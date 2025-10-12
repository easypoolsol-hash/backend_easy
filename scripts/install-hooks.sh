#!/bin/bash
# Install pre-commit hooks
# Run once after cloning repo

set -e

echo "Installing pre-commit hooks..."

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    echo "pre-commit not found. Installing..."
    pip install pre-commit
fi

# Install hooks
pre-commit install

# Install commit-msg hook (optional - for conventional commits)
pre-commit install --hook-type commit-msg || true

echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "To test hooks without committing:"
echo "  pre-commit run --all-files"
echo ""
echo "To skip hooks (not recommended):"
echo "  git commit --no-verify"
