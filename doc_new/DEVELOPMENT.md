# Development Guide

## First Time Setup

### 1. Install Pre-commit Hooks

**Why?** Catches errors before CI, saves time.

**Windows:**
```powershell
.\scripts\install-hooks.ps1
```

**Linux/Mac:**
```bash
bash scripts/install-hooks.sh
```

**Verify installation:**
```bash
pre-commit run --all-files
```

## Pre-commit Hooks Overview

Our hooks catch issues **before commit**, matching CI exactly:

| Hook | What it does | Auto-fix? |
|------|--------------|-----------|
| `ruff` | Linting (E501, F401, etc.) | ✅ Yes |
| `ruff-format` | Code formatting | ✅ Yes |
| `mypy` | Type checking | ❌ No (manual fix) |
| `bandit` | Security scan | ❌ No (manual fix) |
| `trailing-whitespace` | Remove trailing spaces | ✅ Yes |
| `end-of-file-fixer` | Add newline at EOF | ✅ Yes |

### Auto-fix vs Manual Fix

**✅ Ruff auto-fixes:**
- Import sorting
- Unused imports removal
- Line length (where safe)
- Formatting

**❌ You must fix manually:**
- Type errors (mypy)
- Security issues (bandit)
- Logic errors
- Breaking changes

## Workflow

### Normal Commit
```bash
git add .
git commit -m "feat: add feature"
# Hooks run automatically
# If ruff finds issues, it auto-fixes and fails
# You must re-add fixed files and commit again
```

### If Hooks Fail

**Ruff fixed issues:**
```bash
# Ruff already fixed files
git add .  # Add the fixes
git commit -m "feat: add feature"  # Commit again
```

**Mypy/Bandit errors:**
```bash
# Fix issues manually
vim app/students/models.py
git add .
git commit -m "feat: add feature"
```

### Skip Hooks (Emergency Only)
```bash
git commit --no-verify -m "WIP: broken code"
# ⚠️ CI will still fail! Only use for WIP branches
```

## Testing Locally

### Run all hooks manually
```bash
pre-commit run --all-files
```

### Run specific hook
```bash
pre-commit run ruff --all-files
pre-commit run mypy --all-files
```

### Run unit tests (fast)
```bash
pytest tests/unit/ -v
```

### Run integration tests (needs Docker)
```bash
docker compose -f docker-compose.test.yml up -d
pytest tests/integration/ -v
```

## CI Pipeline

Our CI runs the same checks:

1. **Quality** (2 min): ruff + mypy
2. **Unit tests** (2 min): Fast, mocked
3. **Build** (3 min): Docker image
4. **Integration tests** (5 min): Real services
5. **E2E tests** (5 min): Full stack

**Pre-commit hooks = Quality + Unit tests locally**

## Industry Standards

### Ruff Auto-fix in Hooks

**✅ Industry standard:**
- Used by: FastAPI, Pydantic, Ruff itself
- Benefits: Automatic formatting, zero manual work
- Safe: Only fixes style, not logic

**How it works:**
1. You commit
2. Ruff finds issues
3. Ruff fixes them automatically
4. Commit fails (intentional)
5. You re-add fixed files
6. Commit succeeds

### Alternative: Manual Ruff

Some teams prefer:
```yaml
- id: ruff
  args: []  # No --fix, just warn
```

**We use auto-fix because:**
- Faster development
- Consistent style
- Prevents "fix lint" commits

## Troubleshooting

### Hooks not running?
```bash
# Check installation
pre-commit --version
git config --get core.hooksPath

# Reinstall
pre-commit install
```

### Hooks too slow?
```bash
# Skip slow hooks for WIP
SKIP=mypy,bandit git commit -m "WIP"
```

### Update hooks
```bash
pre-commit autoupdate
```

## Summary

**Before every commit:**
1. Ruff auto-fixes style
2. Mypy checks types (you fix)
3. Bandit checks security (you fix)

**Result:** CI passes first time, no surprises!
