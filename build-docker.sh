#!/bin/bash
# Docker Build Optimization Script for Bus Kiosk Backend
# This script ensures optimal Docker builds with maximum layer caching

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="bus_kiosk_backend"
TAG=${1:-"latest"}
BUILD_ARGS=""

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        echo "❌ Docker daemon is not running"
        exit 1
    fi
}

# Build optimized Docker image
build_optimized() {
    log_info "🚀 Building optimized Docker image: ${IMAGE_NAME}:${TAG}"

    # Enable BuildKit for better caching and performance
    export DOCKER_BUILDKIT=1

    # Build with optimizations
    docker build \
        --target runtime \
        --tag "${IMAGE_NAME}:${TAG}" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --progress=plain \
        .

    log_success "✅ Docker image built successfully"
}

# Show build info
show_info() {
    echo ""
    echo "📊 Build Optimization Features:"
    echo "  • Multi-stage build (builder + runtime)"
    echo "  • Layer caching for dependencies"
    echo "  • Minimal runtime image"
    echo "  • Non-root user for security"
    echo "  • Virtual environment isolation"
    echo "  • Production-ready with gunicorn"
    echo ""
    echo "🏗️  Layer Caching Strategy:"
    echo "  1. System dependencies (rarely changes)"
    echo "  2. Python virtual environment (rarely changes)"
    echo "  3. pyproject.toml dependencies (changes with updates)"
    echo "  4. Application code (changes frequently)"
    echo ""
}

# Main function
main() {
    echo "🐳 Bus Kiosk Backend - Docker Build Optimizer"
    echo "=============================================="

    check_docker
    show_info
    build_optimized

    echo ""
    log_success "🎉 Build complete! Image: ${IMAGE_NAME}:${TAG}"
    echo ""
    echo "💡 Tips for faster rebuilds:"
    echo "  • Dependencies in pyproject.toml change → Only dependency layers rebuild"
    echo "  • Application code changes → Only final layer rebuilds"
    echo "  • Use BuildKit: export DOCKER_BUILDKIT=1"
    echo "  • Use build cache: docker build --cache-from ${IMAGE_NAME}:latest"
}

# Handle command line arguments
case "${1:-}" in
    "--help"|"-h")
        echo "Usage: $0 [tag]"
        echo "  tag: Docker image tag (default: latest)"
        echo ""
        echo "Examples:"
        echo "  $0                    # Build with tag 'latest'"
        echo "  $0 v1.2.3            # Build with tag 'v1.2.3'"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
