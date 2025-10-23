# ZERO-DRIFT ARCHITECTURE - KNOWLEDGE BASE

**Constitutional Principle for Backend ↔ Frontend Integration**

This document captures the proper way to connect backend and frontend with ZERO API drift, following the patterns established in `backend_easy` ↔ `bus_kiosk_easy` and `frontend_easy`.

---

## 🎯 CORE PRINCIPLE: Single Source of Truth (SSOT)

**Backend OpenAPI Specification is the ONLY source of truth for API contracts.**

```
Backend Code → OpenAPI Schema → Auto-Generate Frontend Client → Constitutional Enforcement
```

**NEVER:**
- ❌ Manually write API client code
- ❌ Hardcode API URLs in frontend
- ❌ Copy-paste API contracts
- ❌ Use Postman/Swagger as source of truth

**ALWAYS:**
- ✅ Backend generates OpenAPI schema automatically
- ✅ Git hooks auto-regenerate frontend clients
- ✅ Constitutional enforcement prevents violations
- ✅ Zero manual synchronization required

---

## 📋 THE RIGHT WAY: Step-by-Step Pattern

### 1. Backend Setup (Django REST Framework Example)

#### Install OpenAPI Schema Generator
```python
# requirements.txt
djangorestframework==3.15.2
drf-spectacular==0.28.0
```

#### Configure Django Settings
```python
# settings.py
INSTALLED_APPS = [
    'drf_spectacular',
    # ... other apps
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Your API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
```

#### Add Management Command Hook
```yaml
# backend/.pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: openapi-schema
        name: Regenerate OpenAPI Schema
        entry: python
        args: [app/manage.py, spectacular, --file, openapi-schema.yaml]
        language: system
        pass_filenames: false
        always_run: true
```

### 2. Copy Schema to Frontend(s)

```yaml
# backend/.pre-commit-config.yaml
- id: copy-schema-to-flutter
  name: Copy OpenAPI Schema to Flutter
  entry: powershell
  args: ["-Command", "Copy-Item openapi-schema.yaml ../your_frontend/openapi-schema.yaml -Force"]
  language: system
  pass_filenames: false
  always_run: true
```

### 3. Generate Frontend Client (CRITICAL PATTERN)

**🚨 USE EXACTLY THIS PATTERN - Learned from bus_kiosk_easy:**

```yaml
# backend/.pre-commit-config.yaml
- id: regenerate-your-frontend-api
  name: Regenerate Your Frontend API Client
  entry: powershell
  args: ["-Command", "cd ../your_frontend; npx @openapitools/openapi-generator-cli generate -i openapi-schema.yaml -g dart-dio -o packages/your_frontend_api --additional-properties=pubName=your_frontend_api,useEnumExtension=true,serializationLibrary=json_serializable; cd packages/your_frontend_api; flutter pub get; dart run build_runner build --delete-conflicting-outputs"]
  language: system
  pass_filenames: false
  always_run: true
```

**Why this specific pattern:**
- ✅ `dart-dio` generator (2025 industry standard for Flutter)
- ✅ `serializationLibrary=json_serializable` (lighter than built_value)
- ✅ `useEnumExtension=true` (modern Dart 3.0+ enum handling)
- ✅ Inline properties (NOT config file - backend controls generation)

### 4. Frontend Imperial Governance Setup

#### Create Governance Structure
```
your_frontend/
├── imperial_governance/
│   ├── pubspec.yaml                    # Tool dependencies
│   ├── analysis_options.yaml           # Linter config
│   ├── enforcement/
│   │   ├── constitutional_enforcement.dart
│   │   └── detectors/
│   │       ├── domain_specific/
│   │       │   └── zero_drift_api_detector.dart
│   │       └── sdk_version_consistency_detector.dart
│   └── README.md
```

#### Imperial Governance Dependencies
```yaml
# your_frontend/imperial_governance/pubspec.yaml
name: imperial_governance
environment:
  sdk: ">=3.9.0 <4.0.0"

dependencies:
  analyzer: ^8.4.0  # For AST-based code scanning
  yaml: ^3.1.2      # For contract parsing
  path: ^1.9.1      # Path utilities
```

### 5. Constitutional Pre-Commit Hook (Frontend)

```yaml
# your_frontend/.pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: constitutional-enforcement
        name: Constitutional Enforcement System
        entry: dart
        args: [run, imperial_governance/enforcement/constitutional_enforcement.dart]
        language: system
        pass_filenames: false
        always_run: true

      - id: verify-openapi-schema
        name: Verify OpenAPI Schema Exists
        entry: powershell
        args: ["-Command", "if (!(Test-Path 'openapi-schema.yaml')) { exit 1 }"]
        language: system
        pass_filenames: false
```

