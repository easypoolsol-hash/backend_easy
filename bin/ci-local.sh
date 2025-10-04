#!/bin/bash
# Simulate CI Pipeline Locally
# Mirrors .github/workflows/ci.yml for local testing

set -e

echo "🚀 Simulating CI pipeline locally..."
echo ""

# Navigate to project root
cd "$(dirname "$0")/.." || exit 1

# Set minimal CI flag (environment variables are now in docker-compose.test.yml)
export CI=true

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Step 1: Code Quality Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./bin/quality-check.sh || exit 1

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Step 2: Unit Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# Run tests using docker-compose.test.yml (like CI does)
docker compose -f docker-compose.test.yml up test --abort-on-container-exit

# Copy coverage report to expected location
docker compose -f docker-compose.test.yml cp test:/app/../build/coverage.xml ./build/coverage.xml || true

# Cleanup
docker compose -f docker-compose.test.yml down -v

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐳 Step 3: Build Docker Image"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./bin/build-image.sh test || exit 1

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Step 4: Test Built Image"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# Test the built image using docker-compose.test.yml (like CI does)
DOCKER_IMAGE=testuser/bus_kiosk_backend:test \
docker compose -f docker-compose.test.yml up image-test --abort-on-container-exit

# Cleanup
docker compose -f docker-compose.test.yml down -v

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ CI Pipeline Simulation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 All checks passed! Ready to push to GitHub."
