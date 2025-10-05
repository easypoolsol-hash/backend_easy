# Test Suite Organization (Fortune 500 Pattern)

**Centralized test structure organized by test type, not by app.**

## 📁 Structure

```
tests/
├── conftest.py           # Shared fixtures (reusable test data)
├── unit/                 # Fast, isolated tests (no external dependencies)
├── integration/          # API + database tests
└── e2e/                  # End-to-end workflow tests
```

## 🎯 Test Categories

### 1. Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Speed**: Fast (< 100ms per test)
- **Database**: Minimal or mocked
- **Example**: `test_kiosk_auth.py` - Tests authentication logic

### 2. Integration Tests (`tests/integration/`)
- **Purpose**: Test API endpoints with database
- **Speed**: Medium (< 1s per test)
- **Database**: Real database (test DB)
- **Example**: `test_kiosk_api.py` - Tests JWT-protected endpoints

### 3. E2E Tests (`tests/e2e/`)
- **Purpose**: Test complete workflows
- **Speed**: Slow (1-5s per test)
- **Database**: Full stack with real data flow
- **Example**: `test_kiosk_workflow.py` - Tests auth → heartbeat → log

## 🚀 Running Tests

### Run All Tests (Recommended)
```bash
pytest tests/ -v
```

### Run Test Pyramid (Fortune 500 Pattern)
```bash
# Run in order: Unit → Integration → E2E (fail fast)
pytest tests/unit/ -v && \
pytest tests/integration/ -v && \
pytest tests/e2e/ -v
```

### Run Specific Category
```bash
pytest tests/unit/           # Fast unit tests only (< 100ms each)
pytest tests/integration/    # Integration tests only (< 1s each)
pytest tests/e2e/            # E2E tests only (1-5s each)
```

### Run with Coverage (60% threshold)
```bash
pytest tests/ --cov=kiosks --cov=buses --cov=students --cov=events --cov=users --cov=bus_kiosk_backend \
  --cov-report=term-missing --cov-fail-under=60
```

### Run Specific Test File
```bash
pytest tests/unit/test_kiosk_auth.py
```

### Run Specific Test
```bash
pytest tests/unit/test_kiosk_auth.py::TestKioskAuthentication::test_kiosk_auth_success
```

### Run with Coverage
```bash
pytest tests/ --cov=kiosks --cov-report=html
```

## ✅ Essential Tests (Current Coverage)

### Kiosk Authentication (`unit/test_kiosk_auth.py`)
- ✅ Valid credentials → JWT token
- ✅ Invalid API key → 400 error
- ✅ Nonexistent kiosk → 400 error
- ✅ Inactive kiosk → 400 error
- ✅ Missing fields → 400 error
- ✅ API key properly hashed
- ✅ JWT contains kiosk metadata

### Kiosk API Access (`integration/test_kiosk_api.py`)
- ✅ Heartbeat with valid token → Success
- ✅ Heartbeat without token → 403 Forbidden
- ✅ User token cannot access kiosk endpoints
- ✅ Health endpoint accessible without auth

### Complete Workflow (`e2e/test_kiosk_workflow.py`)
- ✅ Auth → Heartbeat → Log (end-to-end)
- ✅ Workflow fails without authentication

## 🔧 Shared Fixtures & Factories

### Fixtures (conftest.py)
Reusable test data available to all tests:

- `api_client` - API client for requests
- `test_school` - Test school instance
- `test_bus` - Test bus instance
- `test_kiosk` - Test kiosk with credentials (returns kiosk + plaintext API key)
- `test_student` - Test student with encrypted data
- `test_parent` - Test parent with encrypted PII
- `test_user` - Test user with role
- `authenticated_client` - API client with user auth

### Factories (factories.py)
**Fortune 500 Pattern using Factory Boy** - Less code, more power!

```python
# Instead of manual creation:
school = School.objects.create(name="Test School")
bus = Bus.objects.create(license_plate="TEST-001", route=route, ...)

# Use factories (cleaner, less code):
school = SchoolFactory()
bus = BusFactory()  # Auto-creates related route!

# Create with specific values:
kiosk = KioskFactory(api_key="my-custom-key")
student = StudentFactory(plaintext_name="John Doe")  # Auto-encrypted!

# Access plaintext for assertions:
assert kiosk._api_key == "my-custom-key"
assert student._plaintext_name == "John Doe"
```

**Available Factories:**
- `SchoolFactory` - Creates schools
- `RouteFactory` - Creates routes
- `BusFactory` - Creates buses (with route)
- `KioskFactory` - Creates kiosks (with API key hashing)
- `StudentFactory` - Creates students (auto-encrypts name)
- `ParentFactory` - Creates parents (auto-encrypts PII)
- `StudentParentFactory` - Creates relationships
- `RoleFactory` - Creates roles
- `UserFactory` - Creates users (with password hashing)

## 📝 Adding New Tests

### 1. Identify Test Type
- **Unit**: Tests single function/class, no external deps
- **Integration**: Tests API endpoint + database
- **E2E**: Tests complete user/kiosk workflow

### 2. Create Test File
```python
# tests/unit/test_new_feature.py
import pytest

@pytest.mark.django_db
class TestNewFeature:
    def test_something(self, api_client, test_kiosk):
        # Use shared fixtures
        kiosk, api_key = test_kiosk

        # Write test
        response = api_client.post('/api/endpoint/', {...})
        assert response.status_code == 200
```

### 3. Use Existing Fixtures
See `conftest.py` for available fixtures. Don't recreate test data!

## 🔄 CI/CD Integration

Tests run automatically on:
- Every push to `master/main`
- Every pull request
- Manual workflow dispatch

**CI Pipeline**:
1. Run unit tests (fast feedback)
2. Run integration tests (if unit pass)
3. Run e2e tests (if integration pass)
4. Generate coverage report

## 💡 Best Practices

✅ **DO**:
- Use shared fixtures from `conftest.py`
- Write descriptive test names (`test_kiosk_auth_invalid_api_key`)
- Test happy path + error cases
- Keep tests independent (no order dependency)
- Use `@pytest.mark.django_db` for database tests

❌ **DON'T**:
- Recreate test data in every test (use fixtures!)
- Test implementation details (test behavior, not code)
- Write flaky tests (random failures)
- Make tests depend on each other
- Commit commented-out tests

## 🎯 Test Coverage

**Current Coverage: 62%** ✅

### Coverage Breakdown:
- **Kiosk Authentication**: 93% (Excellent)
- **Kiosk API Views**: 82% (Good)
- **Serializers**: 60-93% (Good)
- **Core Auth/Security**: 95-100% (Excellent)
- **Overall System**: 62% (Good for essential tests)

### Coverage Goals:
- **Unit Tests**: Core business logic (auth, encryption, validation)
- **Integration Tests**: API endpoints + database operations
- **E2E Tests**: Critical user workflows
- **Minimum Threshold**: 60% (enforced in CI)

**Strategy**: Test what matters (critical paths), expand incrementally.

---

**This is a Fortune 500 pattern: Centralized, organized, scalable. Add more tests incrementally!**
