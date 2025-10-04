# 🎯 Simplified Environment & Compose Structure

## Problem Solved

**Before**: Multiple redundant files with duplicated configuration
- `.env.ci` (for docker-compose)
- `.env.ci.local` (for native tests)
- `docker-compose.yml` (local dev)
- `docker-compose.ci.yml` (CI testing)

**After**: Clean, DRY structure with minimal redundancy
- `.env.ci` (ONE file for BOTH local dev AND CI)
- `docker-compose.yml` (ONE file for BOTH local dev AND CI)
- `infrastructure/docker-compose.yml` (production only)
- `infrastructure/.env.production` (production only)

---

## 📁 Final Structure

```
project/
├── .env.ci                          # Local dev + CI testing
├── docker-compose.yml               # Local dev + CI testing
└── infrastructure/
    ├── .env.production              # Production only
    └── docker-compose.yml           # Production only
```

---

## ✅ Key Principles Applied

### 1. **DRY (Don't Repeat Yourself)**
- Environment variables defined **once** in `.env.ci`
- No inline `environment:` duplicates in docker-compose.yml
- `env_file: .env.ci` loads all vars automatically

### 2. **Minimal Overrides**
- `environment:` section only contains Docker network overrides
- Example: `DB_HOST=db` (service name) overrides `DB_HOST=localhost` from .env.ci

### 3. **Production Separation**
- Production config completely separate in `infrastructure/` folder
- No mixing of dev/test and production concerns

---

## 📋 File Contents

### `.env.ci` (Local & CI)

```bash
# Development & CI Testing Environment Configuration
# Used for BOTH local development AND CI testing

DEBUG=True
SECRET_KEY=test-secret-key-for-local-and-ci-do-not-use-in-production
ENCRYPTION_KEY=test-32-byte-encryption-key-dev-ci

# Database Configuration
# DB_HOST defaults to localhost (for native Python)
# Docker services override to 'db' (service name)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=test_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
# Defaults to localhost, overridden by docker-compose
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Application Settings
ALLOWED_HOSTS=*
CORS_ALLOWED_ORIGINS=http://localhost:8000

# Port Configuration
BACKEND_PORT=8000
REDIS_PORT=6379
```

###docker-compose.yml Pattern

```yaml
services:
  web:
    env_file:
      - .env.ci  # Load all vars from file
    environment:
      # ONLY Docker-specific overrides
      - DB_HOST=db  # Override localhost with service name
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    env_file:
      - .env.ci  # Reuse same env file
    environment:
      # Postgres-specific vars
      - POSTGRES_DB=${DB_NAME}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}

  redis:
    env_file:
      - .env.ci  # Consistent across all services
```

---

## 🔄 How It Works

### Local Development (Native Python)

```bash
# Load .env.ci for native Python
source .env.ci  # Unix
# or
Get-Content .env.ci | ForEach-Object { if ($_ -match '^([^#][^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }  # PowerShell

# Run Django directly
python manage.py runserver

# DB_HOST=localhost connects to local PostgreSQL
```

### Local Development (Docker)

```bash
# docker-compose reads .env.ci automatically
docker-compose up

# DB_HOST=db (overridden) connects to db service
```

### CI Testing (Native - Job 2)

```yaml
- name: Load CI environment variables
  run: |
    cat .env.ci >> $GITHUB_ENV

- name: Run Django tests
  run: |
    python manage.py test --verbosity=2

# DB_HOST=localhost connects to GitHub Actions services
```

### CI Testing (Docker - Job 4)

```yaml
- name: Run tests in Docker container
  run: |
    docker-compose up -d db redis
    docker-compose run --rm web sh -c "
    python manage.py migrate &&
    python manage.py test
    "

# DB_HOST=db (overridden) connects to db service
```

---

## 📊 Before vs After Comparison

### Before (Redundant)

```yaml
# docker-compose.yml
services:
  web:
    environment:
      - DEBUG=True
      - SECRET_KEY=${SECRET_KEY}
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_HOST=db
      - DB_PORT=5432
      - REDIS_URL=redis://redis:6379/0
      # ... 10+ more vars duplicated everywhere
```

```yaml
# docker-compose.ci.yml (separate file!)
services:
  backend:
    env_file:
      - .env.ci
    environment:
      # MORE duplicates
```

```bash
# .env.ci (for docker-compose.ci.yml)
DB_HOST=postgres  # Different from dev!
```

```bash
# .env.ci.local (for GitHub Actions)
DB_HOST=localhost  # Yet another copy!
```

### After (DRY)

```yaml
# docker-compose.yml (ONE file for dev + CI)
services:
  web:
    env_file:
      - .env.ci  # All vars loaded here
    environment:
      # ONLY overrides
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
```

```bash
# .env.ci (ONE file for dev + CI)
DB_HOST=localhost  # Default for native Python
# Docker overrides to 'db' in docker-compose.yml
```

---

## ✨ Benefits

### 1. **Single Source of Truth**
- Environment variables defined **once** in `.env.ci`
- Changes propagate everywhere automatically

### 2. **Less Maintenance**
- One file to update instead of 4
- No sync issues between files

### 3. **Clearer Intent**
- `.env.ci` = base configuration
- `environment:` in docker-compose = Docker-specific overrides only
- Separation is obvious

### 4. **Smaller Files**
- docker-compose.yml is cleaner
- No wall of environment variables

### 5. **Reusability**
- Same `.env.ci` works for:
  - Local native Python development
  - Local Docker development
  - CI native tests (Job 2)
  - CI Docker tests (Job 4)

---

## 🚀 Usage Guide

### For Developers

**Local development (native Python):**
```bash
# Copy .env.ci to .env.local and customize if needed
cp .env.ci .env.local
python manage.py runserver
```

**Local development (Docker):**
```bash
# Just run docker-compose (reads .env.ci automatically)
docker-compose up
```

### For CI/CD

**GitHub Actions automatically:**
- Loads `.env.ci` for Job 2 (native tests)
- Uses `.env.ci` in docker-compose for Job 4 (Docker tests)
- No manual configuration needed!

### For Production

**Completely separate:**
```bash
cd infrastructure/
# Use .env.production and infrastructure/docker-compose.yml
docker-compose up -d
```

---

## 🎯 Industry Best Practices Met

✅ **12-Factor App** - Config in environment, not code
✅ **DRY Principle** - No duplication
✅ **Separation of Concerns** - Dev/test vs production
✅ **Convention over Configuration** - Sensible defaults
✅ **Explicit Overrides** - Docker network changes are visible

---

## 📝 Migration Notes

### Files Removed
- ❌ `.env.ci.local` (merged into `.env.ci`)
- ❌ `docker-compose.ci.yml` (merged into `docker-compose.yml`)

### Files Modified
- ✅ `.env.ci` - Now works for both native and Docker
- ✅ `docker-compose.yml` - Uses `env_file` + minimal `environment` overrides
- ✅ `.github/workflows/ci.yml` - Uses main docker-compose.yml
- ✅ `.gitignore` - Tracks `.env.ci` (committed to git)

---

**Result**: Clean, maintainable configuration with ZERO redundancy! 🎉
