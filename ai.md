# Backend Knowledge (AI.md)

This file captures the essential knowledge about the `backend_easy` Django backend. Store architectural decisions, setup steps, deployment notes, and operational runbooks here so the team (and any AI assistants) can act consistently.

## Table of contents

- Overview
- Project structure
- Current status and completed work
- How to run locally
- Dependency management
- API conventions and versioning
- Authentication and security
- Observability and monitoring
- Background processing
- Caching and performance
- Database and migrations
- Testing and CI
- Common troubleshooting
- Contact / maintainers

## Overview

The backend is an industrial Django application providing a REST API for the Bus Kiosk face recognition system. It uses Django 5.x and Django REST Framework (DRF) for API endpoints, Simple JWT for auth, and Celery for background processing.

Key features:

- JWT authentication (refresh tokens)
- DRF viewsets and serializers
- OpenAPI docs via drf-spectacular
- Prometheus metrics, structured JSON logging
- PostgreSQL production-ready configuration
- Redis for caching and Celery broker
- Role-based permissions and PII encryption
- Comprehensive test coverage (28/28 tests passing)

## Project structure

- `bus_kiosk_backend/` - Django project settings, WSGI/ASGI, middleware, exceptions
- `users/` - Custom user model with roles, auth endpoints, API keys
- `students/` - Student models with encrypted PII, school relationships
- `buses/` - Bus and Route models with utilization tracking, assignment APIs
- `events/` - Boarding events and attendance records with ULID generation
- `kiosks/` - Kiosk and device log models
- `imperial_governance/` - Governance/SSOT (single source of truth), constitution validation
- `logs/` - Application logs directory
- `pyproject.toml` - Project metadata and dependencies
- `.venv/` - Virtual environment (ignored in git)

## Current status and completed work

**Status**: Production-ready Django backend with all tests passing (28/28).

**Completed work**:

- Full Django apps implemented: users, students, buses, events, kiosks
- REST APIs for all entities with proper serialization and validation
- JWT authentication with role-based access control
- PII encryption for sensitive student data
- ULID generation for boarding events
- Bulk operations for student assignments and boarding events
- Comprehensive test suite with Factory Boy fixtures
- Security middleware and rate limiting
- Monitoring with Prometheus metrics and structured logging
- Celery background processing setup
- Redis caching configuration
- OpenAPI documentation generation
- Database migrations and schema design
- Custom exception handling and middleware

**OpenAPI Specification**: The canonical API file `openapi.yaml` has been generated using drf-spectacular and contains complete API documentation including:

- All endpoint paths with HTTP methods
- Request/response schemas with field validation
- Authentication requirements (JWT Bearer tokens)
- Server configurations for development and production
- Comprehensive component schemas for all data models

**Recent fixes**:

- Resolved User creation requiring roles
- Fixed Student creation with required school fields
- Eliminated circular import issues
- Generated missing database migrations
- Configured URL patterns for all apps
- Fixed ULID import and generation
- Updated serializers for event_id inclusion
- Corrected permission imports and dependencies

**Technical stack**:

- Django 5.0+ with DRF 3.15+
- PostgreSQL with connection pooling
- Redis for caching and Celery broker
- JWT authentication with refresh tokens
- PII encryption using cryptography library
- ULID for event identifiers
- Comprehensive middleware stack
- Full test coverage with pytest

## How to run locally

1. Create virtualenv and install deps

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install -e ".[dev]"
```

2. Set environment variables (use `.env` or environment)

```bash
DB_NAME=bus_kiosk
DB_USER=bus_kiosk_user
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379/0
SECRET_KEY=changeme
DEBUG=True
```

3. Run migrations and start server

```powershell
python manage.py migrate
python manage.py runserver
```

4. Run Celery locally (optional)

```powershell
celery -A bus_kiosk_backend worker -l info
celery -A bus_kiosk_backend beat -l info
```

## Dependency management

- Managed with `pyproject.toml` and `setuptools`.
- Install production deps: `pip install -e .`
- Install dev deps: `pip install -e ".[dev]"`

## API conventions and versioning

- Base path: `/api/v1/`
- Versioning: `Accept` header versioning (`Accept: application/json;version=v1`)
- Response format: JSON
- Error format: standardized via `bus_kiosk_backend.exceptions.custom_exception_handler`
- Auth: `Authorization: Bearer <JWT>`

## Authentication and security

- Custom `AUTH_USER_MODEL` is `users.User` with role-based permissions.
- Use `rest_framework_simplejwt` for token issuance and refresh.
- Rate limiting configured via DRF throttles with scoped rates for sensitive endpoints.
- Security headers enforced by `bus_kiosk_backend.middleware.SecurityHeadersMiddleware`.
- PII encryption for student data using Fernet symmetric encryption.

## Observability and monitoring

- Prometheus metrics at `/metrics/` (requires `django-prometheus`).
- Health checks at `/health/` and `/health/detailed/`.
- Structured JSON logging via `python-json-logger` and rotating files.
- Request tracing via `RequestLoggingMiddleware` (adds `X-Request-ID`).

## Background processing

- Celery configured with Redis broker and `django_celery_beat` for scheduled tasks.
- Results persisted via `django_celery_results`.

## Caching and performance

- Redis cache backend configured with `django-redis`.
- Example `api_cache` namespace for endpoint caching.
- Use `select_related` and `prefetch_related` to optimize queries.

## Database and migrations

- Production DB: PostgreSQL (configured in settings).
- Use `psycopg2-binary` driver.
- Connection pooling via `CONN_MAX_AGE` and health checks.
- UUID primary keys for all models.
- Proper indexing on foreign keys and frequently queried fields.

## Testing and CI

- Tests use `pytest` + `pytest-django`.
- Type checking with `mypy` and stubs.
- Linting and formatting with `ruff` and `black`.
- Pre-commit configured for local hooks.
- All 28 tests currently passing with comprehensive coverage.

## Common troubleshooting

- If migrations fail: run `python manage.py makemigrations` then `migrate`.
- If Celery can't connect: check `REDIS_URL` and network.
- Debug logs: `logs/django.log` and `logs/api.log` (ensure logs/ is writable).
- If tests fail: ensure test database is clean, check fixture data.

## Contact / maintainers

- Team: Imperial Bus Kiosk Team <team@imperial-easypool.com>

---

Recorded on: 2025-10-04

Maintainers should update this file as architecture decisions change.
