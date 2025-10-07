# Permission Mapping: Where Permissions Are Assigned

**Date:** October 7, 2025
**Security Model:** Deny-by-default (no generic `IsAuthenticated` on core endpoints)

---

## 📋 Permission Classes Defined

**Location:** `backend_easy/app/bus_kiosk_backend/permissions.py`

### 1. `IsKiosk`
- **Allows:** ONLY kiosk devices with valid JWT token (type='kiosk')
- **Denies:** Everyone else (users, unauthenticated, invalid tokens)

### 2. `IsSchoolAdmin`
- **Allows:** ONLY authenticated users with `role.name=='school_admin'`
- **Denies:** Everyone else (kiosks, parents, teachers, unauthenticated)

---

## 🗺️ Permission Assignment Map

### 🔧 **Kiosk Endpoints** (Use `IsKiosk`)

**File:** `backend_easy/app/kiosks/views.py`

| Endpoint | Permission | Line | Function |
|----------|-----------|------|----------|
| `POST /api/v1/auth/` | `AllowAny` | 43 | `kiosk_auth()` |
| `POST /api/v1/{kiosk_id}/heartbeat/` | `IsKiosk` | 188 | `kiosk_heartbeat()` |
| `POST /api/v1/logs/` | `IsKiosk` | 249 | `kiosk_log()` |
| `GET /api/v1/{kiosk_id}/check-updates/` | `IsKiosk` | 335 | `check_updates()` |
| `GET /api/v1/{kiosk_id}/snapshot/` | `IsKiosk` | 395 | `download_snapshot()` |
| `POST /api/v1/{kiosk_id}/heartbeat/` (v2) | `IsKiosk` | 454 | `heartbeat()` |

**Kiosk Permissions Summary:**
```python
# Authentication (public)
@permission_classes([AllowAny])
def kiosk_auth(request):
    """Any device can authenticate"""

# All other kiosk endpoints
@permission_classes([IsKiosk])
def kiosk_heartbeat(request):
    """Only authenticated kiosks"""
```

---

### 👨‍💼 **Admin Endpoints** (Use `IsSchoolAdmin`)

#### **Students App**
**File:** `backend_easy/app/students/views.py`

| ViewSet/Endpoint | Permission | Line | Methods |
|------------------|-----------|------|---------|
| `SchoolViewSet` | `IsSchoolAdmin` | 34 | GET, POST, PUT, DELETE `/api/v1/schools/` |
| `BusViewSet` | `IsSchoolAdmin` | 40 | GET, POST, PUT, DELETE `/api/v1/buses/` |
| `StudentViewSet` | `IsSchoolAdmin` | 53 | GET, POST, PUT, DELETE `/api/v1/students/` |
| `ParentViewSet` | `IsSchoolAdmin` | 130 | GET, POST, PUT, DELETE `/api/v1/parents/` |
| `StudentParentViewSet` | `IsSchoolAdmin` | 153 | GET, POST, PUT, DELETE `/api/v1/student-parents/` |
| `StudentPhotoViewSet` | `IsSchoolAdmin` | 193 | GET, POST, PUT, DELETE `/api/v1/student-photos/` |

**Student Management Permissions:**
```python
class StudentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSchoolAdmin]  # Only school admins
    # All CRUD operations require IsSchoolAdmin
```

---

#### **Buses App**
**File:** `backend_easy/app/buses/views.py`

| ViewSet | Permission | Line | Endpoints |
|---------|-----------|------|-----------|
| `RouteViewSet` | `IsSchoolAdmin` | 20 | `/api/v1/routes/*` |
| `BusViewSet` | `IsSchoolAdmin` | 65 | `/api/v1/buses/*` |

**Bus Management Permissions:**
```python
class BusViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSchoolAdmin]  # Only school admins
```

---

#### **Kiosks Management**
**File:** `backend_easy/app/kiosks/views.py`

| ViewSet | Permission | Line | Endpoints |
|---------|-----------|------|-----------|
| `KioskViewSet` | `IsSchoolAdmin` | 135 | `/api/v1/kiosks/*` (management) |
| `DeviceLogViewSet` | `IsSchoolAdmin` | 304 | `/api/v1/device-logs/*` |

**Kiosk Management Permissions:**
```python
class KioskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSchoolAdmin]  # Only admins can manage kiosks
    # Kiosks cannot create/update/delete other kiosks
```

---

### ⚠️ **Endpoints Still Using Generic `IsAuthenticated`** (Need Review)

#### **Events App**
**File:** `backend_easy/app/events/views.py`

| Endpoint | Current Permission | Line | Should Be? |
|----------|-------------------|------|------------|
| Boarding events | `IsAuthenticated` | 27 | `IsKiosk` (kiosks create boarding events) |
| Event management | `IsAuthenticated` | 87 | `IsSchoolAdmin` (admins view events) |

