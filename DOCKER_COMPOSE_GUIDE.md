# 🐳 Docker Compose Configuration Guide

This project uses Docker Compose for local development and CI testing with **production parity**.

## 📁 Files Overview

```
project/
├── docker-compose.yml              # Full local development stack
├── docker-compose.ci.yml           # CI testing configuration
├── .env.example                    # Example environment variables
├── .env.ci                         # CI environment variables
└── infrastructure/
    └── docker-compose.yml          # Production deployment (separate)
```

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Copy example environment file
cp .env.example .env

# 2. Edit .env with your local settings
nano .env

# 3. Start all services
docker-compose up

# 4. Access the application
# - Backend API: http://localhost:8000
# - Grafana: http://localhost:3000
# - Prometheus: http://localhost:9090
```

### Stop Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

---

## 🧪 Testing Locally (Like CI Does)

### Test the Docker Image

```bash
# 1. Build the Docker image
docker build -t bus_kiosk_backend:test .

# 2. Run CI tests locally
docker-compose -f docker-compose.ci.yml up --abort-on-container-exit

# 3. Clean up
docker-compose -f docker-compose.ci.yml down -v
```

This runs the **exact same tests** that GitHub Actions CI runs!

---

## 📦 What's Included

### `docker-compose.yml` (Local Development)

**Services:**
- ✅ **web**: Django application (port 8000)
- ✅ **db**: PostgreSQL 15 (port 5432)
- ✅ **redis**: Redis 7 (port 6379)
- ✅ **celery_worker**: Background task worker
- ✅ **celery_beat**: Scheduled tasks
- ✅ **prometheus**: Metrics collection (port 9090)
- ✅ **grafana**: Visualization dashboard (port 3000)
- ✅ **alertmanager**: Alert management (port 9093)
- ✅ **Exporters**: node, postgres, redis metrics

**Features:**
- 🔄 Hot reload (code changes reflect immediately)
- 📊 Full monitoring stack
- 🔍 Health checks on all services
- 💾 Persistent volumes for data
- 🌐 All ports exposed for debugging

---

### `docker-compose.ci.yml` (CI Testing)

**Services:**
- ✅ **backend**: Your Django app (built image)
- ✅ **postgres**: PostgreSQL 15 (test database)
- ✅ **redis**: Redis 7 (test cache)

**Features:**
- ⚡ Minimal services (faster startup)
- 🧪 Runs migrations + static collection + tests
- 🎯 Production parity (same versions as prod)
- ❌ No volumes (tests pre-built image)
- ✅ Health checks ensure services are ready

---

## 🔧 Environment Variables

### Local Development (.env)

```bash
# Django
DEBUG=True
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-32-byte-key-here

# Database
DB_NAME=bus_kiosk_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Application
ALLOWED_HOSTS=localhost,127.0.0.1
```

### CI Testing (.env.ci)

```bash
# Django
DEBUG=True
SECRET_KEY=test-secret-key-for-ci
ENCRYPTION_KEY=test-32-byte-encryption-key-ci

# Database (matches docker-compose.ci.yml)
DB_NAME=test_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=postgres  # ← Note: service name in docker-compose
DB_PORT=5432

# Redis (matches docker-compose.ci.yml)
REDIS_URL=redis://redis:6379/0
```

---

## 🎯 Production vs CI vs Local

| Aspect | Local Dev | CI Testing | Production |
|--------|-----------|------------|------------|
| **File** | `docker-compose.yml` | `docker-compose.ci.yml` | `infrastructure/docker-compose.yml` |
| **Services** | All + Monitoring | Backend + DB + Redis | Full stack |
| **Volumes** | Yes (hot reload) | No (test image) | Yes (persistence) |
| **Ports** | All exposed | None exposed | Reverse proxy only |
| **Purpose** | Development | Testing image | Serve users |
| **DEBUG** | True | True | False |

---

## 🛠️ Common Commands

### Development

```bash
# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f web

# Run Django commands
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py shell

# Rebuild image
docker-compose up --build

# Check service status
docker-compose ps
```

### Testing

```bash
# Run tests in CI environment
docker-compose -f docker-compose.ci.yml up --abort-on-container-exit

# View CI test logs
docker-compose -f docker-compose.ci.yml logs backend

# Clean up after tests
docker-compose -f docker-compose.ci.yml down -v
```

### Debugging

```bash
# Enter running container
docker-compose exec web bash

# Check database connection
docker-compose exec db psql -U postgres -d bus_kiosk_db

# Check Redis connection
docker-compose exec redis redis-cli ping

# View all container logs
docker-compose logs
```

---

## 🔍 Troubleshooting

### Services Won't Start

```bash
# Check if ports are in use
netstat -an | grep 8000
netstat -an | grep 5432
netstat -an | grep 6379

# Remove old containers
docker-compose down -v
docker system prune -a
```

### Database Connection Issues

```bash
# Wait for PostgreSQL to be ready
docker-compose logs db | grep "ready to accept connections"

# Check database exists
docker-compose exec db psql -U postgres -l
```

### Tests Fail in CI But Pass Locally

1. Check environment variables in `.env.ci`
2. Verify DB_HOST=postgres (service name, not localhost)
3. Ensure health checks pass before tests run
4. Check that migrations are running

---

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [12-Factor App Methodology](https://12factor.net/)
- [Django Docker Best Practices](https://docs.docker.com/samples/django/)

---

## 💡 Pro Tips

1. **Use `.env` files** - Never commit secrets to git
2. **Test locally before pushing** - Run `docker-compose -f docker-compose.ci.yml up`
3. **Clean volumes regularly** - `docker-compose down -v` to start fresh
4. **Monitor resources** - Check Docker Desktop for CPU/memory usage
5. **Use named volumes** - Persist data between container restarts

---

**Questions?** Check the main project README or ask in the team chat!
