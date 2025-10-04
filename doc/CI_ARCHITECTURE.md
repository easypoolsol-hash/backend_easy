# CI/CD Architecture - Responsibility Matrix

## 🎯 **Design Principle: Single Responsibility**
Each component has ONE clear job. No overlapping responsibilities. No redundant environment variable management.

---

## 📋 **Component Responsibilities**

### 1️⃣ **docker-compose.test.yml** - Test Infrastructure Provider
**Job:** Provide complete, self-contained test environment

**Responsibilities:**
- ✅ Define ALL test environment variables (hardcoded - safe for testing)
- ✅ Configure test database (PostgreSQL)
- ✅ Configure test cache/broker (Redis)
- ✅ Define health checks for all services
- ✅ Set up test network
- ✅ Build and run test containers

**Environment Variables Owned:**
```yaml
DEBUG, SECRET_KEY, ENCRYPTION_KEY, DB_ENGINE, DB_NAME, DB_USER,
DB_PASSWORD, DB_HOST, DB_PORT, REDIS_URL, CELERY_BROKER_URL,
CELERY_RESULT_BACKEND, ALLOWED_HOSTS, CI
```

**Services Provided:**
- `test` - Runs pytest with migrations
- `db` - PostgreSQL test database
- `redis` - Redis test cache/broker
- `image-test` - Tests built Docker image

**Key Optimization:**
- Uses YAML anchors (`&test_env`, `&image_test_env`) to eliminate duplication
- `image-test` inherits from `test_env` and only overrides `DEBUG: false`
- Zero redundant environment variables

---

### 2️⃣ **ci.yml** - CI/CD Orchestrator
**Job:** Coordinate the entire CI/CD pipeline

**Responsibilities:**
- ✅ Orchestrate job execution order
- ✅ Manage job dependencies (`needs:`)
- ✅ Handle artifact passing (Docker images)
- ✅ Integrate with external services (Codecov, Trivy, Docker Hub)
- ✅ Control deployment conditions (master/main branches only)

**Does NOT:**
- ❌ Define test environment variables (docker-compose.test.yml handles this)
- ❌ Manage database/Redis configuration (docker-compose.test.yml handles this)
- ❌ Duplicate any configuration from docker-compose.test.yml

**Environment Variables Owned:**
```yaml
REGISTRY: docker.io
IMAGE_NAME: bus_kiosk_backend
# Only these two - everything else is in docker-compose.test.yml
```

**Job Pipeline:**
```
code-quality → test → build → test-image → security → push
```

**Key Optimization:**
- Removed redundant TEST_* environment variables (now in docker-compose.test.yml)
- Simply calls `docker compose -f docker-compose.test.yml up [service]`
- No environment variable passing needed

---

### 3️⃣ **bin/quality-check.sh** - Code Quality Checker
**Job:** Run linting and type checking

**Responsibilities:**
- ✅ Run Ruff linting
- ✅ Run MyPy type checking
- ✅ Install dependencies if in CI (`CI=true`)

**Does NOT:**
- ❌ Manage test environment variables
- ❌ Run tests (that's docker-compose.test.yml's job)
- ❌ Build images (that's build-image.sh's job)

**Environment Variables Used:**
- `CI` - Only to determine if dependencies should be installed

---

### 4️⃣ **bin/build-image.sh** - Image Builder
**Job:** Build Docker image

**Responsibilities:**
- ✅ Build Docker image with specified tag
- ✅ Enable BuildKit for caching
- ✅ Use proper build context

**Does NOT:**
- ❌ Test the image (that's docker-compose.test.yml's job)
- ❌ Push the image (that's ci.yml's job)
- ❌ Manage test environment

**Environment Variables Used:**
- `DOCKER_USERNAME` - Only for image naming
- Tag passed as argument: `./bin/build-image.sh test`

---

### 5️⃣ **bin/ci-local.sh** - Local CI Simulator
**Job:** Mirror ci.yml workflow for local testing

**Responsibilities:**
- ✅ Run quality checks (via quality-check.sh)
- ✅ Run tests (via docker-compose.test.yml)
- ✅ Build image (via build-image.sh)
- ✅ Test built image (via docker-compose.test.yml)

