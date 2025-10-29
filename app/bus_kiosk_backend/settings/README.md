# Django Settings - Fortune 500 Pattern

Industry-standard Django settings structure following 12-Factor App methodology and Django Two Scoops best practices.

## Structure

```
bus_kiosk_backend/settings/
├── __init__.py      # Auto-detects environment and loads appropriate settings
├── base.py          # Common settings shared across all environments
├── local.py         # Local development settings (.env loading happens here)
├── ci.py            # CI/CD testing settings (GitHub Actions, GitLab CI, etc.)
└── production.py    # Production settings (HTTPS, PostgreSQL, Redis required)
```

## Fortune 500 Principles

### 1. **NO .env in Production**
- **Local Development**: Uses .env file (loaded in `local.py` only)
- **Production**: Environment variables injected by cloud platform (GCP Secret Manager, K8s secrets)
- **CI/CD**: Environment variables set in pipeline configuration

### 2. **Auto-Detection**
Settings are automatically loaded based on environment detection:

```python
# Priority order:
1. DJANGO_ENV environment variable (explicit override)
2. CI platform detection (GITHUB_ACTIONS, GITLAB_CI, etc.)
3. Cloud platform detection (GAE_APPLICATION, K_SERVICE, AWS_EXECUTION_ENV)
4. Default: local development
```

### 3. **Fail-Fast in Production**
Production settings use `os.environ["KEY"]` (not `os.getenv()`) to fail immediately if required secrets are missing.

## Usage

### Local Development

```bash
# Default - auto-detects as local
python manage.py runserver

# Explicit override
export DJANGO_ENV=local
python manage.py runserver
```

**Local settings include:**
- .env file loading (ONLY place where .env is used)
- SQLite database
- In-memory cache (no Redis needed)
- DEBUG=True
- CORS for localhost
- Browsable DRF API

### CI/CD Testing

```bash
# Auto-detected in CI environments (GITHUB_ACTIONS=true)
python manage.py test

# Explicit override
export DJANGO_ENV=ci
python manage.py test
```

**CI settings include:**
- In-memory SQLite database (`:memory:`)
- Synchronous Celery (no broker needed)
- Console-only logging
- Fast password hashers
- Minimal middleware
- No external services required

### Production Deployment

```bash
# Auto-detected in production (GAE_APPLICATION, K_SERVICE, etc.)
gunicorn bus_kiosk_backend.wsgi:application

# Explicit override
export DJANGO_ENV=production
gunicorn bus_kiosk_backend.wsgi:application
```

**Production settings require:**
- `SECRET_KEY` environment variable (fails if not set)
- `ENCRYPTION_KEY` environment variable (fails if not set)
- PostgreSQL database (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`)
- Redis cache (`REDIS_URL`)
- Celery broker (`CELERY_BROKER_URL`)
- Google Maps API Key (`GOOGLE_MAPS_API_KEY`)
- Firebase service account (`FIREBASE_SERVICE_ACCOUNT_KEY_PATH`)

**Production settings enforce:**
- DEBUG=False (hard-coded, cannot be overridden)
- HTTPS enforcement (SECURE_SSL_REDIRECT=True)
- HSTS (1 year)
- HTTPS-only CORS origins
- No localhost in ALLOWED_HOSTS
- PostgreSQL database (SQLite rejected)
- Redis required (in-memory cache rejected)

## Environment Variables

### Required in Production

```bash
# Security
SECRET_KEY=<django-secret-key>
ENCRYPTION_KEY=<fernet-encryption-key>

# Database (PostgreSQL)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=<database-name>
DB_USER=<database-user>
DB_PASSWORD=<database-password>
DB_HOST=<database-host>
DB_PORT=5432

# Redis (Cache + Celery + Channels)
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0

# External Services
GOOGLE_MAPS_API_KEY=<api-key>
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=<path-to-service-account-json>
```

### Optional Overrides

```bash
# Environment override (local, ci, production)
DJANGO_ENV=production

# Additional allowed hosts (comma-separated)
ALLOWED_HOSTS=example.com,www.example.com

# Additional CSRF trusted origins (comma-separated)
CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com

# Logging (set to "true" to enable file logging)
USE_FILE_LOGGING=true
```

## Migration from Old Settings

**Old structure (anti-pattern):**
```
bus_kiosk_backend/
├── settings.py              # ❌ Monolithic
├── dev_settings.py          # ❌ Imports from settings.py
├── prod_settings.py         # ❌ Partial overrides
├── production_settings.py   # ❌ Duplicate/confusing
├── test_settings.py         # ❌ Separate imports
└── settings_backup.py       # ❌ Technical debt
```

**New structure (Fortune 500 pattern):**
```
bus_kiosk_backend/settings/
├── __init__.py      # ✅ Auto-detection
├── base.py          # ✅ Single source of truth
├── local.py         # ✅ Inherits from base
├── ci.py            # ✅ Inherits from base
└── production.py    # ✅ Inherits from base
```

## Benefits

1. **DRY Principle**: Common settings in one place ([base.py](base.py))
2. **Auto-Detection**: No manual settings file specification needed
3. **Security**: .env files NEVER used in production
4. **Fail-Fast**: Production settings validate required environment variables
5. **Industry Standard**: Used by Django Two Scoops, Cookiecutter Django, Fortune 500 companies
6. **12-Factor App**: Environment-based configuration, no secrets in code

## Verification

```bash
# Check settings load correctly
python manage.py check

# Verify environment detection
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bus_kiosk_backend.settings'); import django; django.setup(); from django.conf import settings; print(f'Environment: {settings.ENVIRONMENT}')"

# Test with different environments
DJANGO_ENV=local python manage.py check
DJANGO_ENV=ci python manage.py check
```

## Troubleshooting

### Production deployment fails with "SECRET_KEY not found"

**Problem**: Environment variable not injected properly.

**Solution**: Verify environment variables are set in your deployment platform:
- GCP: Check Secret Manager and service configuration
- Kubernetes: Verify secrets and configmaps
- Docker: Check docker-compose.yml or environment variables

### Local development loads wrong settings

**Problem**: DJANGO_ENV or CI environment variables set globally.

**Solution**: Unset override variables:
```bash
unset DJANGO_ENV
unset GITHUB_ACTIONS
```

### Tests fail with "Production requires PostgreSQL"

**Problem**: Tests are loading production settings instead of CI settings.

**Solution**: Set DJANGO_ENV=ci in test runner:
```bash
DJANGO_ENV=ci python manage.py test
```

## References

- [Django Two Scoops](https://www.feldroy.com/books/two-scoops-of-django-3-x)
- [12-Factor App](https://12factor.net/)
- [Django Settings Documentation](https://docs.djangoproject.com/en/stable/topics/settings/)
- [Cookiecutter Django](https://github.com/cookiecutter/cookiecutter-django)
