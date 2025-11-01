# F500 Logging & Singleton Pattern Plan

## Critical Singletons Needed

### 1. Firebase Admin ✅ DONE
**Location:** `settings/base.py`
```python
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
```

### 2. Redis Connection Pool
**Why:** Redis creates connection pools - multiple inits = resource leak
**Location:** `settings/base.py` or dedicated `redis_client.py`
```python
class RedisClient:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return cls._instance
```

### 3. Face Recognition ML Model
**Why:** Loading model is expensive (100MB+), should load once
**Location:** `students/services/face_recognition_service.py`
```python
class FaceRecognitionService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Load model once
            cls._model = load_face_recognition_model()
        return cls._instance
```

### 4. Celery App ✅ ALREADY SINGLETON
Django-Celery handles this automatically

### 5. Database Connections ✅ ALREADY HANDLED
Django ORM connection pooling handles this

---

## F500 Logging Strategy

### Industry Standard: Structured Logging

**Library:** `structlog` (used by Uber, Lyft, Stripe)

**Why:**
- JSON output → easy parsing by log aggregators (Cloud Logging, Datadog)
- Contextual data (request_id, user_id, trace_id)
- Performance metrics built-in
- Error classification

### Implementation

**1. Install:**
```bash
pip install structlog python-json-logger
```

**2. Configuration (`settings/base.py`):**
```python
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()  # JSON output
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

**3. Usage:**
```python
import structlog

logger = structlog.get_logger(__name__)

# Simple logging
logger.info("user_login", user_id=123, ip="1.2.3.4")

# With context
logger = logger.bind(request_id=request.id)
logger.info("processing_payment", amount=100, currency="USD")

# Error tracking
try:
    dangerous_operation()
except Exception as e:
    logger.error("operation_failed", error=str(e), exc_info=True)
```

**4. Output (JSON):**
```json
{
  "event": "user_login",
  "user_id": 123,
  "ip": "1.2.3.4",
  "level": "info",
  "timestamp": "2025-10-30T15:30:00Z",
  "logger": "users.views"
}
```

### Google Cloud Integration

**Use Google's `google-cloud-logging`:**
```python
import google.cloud.logging

client = google.cloud.logging.Client()
client.setup_logging()  # Auto-integrates with Cloud Logging
```

### Log Levels (F500 Pattern)

```python
# CRITICAL - System down, immediate action needed
logger.critical("database_offline", error=str(e))

# ERROR - Operation failed, but system continues
logger.error("payment_failed", user_id=123, amount=100)

# WARNING - Unexpected but handled
logger.warning("rate_limit_approaching", user_id=123, limit=1000)

# INFO - Important business events
logger.info("user_signup", user_id=123, plan="premium")

# DEBUG - Detailed diagnostic (disabled in production)
logger.debug("cache_hit", key="user:123", ttl=300)
```

### Context Managers (Advanced)

```python
from django.utils.log import log_response

@log_response
def process_payment(payment):
    logger = structlog.get_logger(__name__)
    logger = logger.bind(
        payment_id=payment.id,
        amount=payment.amount,
        user_id=payment.user_id
    )

    try:
        logger.info("payment_started")
        result = charge_card(payment)
        logger.info("payment_success", transaction_id=result.id)
        return result
    except Exception as e:
        logger.error("payment_failed", error=str(e), exc_info=True)
        raise
```

---

## Priority Implementation Order

### Phase 1 (Critical - DO NOW)
1. ✅ Firebase singleton (DONE)
2. Add structured logging to settings
3. Redis connection singleton
4. Face recognition model singleton

### Phase 2 (Important - NEXT SPRINT)
5. Add request_id middleware
6. Integrate with Google Cloud Logging
7. Add error tracking (Sentry)

### Phase 3 (Nice to have)
8. Performance metrics logging
9. Audit logging for sensitive operations
10. Log aggregation dashboard

---

## Example: Before vs After

### Before (Current)
```python
print("[STAGING] Staging settings loaded successfully")
print(f"[STAGING] DEBUG = {DEBUG}")
```

### After (F500 Pattern)
```python
logger = structlog.get_logger(__name__)
logger.info(
    "settings_loaded",
    environment="staging",
    debug=DEBUG,
    database="postgresql",
    cache="redis"
)
```

**Output (JSON in Cloud Logging):**
```json
{
  "event": "settings_loaded",
  "environment": "staging",
  "debug": true,
  "database": "postgresql",
  "cache": "redis",
  "level": "info",
  "timestamp": "2025-10-30T15:30:00Z"
}
```

**Benefits:**
- Easy to filter: `environment="staging" AND level="error"`
- Machine-readable
- No cluttered output
- Auto-indexed in Cloud Logging

---

## Files to Create/Modify

1. `app/core/logging.py` - Structured logging setup
2. `app/core/singletons.py` - Singleton base class
3. `app/core/middleware/logging_middleware.py` - Request ID tracking
4. `settings/base.py` - Update logging config
5. `requirements.txt` - Add structlog, google-cloud-logging

---

## Testing Strategy

1. Unit tests for singletons (verify single instance)
2. Load tests for Redis/ML model singletons (verify no resource leak)
3. Log output validation (ensure JSON format)
4. Cloud Logging integration test
