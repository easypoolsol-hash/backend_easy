# Bus Kiosk Backend

A Django-based backend service for bus kiosk management system with auto-generated OpenAPI client.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)

### Development Setup
```bash
# 1. Clone and setup
./bin/dev-setup.sh

# 2. Run quality checks
./bin/quality-check.sh

# 3. Run tests
./bin/run-tests.sh

# 4. Start development server
cd app && python manage.py runserver
```

### Full CI Pipeline (before pushing)
```bash
./bin/ci-local.sh
```

## 📁 Project Structure

```
backend_easy/
├── app/                    # Django application code
│   ├── bus_kiosk_backend/  # Main Django project
│   ├── users/             # User management app
│   ├── students/          # Student management app
│   ├── buses/             # Bus management app
│   ├── kiosks/            # Kiosk management app
│   └── tests/             # Test suite
├── bin/                    # Executable scripts (CI/CD, development)
├── config/                 # Configuration files
│   ├── pyproject.toml     # Python project config
│   ├── mypy.ini          # Type checking config
│   └── Makefile           # Build tasks
├── doc/                    # Documentation
│   ├── ai.md             # AI/ML documentation
│   ├── CI_REFACTOR.md    # CI/CD improvements
│   ├── LINTING_README.md # Code quality guide
│   ├── task.md           # Project planning
│   └── openapi.yaml      # API specification
├── build/                  # Build artifacts (generated)
│   ├── coverage.xml       # Test coverage reports
│   ├── .coverage         # Coverage data
│   └── logs/             # Application logs
├── infrastructure/         # Production deployment
│   ├── docker-compose.prod.yml
│   ├── docker-compose.monitoring.yml
│   ├── deploy.sh         # Production deployment script
│   └── nginx/            # Nginx configuration
├── imperial_governance/    # Architecture & governance docs
├── tools/                  # Development utilities (future)
├── docker-compose.yml      # Local development
└── Dockerfile             # Container build
```

## 🛠️ Development Workflow

### Code Quality
```bash
# Run all quality checks
./bin/quality-check.sh

# Fix formatting automatically
ruff check --fix .
```

### Testing
```bash
# Run tests with coverage
./bin/run-tests.sh

# Run specific test
cd app && python manage.py test users.tests.UserModelTest
```

### Docker Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Run commands in container
docker-compose exec web python manage.py shell
```

## 🚢 Deployment

### Local Testing
```bash
# Test full CI pipeline locally
./bin/ci-local.sh

# Run only unit tests
./bin/run-tests.sh
```

### Production Deployment
Deployments are handled via GitHub Actions CD pipeline:

1. **Manual trigger** from GitHub UI
2. **Tag management** (blue/green/staging/production)
3. **SSH deployment** to production server
4. **Zero-downtime updates** with health checks

## 📊 Monitoring & Health

- **Health endpoint**: `GET /health/`
- **Logs**: Available in `build/logs/`
- **Metrics**: Prometheus/Grafana (production)
- **Coverage**: Codecov integration

## 🔧 Configuration

### Environment Variables
```bash
# .env file should ONLY contain external/sensitive keys:
GOOGLE_MAPS_API_KEY=your-google-maps-key
STRIPE_SECRET_KEY=your-stripe-secret
EXTERNAL_API_KEY=your-external-api-key

# Local development defaults are now in docker-compose.yml
# No need to set DEBUG, DB credentials, Redis URLs in .env for local dev
```

### Python Dependencies
Managed via `config/pyproject.toml`:

- **Core**: Django, DRF, PostgreSQL, Redis
- **Dev**: pytest, ruff, mypy, coverage
- **Prod**: gunicorn, whitenoise

## 🤝 Contributing

1. **Setup**: `./bin/dev-setup.sh`
2. **Develop**: Make changes in `app/`
3. **Test**: `./bin/ci-local.sh` before pushing
4. **Document**: Update relevant docs in `doc/`

## 📚 Documentation

- **API Docs**: `doc/openapi.yaml`
- **Architecture**: `imperial_governance/`
- **Development**: `doc/` directory
- **Scripts**: `bin/README.md`

## 🔐 Security

- **Fail-fast production**: Missing secrets cause immediate failure
- **Security scanning**: Trivy integration in CI
- **Dependency checks**: Automated vulnerability scanning
- **Code analysis**: Ruff security rules enabled

## 🏭 Industry Standards Implementation

### Fortune 500 Quality Assurance Pipeline

This backend implements enterprise-grade quality assurance practices:

#### 🔍 Code Quality Gates
- **Pre-commit hooks**: Automatic formatting, linting, and schema regeneration
- **Type checking**: MyPy with comprehensive Django stubs
- **Security scanning**: Bandit for security vulnerabilities
- **Import sorting**: Automated with isort/black integration

#### 🧪 Testing Strategy
- **Unit tests**: Model and utility function coverage
- **Integration tests**: API endpoint and workflow testing
- **Performance tests**: Benchmarking critical paths
- **Contract testing**: OpenAPI schema validation
- **Coverage requirements**: 85% minimum coverage

#### 🚀 CI/CD Pipeline
- **Quality checks**: Pre-commit, linting, security scanning
- **Multi-stage testing**: Unit → Integration → Performance
- **Coverage reporting**: Codecov integration
- **Automated deployment**: Blue/green with rollback capability

#### 📊 Monitoring & Observability
- **Health endpoints**: Comprehensive system health checks
- **Structured logging**: JSON logging with correlation IDs
- **Metrics collection**: Prometheus integration
- **Error tracking**: Sentry integration (production)

### Zero Drift Architecture

- **OpenAPI schema**: Auto-generated and validated
- **API client generation**: Automatic Flutter client updates
- **Contract testing**: Schema-driven test generation
- **Version management**: Semantic versioning with compatibility checks

### Security First Approach

- **JWT authentication**: Secure token-based auth
- **RBAC implementation**: Role-based access control
- **API key management**: Secure key rotation
- **Input validation**: Comprehensive request validation
- **Rate limiting**: DDoS protection
- **Audit logging**: Complete action tracking
# Test comment to trigger pre-commit hook
# Test Firebase IAM fix
