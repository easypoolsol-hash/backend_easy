# Automated Skip Logic System

## Problem Statement

Pre-commit hooks and CI pipelines traditionally run **all checks on every commit**, leading to:

1. **False Positives**: API drift validation failing on config-only changes
2. **Wasted Time**: Running tests when only documentation changed
3. **Developer Friction**: Committing `.pre-commit-config.yaml` triggers unnecessary API regeneration
4. **CI Cost**: Running full test suites for trivial changes

### Example of the Problem

```bash
# Developer commits pre-commit config update
git add .pre-commit-config.yaml
git commit -m "Add skip tests parameter"

# Old behavior (BAD):
❌ API drift validation runs (even though no API changed)
❌ Unit tests run (even though no code changed)
❌ Integration tests run (wasting 5+ minutes)
❌ Drift validator fails with timestamp mismatch

# New behavior (GOOD):
✅ Only config-relevant hooks run
⏭️  API drift validation SKIPPED (config-only change)
⏭️  Tests SKIPPED (config-only change)
✅ Commit succeeds instantly
```

## Solution Architecture

### 1. Smart Hook Orchestrator

**Location**: [`scripts/smart_hook_orchestrator.sh`](../scripts/smart_hook_orchestrator.sh)

A coordinator script that wraps each pre-commit hook and decides whether to:
- **Run** the hook (changes are relevant)
- **Skip** the hook (changes are irrelevant)

#### How It Works

```bash
# Instead of running hook directly:
entry: python -m pytest tests/

# We wrap it with orchestrator:
entry: bash scripts/smart_hook_orchestrator.sh unit-tests-core python -m pytest tests/
```

The orchestrator:
1. Analyzes what files are staged for commit
2. Categorizes changes (config-only, test-only, API changes, etc.)
3. Applies skip logic based on hook type
4. Either runs the hook or skips with explanation

#### Change Detection Logic

```bash
# Config-only changes
.pre-commit-config.yaml, pyproject.toml, docker-compose.yml, .github/workflows/

# Test-only changes
tests/**/*.py

# API code changes
app/**/views.py, app/**/serializers.py, app/**/urls.py, app/**/models.py

# ML code changes
app/**/*embed*.py, app/**/*face*.py
```

### 2. Hook-Specific Skip Rules

#### API Drift Validation

**Skip when:**
- ✅ Only config files changed
- ✅ Only test files changed
- ✅ Schema was just regenerated in this commit

**Run when:**
- ❌ API code changed (views, serializers, URLs, models)
- ❌ OpenAPI schema changed

**Rationale**: If no API code changed, the schema can't be out of date. If the schema was just regenerated in this commit, it's fresh by definition.

#### Test Hooks

**Skip when:**
- ✅ Only config files changed (CI will run full suite anyway)
- ✅ Only documentation changed

**Run when:**
- ❌ Any application code changed
- ❌ Test code changed

**Rationale**: Config-only changes don't need local test runs - CI provides comprehensive testing.

#### Schema Regeneration

**Skip when:**
- ✅ No API code changed

**Run when:**
- ❌ views.py, serializers.py, urls.py, or models.py changed

**Rationale**: OpenAPI schema is generated from Django code. If Django code didn't change, schema doesn't need regeneration.

#### Client Regeneration

**Skip when:**
- ✅ OpenAPI schema unchanged

**Run when:**
- ❌ openapi-schema.yaml changed

**Rationale**: Client is generated from schema. If schema didn't change, client doesn't need regeneration.

### 3. CI Pipeline Integration

**Location**: [`.github/workflows/detect-changes.yml`](../.github/workflows/detect-changes.yml)

A reusable workflow that detects what changed in the PR/push.

#### Outputs

```yaml
outputs:
  config-only: 'true/false'      # Only config files changed
  test-only: 'true/false'        # Only test files changed
  api-changes: 'true/false'      # API code changed
  ml-changes: 'true/false'       # ML code changed
  should-run-tests: 'true/false' # Should tests run?
```

#### Usage in CI

```yaml
jobs:
  detect-changes:
    uses: ./.github/workflows/detect-changes.yml

  unit-tests:
    needs: [detect-changes]
    # Automatically skip if config-only
    if: needs.detect-changes.outputs.should-run-tests == 'true'
```

**Benefits**:
- Saves GitHub Actions minutes
- Faster feedback on trivial changes
- Still runs full suite on code changes

## Implementation Guide

### Pre-commit Hooks

**Before** (runs unconditionally):
```yaml
- id: unit-tests-core
  entry: python -m pytest tests/unit/
  files: \.py$
```

**After** (uses orchestrator):
```yaml
- id: unit-tests-core
  entry: bash
  args: ["scripts/smart_hook_orchestrator.sh", "unit-tests-core", "python", "-m", "pytest", "tests/unit/"]
  files: \.py$
```

### Adding New Skip Logic

To add skip logic for a new hook:

1. **Edit orchestrator**: Add case to `smart_hook_orchestrator.sh`

```bash
case "$HOOK_NAME" in
    "my-new-hook")
        if has_config_only_changes; then
            echo "⏭️  SKIP: Config-only changes"
            exit 0
        fi
        exec "$@"
        ;;
esac
```