---

## 🛡️ CONSTITUTIONAL DETECTORS

### Zero-Drift API Detector

**Purpose:** Prevent hardcoded API URLs and raw HTTP calls

**What it detects:**
```dart
// ❌ VIOLATION - Hardcoded URL
await dio.get('/api/v1/students/');

// ❌ VIOLATION - Raw Dio call
await _dio.post('/api/v1/auth/login');

// ✅ CORRECT - Generated client
await _apiClient.studentsStudentsList();
```

**Implementation Pattern:**
- Use `package:analyzer` for AST-based scanning
- Scan `lib/services/`, `lib/repositories/`, `lib/data/`
- Regex pattern: `r'^/api/v\d+/'` for hardcoded URLs
- Check method invocations: `dio.get`, `dio.post`, etc.
- Exit code 1 on violations (blocks git commit)

### SDK Version Consistency Detector

**Purpose:** Ensure all packages use same Dart SDK version

**What it checks:**
```yaml
# All pubspec.yaml files must have:
environment:
  sdk: ">=3.9.0 <4.0.0"
```

**Why it matters:**
- Prevents `version solving failed` errors
- Ensures `null-aware-elements` feature availability
- Reproducible builds across team

---

## 📊 2025 BEST PRACTICES (VERIFIED)

### Generator Choice: `dart-dio` vs `dart`

**Research Result (Web Search Validated):**
- ✅ **USE: `dart-dio`** - Specifically designed for Flutter/Dart
- ✅ Uses Dio HTTP client (industry standard for Flutter 2025)
- ✅ Better integration with Flutter ecosystem
- ❌ DON'T USE: `dart` generator (generic, lacks Dio integration)

### Serialization Library: `json_serializable` vs `built_value`

**Research Result (Web Search Validated):**
- ✅ **USE: `json_serializable`** - Flutter's official recommendation
- ✅ Simpler, lighter, better performance
- ✅ Official Flutter docs use it as the example
- ✅ Works with `retrofit` and `dio` seamlessly
- ❌ `built_value` is for complex apps needing strict immutability (overkill for most)

### Additional Modern Patterns (Optional)
- ✅ `freezed` for immutable models (works WITH json_serializable)
- ✅ Dart 3.9.0+ for null-aware-elements feature
- ✅ `useEnumExtension: true` for modern enum handling

---

## 🚨 COMMON MISTAKES (AVOID THESE)

### Mistake 1: Using OpenAPI Generator Config File

**❌ WRONG:**
```yaml
# your_frontend/openapi-generator-config.yaml
generatorName: dart-dio
inputSpec: openapi-schema.yaml
# ... properties here
```

**Why wrong:** Config file can drift from backend hook

**✅ RIGHT:**
```yaml
# backend/.pre-commit-config.yaml
entry: npx @openapitools/openapi-generator-cli generate -i openapi-schema.yaml -g dart-dio --additional-properties=pubName=your_frontend_api,...
```

**Why right:** Backend controls the generation, single source of truth

### Mistake 2: Manual SDK Version in Generated Package

**❌ WRONG:** Manually editing `packages/your_frontend_api/pubspec.yaml` after generation

**✅ RIGHT:** Update SDK version programmatically in backend hook or use post-generation script

### Mistake 3: Trusting Config File Generator Name

**What we found:**
- bus_kiosk config file said `generatorName: dart`
- But backend hook actually uses `-g dart-dio`
- **Backend hook is the truth, not the config file!**

### Mistake 4: Not Running build_runner After Generation

**❌ WRONG:**
```bash
npx @openapitools/openapi-generator-cli generate ...
# Stop here
```

**✅ RIGHT:**
```bash
npx @openapitools/openapi-generator-cli generate ...
cd packages/your_frontend_api
flutter pub get
dart run build_runner build --delete-conflicting-outputs
```

**Why:** `json_serializable` needs build_runner to generate `.g.dart` files

---

## 📐 ARCHITECTURE PATTERNS

### Pattern 1: Generated Package Location

**Standard Location:**
```
your_frontend/
├── lib/                    # Your app code
├── packages/
│   └── your_frontend_api/  # Generated API client (separate package)
│       ├── lib/
│       ├── pubspec.yaml
│       └── ...
└── pubspec.yaml
```

**Why separate package:**
- ✅ Clear boundary between app and generated code
- ✅ Can have different SDK versions if needed
- ✅ Easier to `.gitignore` generated files
- ✅ Industry standard pattern

### Pattern 2: Git Ignore Strategy

**Option A: Commit Generated Code (Recommended)**
```gitignore
# Don't ignore packages/your_frontend_api/
# Commit the generated code for:
# - Faster CI builds (no regeneration needed)
# - Clear diffs when API changes
# - Works offline
```

