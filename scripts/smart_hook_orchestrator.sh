#!/bin/bash
# SMART HOOK ORCHESTRATOR
# Coordinates pre-commit hooks to prevent false positives and unnecessary work
#
# Problem: Hooks run independently, causing:
# - API drift validation fails on config-only changes
# - Client regeneration runs unnecessarily
# - Timestamp mismatches between spec and client
#
# Solution: Intelligent skip detection based on:
# 1. What files actually changed
# 2. What hooks already ran in this commit
# 3. Dependencies between hooks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

HOOK_NAME="$1"
shift # Remaining args are for the actual hook

echo -e "${BLUE}🔧 Smart Hook Orchestrator${NC}"
echo "Hook: $HOOK_NAME"

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

# Detect what category of changes we have
has_api_code_changes() {
    echo "$STAGED_FILES" | grep -qE '(views|serializers|urls|models)\.py$'
}

has_openapi_schema_changes() {
    echo "$STAGED_FILES" | grep -qE 'openapi-schema\.yaml$'
}

has_config_only_changes() {
    # Config files that don't affect API contract
    local config_patterns='(\.pre-commit-config\.yaml|pyproject\.toml|\.github/workflows/|docker-compose|Dockerfile|\.env)'

    # Check if ALL changes are config files
    if [ -z "$STAGED_FILES" ]; then
        return 1
    fi

    # Check if any non-config files are changed
    if echo "$STAGED_FILES" | grep -vE "$config_patterns" | grep -q .; then
        return 1  # Has non-config changes
    else
        return 0  # Only config changes
    fi
}

has_test_only_changes() {
    # Check if all changes are in test files
    if echo "$STAGED_FILES" | grep -v 'tests/' | grep -v '^test_' | grep -q .; then
        return 1  # Has non-test changes
    else
        return 0  # Only test changes
    fi
}

# Check if schema was just regenerated in this commit cycle
schema_just_regenerated() {
    # If openapi-schema.yaml is staged, it was just regenerated
    echo "$STAGED_FILES" | grep -qE 'openapi-schema\.yaml$'
}

# Decision logic for each hook
case "$HOOK_NAME" in
    "validate-api-drift")
        echo "Analyzing drift validation necessity..."

        # Skip if only config files changed
        if has_config_only_changes; then
            echo -e "${YELLOW}⏭️  SKIP: Only config files changed, no API drift possible${NC}"
            exit 0
        fi

        # Skip if only test files changed
        if has_test_only_changes; then
            echo -e "${YELLOW}⏭️  SKIP: Only test files changed, no API drift possible${NC}"
            exit 0
        fi

        # Skip if schema was just regenerated (it's fresh by definition)
        if schema_just_regenerated; then
            echo -e "${GREEN}✓ Schema just regenerated in this commit - guaranteed fresh${NC}"
            exit 0
        fi

        # Run drift validation if:
        # - API code changed (schema should be regenerated)
        # - Schema file changed (client should be regenerated)
        if has_api_code_changes || has_openapi_schema_changes; then
            echo -e "${BLUE}→ Running drift validation (API changes detected)${NC}"
            exec "$@"
        else
            echo -e "${YELLOW}⏭️  SKIP: No API-related changes detected${NC}"
            exit 0
        fi
        ;;

    "openapi-schema")
        echo "Analyzing schema regeneration necessity..."

        if has_api_code_changes; then
            echo -e "${BLUE}→ Regenerating schema (API code changed)${NC}"
            exec "$@"
        else
            echo -e "${YELLOW}⏭️  SKIP: No API code changes, schema regeneration not needed${NC}"
            exit 0
        fi
        ;;

    "copy-schema-to-flutter"|"regenerate-bus-kiosk-api"|"regenerate-frontend-easy-api")
        echo "Analyzing client regeneration necessity..."

        # Only run if schema actually changed
        if has_openapi_schema_changes; then
            echo -e "${BLUE}→ Running client sync (schema changed)${NC}"
            exec "$@"
        else
            echo -e "${YELLOW}⏭️  SKIP: Schema unchanged, client sync not needed${NC}"
            exit 0
        fi
        ;;

    "unit-tests-core"|"auth-tests"|"ml-tests")
        echo "Analyzing test necessity..."

        # Skip tests for config-only changes
        if has_config_only_changes; then
            echo -e "${YELLOW}⏭️  SKIP: Config-only changes, tests not needed${NC}"
            echo -e "${YELLOW}   (CI will run full test suite)${NC}"
            exit 0
        fi

        # Run tests if relevant files changed
        echo -e "${BLUE}→ Running tests (code changes detected)${NC}"
        exec "$@"
        ;;

    *)
        # Unknown hook - pass through
        echo -e "${BLUE}→ Running hook (no skip logic defined)${NC}"
        exec "$@"
        ;;
esac