**Does NOT:**
- ❌ Define test environment variables (docker-compose.test.yml handles this)
- ❌ Duplicate logic from other scripts

**Environment Variables Set:**
- `CI=true` - Only to trigger CI behavior in quality-check.sh

**Key Optimization:**
- Removed 14 lines of redundant environment variable exports
- Now trusts docker-compose.test.yml to provide all test environment

---

### 6️⃣ **bin/run-tests.sh** - Local Test Runner
**Job:** Run tests locally (outside Docker)

**Responsibilities:**
- ✅ Run pytest locally
- ✅ Set local development defaults

**Does NOT:**
- ❌ Used by CI (CI uses docker-compose.test.yml directly)

**Note:** This is for local development only. CI doesn't use this script.

---

## 🔄 **Data Flow**

### CI Pipeline Flow:
```
1. ci.yml (quality job)
   └─> bin/quality-check.sh
       └─> Ruff + MyPy

2. ci.yml (test job)
   └─> docker compose -f docker-compose.test.yml up test
       └─> docker-compose.test.yml provides ALL environment
           └─> pytest runs

3. ci.yml (build job)
   └─> bin/build-image.sh test
       └─> Builds Docker image

4. ci.yml (test-image job)
   └─> docker compose -f docker-compose.test.yml up image-test
       └─> docker-compose.test.yml provides ALL environment
           └─> Image smoke test runs

5. ci.yml (security job)
   └─> Trivy scans image

6. ci.yml (push job)
   └─> Pushes to Docker Hub (master/main only)
```

### Local Development Flow:
```
1. Developer runs: ./bin/ci-local.sh
   └─> Step 1: ./bin/quality-check.sh
   └─> Step 2: docker compose -f docker-compose.test.yml up test
   └─> Step 3: ./bin/build-image.sh test
   └─> Step 4: docker compose -f docker-compose.test.yml up image-test
```

---

## ✅ **Optimization Results**

### Redundancy Eliminated:

| Component | Before | After | Improvement |
|-----------|--------|-------|-------------|
| **ci.yml env vars** | 7 variables | 2 variables | -5 redundant vars |
| **ci-local.sh env vars** | 14 exported vars | 1 exported var | -13 redundant vars |
| **docker-compose.test.yml** | Duplicated env blocks | YAML anchors with inheritance | Zero duplication |
| **test-image job** | Passed env vars | No env passing needed | Cleaner workflow |

### Total Lines of Code Saved:
- **ci.yml:** -7 lines (removed redundant env vars)
- **ci-local.sh:** -13 lines (removed redundant exports)
- **docker-compose.test.yml:** -13 lines (YAML anchors vs duplication)
- **Total:** ~33 lines of redundant code eliminated

### Maintainability Gains:
- ✅ **Single Source of Truth:** All test environment in docker-compose.test.yml
- ✅ **No Synchronization Issues:** Change once, applies everywhere
- ✅ **Clear Responsibilities:** Each component has ONE job
- ✅ **Easier Debugging:** Know exactly where each configuration lives
- ✅ **Faster Onboarding:** New developers understand the architecture immediately

---

## 🎯 **Key Takeaways**

1. **docker-compose.test.yml is the boss** for test environment
2. **ci.yml orchestrates**, doesn't duplicate
3. **Scripts do ONE thing** and do it well
4. **Environment variables** live in ONE place
5. **Zero redundancy** across the entire CI/CD pipeline

---

## 📚 **Quick Reference**

**Need to change test database password?**
→ Edit `docker-compose.test.yml` only (both x-test-env and db service)

**Need to add a test environment variable?**
→ Add to `x-test-env` in `docker-compose.test.yml` only

**Need to modify CI job order?**
→ Edit `ci.yml` `needs:` dependencies only

**Need to change linting rules?**
→ Edit `bin/quality-check.sh` only

**Need to change build arguments?**
→ Edit `bin/build-image.sh` only

---

**Last Updated:** October 5, 2025
**Architecture Version:** 2.0 (Optimized)
