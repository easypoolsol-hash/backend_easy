#!/bin/bash
# Build Docker Image
# Usage: ./bin/build-image.sh [tag]
# Example: ./bin/build-image.sh v1.0.0

set -e

TAG="${1:-latest}"
IMAGE_NAME="${DOCKER_USERNAME:-testuser}/bus_kiosk_backend"

echo "🐳 Building Docker image: ${IMAGE_NAME}:${TAG}"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.." || exit 1

# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1

# Build image
docker build \
    --target runtime \
    --tag "${IMAGE_NAME}:${TAG}" \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --progress=plain \
    .

echo ""
echo "✅ Docker image built: ${IMAGE_NAME}:${TAG}"
