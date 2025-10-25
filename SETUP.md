# Backend Development Setup

## Prerequisites

- **Python 3.12** (required - specified in pyproject.toml)
- Git
- PostgreSQL (for production)

## Local Development Setup

### 1. Create Virtual Environment

```bash
# Windows
py -3.12 -m venv .venv

# Linux/Mac
python3.12 -m venv .venv
```

### 2. Activate Virtual Environment

```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install runtime dependencies (skip ai-edge-litert on Windows - only needed for production)
pip install Django djangorestframework djangorestframework-simplejwt psycopg2-binary celery redis django-redis channels channels-redis daphne Pillow opencv-python-headless numpy django-prometheus drf-api-logger psutil django-cors-headers django-celery-beat django-celery-results django-filter cryptography django-csp djangorestframework-api-key python-decouple requests ulid-py drf-spectacular python-json-logger django-auditlog django-model-utils argon2-cffi pytz

# Install OpenAPI dependencies
pip install drf-spectacular[sidecar] openapi-core openapi-schema-validator openapi-spec-validator prance

# Install dev dependencies
pip install ruff mypy black pre-commit django-stubs django-stubs-ext djangorestframework-stubs mypy-extensions types-PyYAML types-requests types-redis types-psutil types-django-filter types-pytz django-debug-toolbar django-extensions werkzeug

# Install test dependencies
pip install pytest pytest-django pytest-cov pytest-asyncio factory-boy faker pytest-xdist pytest-mock
```

### 4. Install Pre-commit Hooks

```bash
pre-commit install
```

### 5. Run Migrations

```bash
cd app
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver
```

## Why Use a Virtual Environment?

1. **Dependency Isolation** - Avoids conflicts with system Python packages
2. **Match CI Environment** - CI uses Python 3.12, local should match
3. **Reproducible Builds** - Everyone has identical environments
4. **Pre-commit Hooks Work** - Hooks will use correct Python version and dependencies

## Linting & Type Checking

The pre-commit hooks now match CI exactly:

```bash
# Run all checks manually
ruff check --fix .
mypy app --no-incremental

# Or just commit - hooks run automatically
git commit -m "your message"
```

## Troubleshooting

### `ai-edge-litert` install fails on Windows
This is expected - the package is Linux-only and only needed for production face recognition. Local development works without it.

### Pre-commit hook fails with "module not found"
Make sure you activated the venv and installed all dependencies.

### Mypy fails to find Django
Make sure `PYTHONPATH=app` is set (handled automatically by pre-commit hook).