**Option B: Ignore Generated Code**
```gitignore
# .gitignore
packages/your_frontend_api/
```
**Requires:** CI/CD must run backend hook before building frontend

**Our Choice:** Option A (commit generated code)

### Pattern 3: Mono-repo vs Multi-repo

**Mono-repo (Our Choice):**
```
project_root/
├── backend_easy/
├── bus_kiosk_easy/
└── frontend_easy/
```

**Advantages:**
- ✅ Backend hook can access all frontends easily
- ✅ Single git commit updates everything
- ✅ Atomic changes across stack

**Multi-repo Alternative:**
```
backend_repo/
  └── .pre-commit hooks push schema to artifact storage

frontend_repo/
  └── Download schema from artifact storage
```

---

## 🔄 WORKFLOW EXAMPLES

### Example 1: Adding New Backend Endpoint

**Backend Developer:**
```python
# backend_easy/app/students/views.py
class StudentAttendanceViewSet(viewsets.ModelViewSet):
    queryset = StudentAttendance.objects.all()
    serializer_class = StudentAttendanceSerializer
```

**What happens automatically:**
1. Developer commits code
2. Backend pre-commit hook runs:
   - Generates updated `openapi-schema.yaml`
   - Copies to `bus_kiosk_easy/` and `frontend_easy/`
   - Regenerates both API clients
   - Runs `build_runner` for JSON serialization
3. Git commit succeeds with updated schema + clients

**Frontend Developer:**
```bash
git pull  # Get latest changes
```

**New method available immediately:**
```dart
// No manual work - method exists now!
final attendance = await _apiClient.studentsStudentAttendanceList();
```

### Example 2: Changing Field Type (Breaking Change)

**Backend change:**
```python
# Before
age = models.CharField(max_length=3)

# After
age = models.IntegerField()
```

**What happens:**
1. Backend commits change
2. Schema regenerated with `age: integer` (was `age: string`)
3. Frontend clients regenerated
4. Frontend code using old type → **Compile error!**

```dart
// This now fails to compile:
String age = student.age;  // ❌ Error: int is not String

// Must fix to:
int age = student.age;  // ✅ Correct
```

**This is GOOD!** Compile-time error > Runtime crash

### Example 3: Frontend Tries to Hardcode URL

**Developer writes:**
```dart
// lib/services/custom_service.dart
final response = await dio.get('/api/v1/custom/endpoint/');
```

**What happens:**
1. Developer commits code
2. Frontend pre-commit hook runs
3. Zero-drift detector scans code
4. **VIOLATION DETECTED** - Commit blocked!

```
🚨 CONSTITUTIONAL VIOLATIONS DETECTED
❌ ERROR: no_hardcoded_api_urls
   📄 File: lib/services/custom_service.dart
   💬 Hardcoded API URL detected: "/api/v1/custom/endpoint/"
   💡 Use generated API client method instead
```

**Developer must fix:**
```dart
// Use generated client
final response = await _apiClient.customEndpointList();
```

---

## 🎓 CREATING A NEW FRONTEND

### Step-by-Step Checklist

**1. Create Flutter Project**
```bash
flutter create your_new_frontend
cd your_new_frontend
```

**2. Create Imperial Governance**
```bash
mkdir -p imperial_governance/enforcement/detectors/domain_specific
```

Copy governance structure from `frontend_easy/imperial_governance/`

**3. Update Backend Pre-Commit Hook**

Edit `backend_easy/.pre-commit-config.yaml`:
```yaml
- id: regenerate-your-new-frontend-api
  name: Regenerate Your New Frontend API Client
  entry: powershell
  args: ["-Command", "cd ../your_new_frontend; npx @openapitools/openapi-generator-cli generate -i openapi-schema.yaml -g dart-dio -o packages/your_new_frontend_api --additional-properties=pubName=your_new_frontend_api,useEnumExtension=true,serializationLibrary=json_serializable; cd packages/your_new_frontend_api; flutter pub get; dart run build_runner build --delete-conflicting-outputs"]
```

**4. Create Frontend Pre-Commit Hook**

Create `.pre-commit-config.yaml` (copy from `frontend_easy/`)

**5. Install Dependencies**
```bash
# Imperial Governance
cd imperial_governance
dart pub get
cd ..

# Frontend
flutter pub get
```

**6. Install Git Hooks**
```bash
# Backend (if not already installed)
cd backend_easy
pre-commit install

# Your Frontend
cd your_new_frontend
pre-commit install
```

