# 🔧 Bin Scripts

Executable scripts for development, testing, and CI/CD workflows.

## 📋 Available Scripts

### 🏠 Local Development

#### `dev-setup.sh`
**First-time setup for new developers**
```bash
./bin/dev-setup.sh
```
- Creates `.env` from `.env.example`
- Starts Docker services (PostgreSQL, Redis)
- Installs Python dependencies
- Runs database migrations
- Optionally creates superuser

---

### 🧪 Testing & Quality

#### `quality-check.sh`
**Run code quality checks (linting, type checking)**
```bash
./bin/quality-check.sh
```
- Runs Ruff linting
- Runs MyPy type checking
- Works in both local and CI environments

#### `run-tests.sh`
**Run Django unit and integration tests**
```bash
./bin/run-tests.sh
```
- Runs database migrations
- Executes pytest with coverage
- Works in both local and CI environments

**Requirements:** PostgreSQL and Redis must be running
```bash
docker-compose up -d db redis
```

---

### 🐳 Docker

#### `build-image.sh [tag]`
**Build Docker image**
```bash
./bin/build-image.sh latest
./bin/build-image.sh v1.0.0
```
- Builds optimized Docker image
- Uses BuildKit for caching
- Tags image with specified tag

#### `ci-local.sh`
**Run complete CI pipeline locally (before pushing)**
```bash
./bin/ci-local.sh
```
Runs all CI steps:
1. ✅ Code quality checks
2. 🧪 Unit tests (using `docker-compose.test.yml`)
3. 🐳 Build Docker image
4. ✅ Test Docker image (using `docker-compose.test.yml`)

**Environment variables:** No longer needs manual setup - uses hardcoded test values from `docker-compose.test.yml`

Perfect for validating changes before pushing to GitHub!

---

## 🎯 Common Workflows

### New Developer Setup
```bash
# 1. Clone repo
git clone <repo-url>
cd backend_easy

# 2. Run setup
./bin/dev-setup.sh

# 3. Start development server
cd app
python manage.py runserver
```

### Before Committing Code
```bash
# Run quality checks
./bin/quality-check.sh

# Run tests
docker-compose up -d db redis
./bin/run-tests.sh
```

### Before Pushing to GitHub
```bash
# Run full CI pipeline locally
./bin/ci-local.sh
```

### Manual Docker Testing
```bash
# Build image
./bin/build-image.sh test

# Test image (CI handles this automatically)
docker run --rm --network host \
  -e SECRET_KEY=test-key \
  -e DB_HOST=localhost \
  testuser/bus_kiosk_backend:test \
  python manage.py check
```

---

## 🔧 Environment Variables

**Local Development:** Scripts use defaults or respect environment variables from `.env`

**CI/Testing:** No longer needs manual environment variable setup - `docker-compose.test.yml` contains hardcoded safe test values

### CI Detection
Scripts automatically detect CI environment via `CI=true` variable.

---

## 💡 Tips

1. **Make scripts executable:**
   ```bash
   chmod +x bin/*.sh
   ```

2. **Run from any directory:**
   Scripts use `$(dirname "$0")` to find project root

3. **Debugging:**
   Add `set -x` at the top of any script to see commands as they run

4. **Windows:**
   Use Git Bash or WSL to run these scripts on Windows

---

## 📚 Script Dependencies

| Script | Requires |
|--------|----------|
| `quality-check.sh` | Python, pip |
| `run-tests.sh` | Python, PostgreSQL, Redis |
| `build-image.sh` | Docker |
| `dev-setup.sh` | Docker, docker-compose, Python |
| `ci-local.sh` | All of the above |
