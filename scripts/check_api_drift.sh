#!/bin/bash
# CONSTITUTIONAL API DRIFT VALIDATOR
# Industry tool: openapi-diff (Azure/OpenAPITools)
# Zero dependencies - uses npx (already installed)

set -e

echo "🔍 Constitutional API Drift Check"
echo "=================================="

BACKEND_SPEC="openapi-schema.yaml"
FRONTEND_SPEC="../bus_kiosk_easy/bus_kiok/openapi-schema.yaml"

# Check if specs exist
if [ ! -f "$BACKEND_SPEC" ]; then
    echo "❌ Backend OpenAPI spec not found: $BACKEND_SPEC"
    exit 1
fi

if [ ! -f "$FRONTEND_SPEC" ]; then
    echo "❌ Frontend OpenAPI spec not found: $FRONTEND_SPEC"
    exit 1
fi

# Check if specs are identical (should be copied by git hook)
echo "📋 Checking if frontend has latest spec..."
if diff -q "$BACKEND_SPEC" "$FRONTEND_SPEC" > /dev/null 2>&1; then
    echo "✅ Frontend spec is up-to-date"
else
    echo "❌ DRIFT DETECTED: Frontend spec differs from backend"
    echo ""
    echo "Backend spec: $BACKEND_SPEC"
    echo "Frontend spec: $FRONTEND_SPEC"
    echo ""
    echo "Fix: Git hook should have copied spec. Run:"
    echo "  cp $BACKEND_SPEC $FRONTEND_SPEC"
    exit 1
fi

# Check if generated client is fresh
CLIENT_PATH="../bus_kiosk_easy/packages/bus_kiosk_api"
if [ ! -d "$CLIENT_PATH" ]; then
    echo "❌ Generated client not found: $CLIENT_PATH"
    echo "Fix: Run backend git commit to trigger generation"
    exit 1
fi

CLIENT_MARKER="$CLIENT_PATH/.openapi-generator/VERSION"
if [ ! -f "$CLIENT_MARKER" ]; then
    echo "❌ Generated client missing metadata: $CLIENT_MARKER"
    echo "This indicates incomplete generation"
    exit 1
fi

# Compare timestamps (spec should not be newer than client)
SPEC_TIME=$(stat -c %Y "$BACKEND_SPEC" 2>/dev/null || stat -f %m "$BACKEND_SPEC")
CLIENT_TIME=$(stat -c %Y "$CLIENT_MARKER" 2>/dev/null || stat -f %m "$CLIENT_MARKER")

if [ "$SPEC_TIME" -gt "$CLIENT_TIME" ]; then
    echo "❌ DRIFT DETECTED: OpenAPI spec is newer than generated client"
    echo ""
    echo "  Spec modified:   $(date -r "$BACKEND_SPEC" 2>/dev/null || stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$BACKEND_SPEC")"
    echo "  Client generated: $(date -r "$CLIENT_MARKER" 2>/dev/null || stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$CLIENT_MARKER")"
    echo ""
    echo "Fix: Make a backend commit to trigger regeneration"
    echo "  cd backend_easy && git commit --allow-empty -m 'Regenerate API client'"
    exit 1
fi

echo "✅ Generated client is fresh (no drift)"

# Optional: Use openapi-diff for breaking change detection
# Requires: npx (already installed)
# Compares current spec with previous version (if available)
PREV_SPEC="openapi-schema.yaml.prev"
if [ -f "$PREV_SPEC" ]; then
    echo ""
    echo "🔬 Checking for breaking changes..."
    if npx openapi-diff "$PREV_SPEC" "$BACKEND_SPEC" --fail-on-breaking 2>/dev/null; then
        echo "✅ No breaking changes detected"
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 1 ]; then
            echo "⚠️  BREAKING CHANGES DETECTED!"
            echo ""
            echo "Review changes carefully before deploying."
            echo "See: npx openapi-diff $PREV_SPEC $BACKEND_SPEC"
            # Don't fail - just warn
        fi
    fi
fi

echo ""
echo "✅ API drift validation passed"
exit 0
