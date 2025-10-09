# Running integration / performance tests (Docker Compose)

This project provides a `docker-compose.test.yml` that brings up test infrastructure (Postgres + Redis) on your machine for running heavy integration and performance tests.

Overview
- Lightweight tests (unit) run quickly on SQLite and are fine to run locally.
- Heavy integration tests (concurrency, DB transactions, cache chaos) should run against Postgres + Redis to avoid SQLite locking issues.
- `docker-compose.test.yml` exposes Postgres on localhost:5432 and Redis on localhost:6379 so the host Python test runner can use them.

Quick start (Windows PowerShell)

1. From the repo root (`backend_easy`) run the test runner script:

```powershell
# From repo root
.\scripts\run_integration_tests.ps1
```

This will:
- Start Docker Compose services defined in `docker-compose.test.yml` (db, redis, optional image smoke test)
- Wait for Postgres and Redis to become reachable on localhost
- Run Django migrations to prepare the test database
- Execute pytest on the host with coverage and then tear down the test containers

Customizing the test run
- Pass extra pytest args to the script:

```powershell
.\scripts\run_integration_tests.ps1 -PytestArgs "-q -k 'not slow' --maxfail=1 --cov=app"
```

CI notes (industry best practice)
- Run heavy tests in CI using Docker Compose or a job matrix that provides a Postgres service.
- Prefer ephemeral test DBs and use `--project-name` or `--project-directory` to isolate volumes between runs.
- Keep integration tests in their own marker (`@pytest.mark.integration`) and run those selectively in CI.

Troubleshooting
- If Postgres/Redis do not start, check Docker Desktop and ensure ports 5432/6379 are available on the host.
- If tests still fail due to cache/Redis exceptions, ensure your code gracefully handles cache failures (e.g., auditing/logging wrapped in try/except).

Next steps
- Add a GitHub Actions job that uses the `docker-compose.test.yml` to run integration tests in CI.
- Optionally add health-check waits in the PowerShell script to be more resilient to slow starts.
