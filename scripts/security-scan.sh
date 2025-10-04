#!/bin/bash
# Local Security Scanning Script
# This script runs Trivy security scanning on your Docker image

set -e

echo "🔍 Starting local security scan..."

# Configuration
IMAGE_NAME="bus_kiosk_backend"
IMAGE_TAG="test"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# Check if Docker is running
echo ""
echo "📦 Checking Docker..."
if ! docker --version &> /dev/null; then
    echo "❌ Docker is not installed or not running"
    exit 1
fi

# Check if image exists
echo ""
echo "🔍 Checking if Docker image exists..."
if ! docker images "${FULL_IMAGE}" --format "{{.Repository}}:{{.Tag}}" | grep -q "${FULL_IMAGE}"; then
    echo "❌ Image ${FULL_IMAGE} not found. Please build it first with:"
    echo "   docker build -t ${FULL_IMAGE} ."
    exit 1
fi

# Check if Trivy is installed
echo ""
echo "🔍 Checking Trivy installation..."
if ! command -v trivy &> /dev/null; then
    echo "⚠️  Trivy not found. Installing via Docker..."
    echo ""
    echo "Running Trivy via Docker container..."

    # Run Trivy in Docker container
    echo ""
    echo "📊 Scanning image for vulnerabilities (Table format)..."
    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(pwd)":/output \
        aquasec/trivy:latest image \
        --format table \
        --severity HIGH,CRITICAL \
        "${FULL_IMAGE}"

    echo ""
    echo "📄 Generating SARIF report..."
    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(pwd)":/output \
        aquasec/trivy:latest image \
        --format sarif \
        --output /output/trivy-results.sarif \
        "${FULL_IMAGE}"

    echo ""
    echo "📄 Generating JSON report..."
    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(pwd)":/output \
        aquasec/trivy:latest image \
        --format json \
        --output /output/trivy-results.json \
        "${FULL_IMAGE}"
else
    echo "✅ Trivy is installed locally"

    # Run Trivy locally
    echo ""
    echo "📊 Scanning image for vulnerabilities (Table format)..."
    trivy image --severity HIGH,CRITICAL "${FULL_IMAGE}"

    echo ""
    echo "📄 Generating SARIF report..."
    trivy image --format sarif --output trivy-results.sarif "${FULL_IMAGE}"

    echo ""
    echo "📄 Generating JSON report..."
    trivy image --format json --output trivy-results.json "${FULL_IMAGE}"
fi

if [ -f "trivy-results.sarif" ]; then
    echo ""
    echo "✅ Security scan complete!"
    echo "📁 Reports generated:"
    echo "   - trivy-results.sarif (for CodeQL/GitHub)"
    echo "   - trivy-results.json (detailed JSON)"
    echo ""
    echo "💡 To view SARIF in VS Code, install the SARIF Viewer extension"
else
    echo ""
    echo "⚠️  SARIF file not generated"
fi
