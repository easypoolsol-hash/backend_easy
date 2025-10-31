# Skip Guide - Pre-commit & CI

## Pre-commit Hooks

### Quick Skip (for small changes)
Skip specific hooks using the `SKIP` environment variable:

```bash
# Skip OpenAPI schema regeneration
SKIP=openapi-schema git commit -m "fix: typo in comment"

# Skip multiple hooks (comma-separated)
SKIP=openapi-schema,unit-tests-core git commit -m "chore: update config"

# Skip all tests
SKIP=unit-tests-core,auth-tests,ml-tests git commit -m "docs: update README"
```

### Available Hooks to Skip
- `openapi-schema` - OpenAPI schema regeneration
- `validate-api-drift` - API drift validation
- `validate-snapshot-contract` - Snapshot contract validation
- `unit-tests-core` - Core unit tests
- `auth-tests` - Authentication tests
- `ml-tests` - ML/face recognition tests
- `mypy` - Type checking
- `bandit` - Security scanner

### CANNOT Be Skipped (Constitutional Protection)
- `protect-master-branch` - Master branch protection
  - Attempting to skip will result in commit failure
  - This is intentional - prevents accidental direct commits to master

### Example Usage
```bash
# Small config change - skip slow hooks
SKIP=mypy,unit-tests-core git commit -m "chore: update settings"

# Documentation only - skip all code checks
SKIP=mypy,unit-tests-core,openapi-schema git commit -m "docs: add deployment guide"

# Quick fix - skip everything except master protection
SKIP=openapi-schema,mypy,unit-tests-core,auth-tests git commit -m "fix: typo"
```

## GitHub CI/CD

### Skip All CI (docs/config only changes)
Use GitHub's native skip flags in commit message:

```bash
git commit -m "docs: update README [skip ci]"
git commit -m "chore: update .gitignore [ci skip]"
```

This completely skips the CI workflow - no jobs run at all.

### Skip Tests BUT Prevent Image Build
Use `[skip tests]` in commit message:

```bash
git commit -m "chore: update logging config [skip tests]"
```

**What happens:**
- ✅ CI workflow runs (shows in GitHub)
- ⏭️  All test jobs are skipped (quality, tests, build, security)
- ⛔ Image is NOT built
- ⛔ Image is NOT pushed to Artifact Registry
- ⛔ No deployment happens

**Safety guarantee:**
Untested images can NEVER reach staging/production. If tests are skipped, the image won't be built, so there's nothing to deploy.

### When to Use Each

| Use Case | Command | Result |
|----------|---------|--------|
| Docs only | `[skip ci]` | No CI runs at all |
| Config tweaks | `[skip tests]` | CI runs but skips tests + build |
| Code changes | (no flag) | Full test suite + deployment |

### Production Safety

The workflow enforces this rule:
```
NO TESTS → NO IMAGE → NO DEPLOYMENT → NO PRODUCTION RISK
```

If you use `[skip tests]` on develop branch:
- Staging will NOT be updated (no image built)
- Merging to master will do nothing (no staging image to promote)
- Production stays on last tested version

## Configuration Created

Created `settings.local.json` for efficient Claude CLI token usage:
- Default model: Sonnet (faster, cheaper than Opus)
- Auto-compact at 100K tokens → 50K
- Max output: 4096 tokens
- File handling: 500 lines max per read