**7. Test the Pipeline**
```bash
# Backend - trigger generation
cd backend_easy
git add .
git commit -m "test: trigger frontend generation"

# Check if your_new_frontend_api was generated
cd ../your_new_frontend/packages/your_new_frontend_api
ls lib/src/api/  # Should see generated API files
```

**8. Use Generated Client**
```dart
// lib/services/api_service.dart
import 'package:your_new_frontend_api/your_new_frontend_api.dart';
import 'package:dio/dio.dart';

class ApiService {
  late final Dio _dio;
  late final ApiApi _apiClient;

  ApiService() {
    _dio = Dio(BaseOptions(baseUrl: 'https://api.example.com'));
    _apiClient = ApiApi(_dio);
  }

  Future<List<Student>> getStudents() async {
    final response = await _apiClient.studentsStudentsList();
    return response.results ?? [];
  }
}
```

**9. Verify Constitutional Compliance**
```bash
cd your_new_frontend
dart run imperial_governance/enforcement/constitutional_enforcement.dart

# Should output:
# ✅ All detectors passed - Zero violations found
```

---

## 🔧 TROUBLESHOOTING

### Issue: "Missing openapi-schema.yaml"

**Cause:** Backend hasn't generated schema yet

**Solution:**
```bash
cd backend_easy
python app/manage.py spectacular --file openapi-schema.yaml
```

### Issue: "null-aware-elements feature not enabled"

**Cause:** SDK version < 3.8.0

**Solution:** Update generated package pubspec:
```yaml
environment:
  sdk: ">=3.9.0 <4.0.0"
```

### Issue: "build_runner failed with built_value errors"

**Cause:** Generator used `built_value` instead of `json_serializable`

**Solution:** Check backend hook uses:
```bash
--additional-properties=serializationLibrary=json_serializable
```

NOT:
```bash
--additional-properties=serializationLibrary=built_value
```

### Issue: "Import errors - package:openapi not found"

**Cause:** Package name in generated `pubspec.yaml` is wrong

**Solution:** Backend hook must specify correct `pubName`:
```bash
--additional-properties=pubName=your_frontend_api,...
```

### Issue: "Constitutional enforcement not running"

**Cause:** Pre-commit hooks not installed

**Solution:**
```bash
cd your_frontend
pre-commit install
pre-commit run --all-files  # Test manually
```

---

## 📚 REFERENCES & LEARNING RESOURCES

### Official Documentation
- OpenAPI Generator: https://openapi-generator.tech/docs/generators/dart-dio/
- DRF Spectacular: https://drf-spectacular.readthedocs.io/
- Flutter JSON Serialization: https://docs.flutter.dev/data-and-backend/serialization/json

### Why These Choices (Web Research Results)
1. **dart-dio over dart:** Specifically designed for Flutter, uses Dio HTTP client
2. **json_serializable over built_value:** Flutter's official recommendation, simpler, lighter
3. **Pre-commit hooks over manual:** Zero human discipline required, technical enforcement

### Internal References
- See: `backend_easy/.pre-commit-config.yaml` for complete backend hook
- See: `frontend_easy/imperial_governance/` for governance implementation
- See: `bus_kiosk_easy/` for original working pattern

---

## ✅ VERIFICATION CHECKLIST

Before considering a frontend "properly integrated":

- [ ] Backend pre-commit hook regenerates frontend client
- [ ] Frontend has Imperial Governance system
- [ ] Zero-drift API detector is active
- [ ] SDK version consistency detector is active
- [ ] Generated client uses `dart-dio` + `json_serializable`
- [ ] Frontend pre-commit hook blocks violations
- [ ] Manual test: Change backend → Frontend compiles without manual edits
- [ ] Manual test: Try hardcoded URL → Commit blocked
- [ ] Documentation: README explains the pipeline

---

## 🚨 CRITICAL REMINDERS

1. **Backend Hook is Source of Truth**
   - Config files can lie
   - Always check what backend hook actually runs

2. **dart-dio + json_serializable is 2025 Standard**
   - NOT dart generator
   - NOT built_value serialization

3. **Constitutional Enforcement is Mandatory**
   - Not optional
   - Technical barriers, not documentation
   - AI/humans cannot bypass

4. **Generated Code Should Be Committed**
   - Faster CI builds
   - Clear API change diffs
   - Works offline

5. **SDK Version Must Match**
   - All packages: `>=3.9.0 <4.0.0`
   - Required for null-aware-elements

---

**This knowledge was earned through:**
- Analyzing bus_kiosk_easy pattern
- Web research on dart-dio vs dart
- Web research on json_serializable vs built_value
- Trial and error with frontend_easy
- Constitutional principle enforcement

**Date:** 2025-01-24
**Status:** Production-Ready Pattern ✅