**Action needed:** Determine correct permission for boarding events.

---

#### **Users App**
**File:** `backend_easy/app/users/views.py`

| ViewSet | Current Permission | Line | Should Be? |
|---------|-------------------|------|------------|
| User management #1 | `IsAuthenticated` | 23 | `IsSchoolAdmin` |
| User management #2 | `IsAuthenticated` | 28 | `IsSchoolAdmin` |
| User management #3 | `IsAuthenticated` | 97 | `IsSchoolAdmin` |
| User management #4 | `IsAuthenticated` | 137 | `IsSchoolAdmin` |

**Action needed:** Update user endpoints to use role-based permissions.

---

## 📊 Permission Distribution

| Permission Class | Count | Usage |
|------------------|-------|-------|
| `IsKiosk` | 6 endpoints | Kiosk-only operations (sync, heartbeat, logs) |
| `IsSchoolAdmin` | 10 ViewSets | Admin-only operations (student/bus/kiosk management) |
| `AllowAny` | 1 endpoint | Public authentication endpoint |
| `IsAuthenticated` ⚠️ | 6 endpoints | **NEEDS REVIEW** (too generic) |

---

## 🎯 Permission Logic Flow

### Example 1: Student List Request

```
Request: GET /api/v1/students/
    ↓
StudentViewSet: permission_classes = [IsSchoolAdmin]
    ↓
IsSchoolAdmin.has_permission(request, view):
    ↓
    1. request.user.is_authenticated?
       → NO: Return False (401 Unauthorized)
       → YES: Continue
    ↓
    2. hasattr(request.user, 'role')?
       → NO: Return False (403 Forbidden)
       → YES: Continue
    ↓
    3. request.user.role.name == 'school_admin'?
       → NO: Return False (403 Forbidden) ← Kiosks fail here!
       → YES: Return True (200 OK) ← Only admins pass!
```

### Example 2: Kiosk Heartbeat Request

```
Request: POST /api/v1/{kiosk_id}/heartbeat/
    ↓
kiosk_heartbeat(): @permission_classes([IsKiosk])
    ↓
IsKiosk.has_permission(request, view):
    ↓
    1. Validate JWT token?
       → Invalid: Return False (401 Unauthorized)
       → Valid: Continue
    ↓
    2. token.get('type') == 'kiosk'?
       → NO: Return False (403 Forbidden) ← Admins fail here!
       → YES: Continue
    ↓
    3. Kiosk exists and is_active?
       → NO: Return False (403 Forbidden)
       → YES: Return True (200 OK) ← Only kiosks pass!
```

---

## 🔍 How to Find Permission for Specific Endpoint

### Method 1: Search by URL Pattern

```bash
# Find which view handles /api/v1/students/
grep -r "students" backend_easy/app/**/urls.py

# Check permission in that view file
grep "permission_classes" backend_easy/app/students/views.py
```

### Method 2: Search by ViewSet Name

```python
# In students/views.py
class StudentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSchoolAdmin]  # ← Permission here!
```

### Method 3: Search by Function Name

```python
# In kiosks/views.py
@api_view(['POST'])
@permission_classes([IsKiosk])  # ← Permission here!
def kiosk_heartbeat(request):
    pass
```

---

## 📝 Adding New Permissions

### Step 1: Define Permission Class

**File:** `bus_kiosk_backend/permissions.py`

```python
class IsTeacher(BasePermission):
    """Allow only teachers"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not hasattr(request.user, 'role'):
            return False
        return request.user.role.name == 'teacher'
```

### Step 2: Apply to View

**File:** `students/views.py`

```python
from bus_kiosk_backend.permissions import IsTeacher

class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsTeacher]  # Teachers can view attendance
```

### Step 3: Update This Document

Add new permission to the mapping tables above.

---

## 🔒 Security Checklist

✅ **No generic `IsAuthenticated` on admin endpoints** (students, schools, buses)
✅ **Kiosks use explicit `IsKiosk` permission**
✅ **Admin operations use explicit `IsSchoolAdmin` permission**
✅ **Public endpoints use explicit `AllowAny` permission**
⚠️ **Events and Users apps still need review**

---

## 📚 References

- **Permission Classes:** `backend_easy/app/bus_kiosk_backend/permissions.py`
- **Student Views:** `backend_easy/app/students/views.py`
- **Bus Views:** `backend_easy/app/buses/views.py`
- **Kiosk Views:** `backend_easy/app/kiosks/views.py`
- **Django Permissions Docs:** https://www.django-rest-framework.org/api-guide/permissions/

---

**Last Updated:** October 7, 2025