2. **Update pre-commit config**: Wrap hook with orchestrator

```yaml
- id: my-new-hook
  entry: bash
  args: ["scripts/smart_hook_orchestrator.sh", "my-new-hook", "original-command"]
```

### Debugging

Enable verbose output:

```bash
# See what orchestrator is doing
SKIP_DEBUG=1 git commit

# Force run all hooks (bypass skip logic)
SKIP_DISABLED=1 git commit
```

Add to orchestrator:
```bash
if [ "$SKIP_DEBUG" = "1" ]; then
    echo "DEBUG: Staged files: $STAGED_FILES"
    echo "DEBUG: Config-only: $(has_config_only_changes && echo true || echo false)"
fi

if [ "$SKIP_DISABLED" = "1" ]; then
    echo "⚠️  Skip logic disabled by SKIP_DISABLED=1"
    exec "$@"
fi
```

## Benefits

### For Developers

1. **Faster Commits**: Config-only commits complete in seconds
2. **Less Friction**: No false API drift errors
3. **Better UX**: Clear skip messages explain why hooks didn't run
4. **Predictability**: Same logic in pre-commit and CI

### For CI/CD

1. **Cost Savings**: Skip expensive test runs on trivial changes
2. **Faster Feedback**: Config updates deploy immediately
3. **Resource Efficiency**: Don't spin up Docker for documentation changes
4. **Smarter Pipeline**: Tests only run when needed

### For Codebase Quality

1. **Zero False Positives**: Drift validation only runs when relevant
2. **Guaranteed Consistency**: Pre-commit and CI use same logic
3. **Documentation**: Clear skip reasons in commit output
4. **Extensibility**: Easy to add new skip rules

## Comparison

### Without Automated Skip Logic

```bash
$ git add .pre-commit-config.yaml
$ git commit -m "Update pre-commit config"

Regenerate OpenAPI Schema........................Skipped (no files matched)
Copy OpenAPI Schema to Flutter...................Skipped (no files matched)
Regenerate Bus Kiosk API Client..................Skipped (no files matched)
Regenerate Frontend Easy API Client..............Skipped (no files matched)
Validate API Drift...............................Failed ❌
  ❌ DRIFT DETECTED: OpenAPI spec is newer than generated client
  Fix: Make a backend commit to trigger regeneration

Unit Tests (Core Logic)..........................Passed (but wasted time)
Auth Tests (Security Critical)...................Passed (but wasted time)
ML Tests (Face Recognition)......................Passed (but wasted time)

Total time: 45 seconds
Result: FAILURE (false positive)
```

### With Automated Skip Logic

```bash
$ git add .pre-commit-config.yaml
$ git commit -m "Update pre-commit config"

Regenerate OpenAPI Schema........................Skipped (no files matched)
Copy OpenAPI Schema to Flutter...................Skipped (no files matched)
Regenerate Bus Kiosk API Client..................Skipped (no files matched)
Regenerate Frontend Easy API Client..............Skipped (no files matched)
Validate API Drift...............................Skipped
  ⏭️  SKIP: Only config files changed, no API drift possible
Unit Tests (Core Logic)..........................Skipped
  ⏭️  SKIP: Config-only changes, tests not needed (CI will run full suite)
Auth Tests (Security Critical)...................Skipped
  ⏭️  SKIP: Config-only changes, tests not needed (CI will run full suite)
ML Tests (Face Recognition)......................Skipped
  ⏭️  SKIP: Config-only changes, tests not needed (CI will run full suite)

Total time: 3 seconds
Result: SUCCESS ✅
```

## Maintenance

### When to Update Skip Logic

1. **New file types**: Add patterns to change detection
2. **New dependencies**: Update skip rules to reflect dependencies
3. **False skips**: If hook should run but doesn't, tighten skip rules
4. **False runs**: If hook runs unnecessarily, broaden skip rules

### Testing Skip Logic

```bash
# Test config-only changes
git add .pre-commit-config.yaml
git commit -m "test" --no-verify  # Bypass to test

# Test API changes
git add app/users/views.py
git commit -m "test" --no-verify

# Verify skip behavior matches expectations
```

### Monitoring

Track skip rates in CI:

```yaml
- name: Report skip statistics
  run: |
    echo "Tests skipped: ${{ needs.detect-changes.outputs.should-run-tests == 'false' }}"
    echo "Reason: ${{ needs.detect-changes.outputs.config-only }}"
```

## References

- [Pre-commit Hook Documentation](https://pre-commit.com/)
- [GitHub Actions - Conditional Jobs](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idif)
- [tj-actions/changed-files](https://github.com/tj-actions/changed-files) - Change detection action
- [Industry Best Practices: Smart CI Pipelines](https://martinfowler.com/articles/branching-patterns.html#smart-ci)

## Future Enhancements

1. **Skip History**: Track which hooks skip most frequently
2. **Smart Caching**: Cache test results for unchanged code paths
3. **Parallel Hook Execution**: Run independent hooks concurrently
4. **ML-Based Prediction**: Predict which tests are likely to fail based on changes
