# Kiosk API Status Report - Complete Analysis

**Date**: October 6, 2025
**Project**: Imperial EasyPool - Bus Kiosk System
**Architecture**: Offline-First with Snapshot Sync

---

## 📊 Executive Summary

| Status | Count | APIs |
|--------|-------|------|
| ✅ **Connected & Working** | 3 | Auth, Token Refresh, Heartbeat |
| ⏳ **Missing/Not Connected** | 3 | Snapshot Download, Boarding Upload, Logs Upload |
| ❌ **Redundant (Remove)** | 6 | Students, Face Embeddings, Buses, Routes, GPS, Face Upload |

---

## ✅ APIs Currently Connected (Working)

### 1. **Authentication** ✅
- **Endpoint**: `POST /api/v1/auth/`
- **Location**: `api_service.dart` (JWT interceptor)
- **Status**: ✅ **CONNECTED & WORKING**
- **Usage**: Login with kiosk credentials
- **Code**:
  ```dart
  // Automatic JWT token attachment in interceptor
  final accessToken = await AuthService.instance.getAccessToken();
  options.headers['Authorization'] = 'Bearer $accessToken';
  ```

### 2. **Token Refresh** ✅
- **Endpoint**: `POST /api/v1/auth/token/refresh/`
- **Location**: `api_service.dart._refreshTokens()`
- **Status**: ✅ **CONNECTED & WORKING**
- **Usage**: Refresh expired JWT tokens automatically
- **Code**:
  ```dart
  final response = await refreshDio.post<Map<String, dynamic>>(
    '/api/v1/auth/token/refresh/',
    data: {'refresh': refreshToken},
  );
  ```

### 3. **Device Heartbeat** ✅
- **Endpoint**: `POST /api/v1/kiosks/{kiosk_id}/heartbeat/`
- **Location**: `health_reporter.dart.reportHeartbeat()`
- **Status**: ✅ **CONNECTED & WORKING**
- **Usage**: Report device health metrics periodically
- **Code**:
  ```dart
  final response = await _apiClient.apiV1HeartbeatCreate2(
    kioskId: kioskId,
    heartbeat: heartbeat,
  );
  ```

### 4. **Check for Updates** ✅
- **Endpoint**: `GET /api/v1/kiosks/{kiosk_id}/check-updates/?last_sync={timestamp}`
- **Location**: `sync_service.dart._checkForUpdates()`
- **Status**: ✅ **CONNECTED & WORKING**
- **Usage**: Check if new snapshot available
- **Code**:
  ```dart
  final response = await _apiClient.apiV1CheckUpdatesRetrieve(
    kioskId: kioskId,
    lastSync: _lastSyncVersion,
  );
  ```

---

## ⏳ APIs Missing/Not Connected (Need Implementation)

### 5. **Snapshot Download** ⏳
- **Endpoint**: `GET /api/v1/kiosks/{kiosk_id}/snapshot/`
- **Backend**: ✅ **Implemented** (see `kiosks/views.py:download_snapshot`)
- **Frontend**: ❌ **NOT CONNECTED**
- **Status**: ⏳ **CRITICAL - NEEDS CONNECTION**
- **Issue**: Code references `updateInfo['download_url']` but actual snapshot endpoint not called
- **Current Code** (line 77 in sync_service.dart):
  ```dart
  final snapshotFile = await _downloadSnapshot(updateInfo['download_url'] as String);
  ```
- **What's Missing**:
  - Actual API call to `/api/v1/kiosks/{kiosk_id}/snapshot/`
  - Currently uses hardcoded download URL from check-updates response
  - Should use generated client method

**✅ HOW TO FIX**:
```dart
// Use generated API client to get snapshot download URL
final response = await _apiClient.apiV1SnapshotRetrieve(kioskId: kioskId);
final downloadUrl = response.data!.downloadUrl;
// Then download the actual SQLite file
```

### 6. **Boarding Events Upload (Bulk)** ⏳
- **Endpoint**: `POST /api/v1/boarding-events/bulk/`
- **Backend**: ✅ **Endpoint exists** (see `events/urls.py`)
- **Frontend**: ❌ **NOT CONNECTED**
- **Status**: ⏳ **CRITICAL - NEEDS CONNECTION**
- **Current Issue**: Manual method `recordBoarding()` in `api_service.dart` is **WRONG**
  - Uses wrong endpoint: `/boarding/` (should be `/api/v1/boarding-events/bulk/`)
  - Sends single event instead of bulk array
  - Not queued for offline upload

**Current WRONG Code** (line 134 in api_service.dart):
```dart
Future<Response<dynamic>> recordBoarding({
  required String studentId,
  required String kioskId,
  required double confidence,
}) async => _dio.post(
  '/boarding/',  // ❌ WRONG ENDPOINT
  data: {
    'student_id': studentId,
    'kiosk_id': kioskId,
    'confidence': confidence,
    'timestamp': DateTime.now().toIso8601String(),
  },
);
```

**✅ HOW TO FIX**:
1. Remove manual `recordBoarding()` method
2. Use generated client for bulk upload:
```dart
// Queue events locally, then upload in batch
final events = [
  BoardingEvent(
    studentId: '...',
    kioskId: kioskId,
    timestamp: DateTime.now(),
    confidence: 0.95,
  ),
  // ... more events
];

final response = await _apiClient.apiV1BoardingEventsBulkCreate(
  bulkBoardingEventRequest: BulkBoardingEventRequest(events: events),
);
```

### 7. **Device Logs Upload** ⏳
- **Endpoint**: `POST /api/v1/kiosks/{kiosk_id}/logs/`
- **Backend**: ✅ **Endpoint exists** (see `kiosks/views.py`)
- **Frontend**: ❌ **NOT CONNECTED**
- **Status**: ⏳ **IMPORTANT - NEEDS CONNECTION**
- **Usage**: Upload application logs for debugging

**✅ HOW TO FIX**:
```dart
// Collect logs and upload periodically
final logs = [
  LogEntry(
    timestamp: DateTime.now(),
    level: 'ERROR',
    message: 'Face detection failed',
    context: {'student_id': '...'},
  ),
];

final response = await _apiClient.apiV1LogsCreate(
  kioskId: kioskId,
  bulkLogRequest: BulkLogRequest(logs: logs),
);
```

---

## ❌ Redundant APIs (Should Remove)

These APIs are **redundant** because data is in the **snapshot** (local SQLite). Kiosks should **NOT** call these endpoints.

### 8. **Get Students** ❌
- **Endpoint**: `GET /api/v1/students/`
- **Location**: `api_service.dart.getStudents()`
- **Status**: ❌ **REDUNDANT - REMOVE**
- **Why**: Student data is in snapshot (SQLite `students` table)

**Current WRONG Code** (line 128):
```dart
Future<Response<dynamic>> getStudents() async => _dio.get<dynamic>('/students/');
```

**✅ CORRECT Approach**:
```dart
// Read from local snapshot instead
final students = await databaseService.getAllStudents();
```

**ACTION**: Delete `getStudents()` method from `api_service.dart`

### 9. **Get Face Embeddings** ❌
- **Endpoint**: `GET /api/v1/face-embeddings/` (NOW REMOVED FROM BACKEND!)
- **Status**: ❌ **REDUNDANT - ALREADY REMOVED FROM BACKEND**
- **Why**: Embeddings are in snapshot (SQLite `face_embeddings` table)

**✅ CORRECT Approach**:
```dart
// Read from local snapshot
final embeddings = await databaseService.getAllEmbeddings();
```

**ACTION**: No API client code exists (endpoint already removed)

### 10. **Upload Student Face** ❌
- **Endpoint**: `POST /students/faces/`
- **Location**: `api_service.dart.uploadStudentFace()`
- **Status**: ❌ **REDUNDANT - REMOVE**
- **Why**: Face embeddings are generated **server-side**, not by kiosks

**Current WRONG Code** (line 89):
```dart
Future<Response<dynamic>> uploadStudentFace({
  required String studentId,
  required List<int> imageBytes,
  required Map<String, double> faceEmbedding,
}) async {
  final formData = FormData.fromMap({
    'student_id': studentId,
    'image': MultipartFile.fromBytes(imageBytes, filename: 'face.jpg'),
    'embedding': faceEmbedding.toString(),
  });

  return _dio.post('/students/faces/', data: formData);
}
```

**Why This Is Wrong**:
- Kiosks should NOT generate or upload embeddings
- Embeddings must be generated server-side for quality control
- This endpoint doesn't even exist in backend!

**ACTION**: Delete `uploadStudentFace()` method from `api_service.dart`

### 11. **Upload GPS Location** ⚠️
- **Endpoint**: `POST /kiosks/location/`
- **Location**: `api_service.dart.uploadLocation()`
- **Status**: ❌ **REMOVED (May Need Later)**
- **Note**: Kiosks are **INSIDE BUSES (mobile)**, not stationary!

**Current WRONG Code** (line 104):
```dart
Future<Response<dynamic>> uploadLocation({
  required String kioskId,
  required double latitude,
  required double longitude,
  required double accuracy,
}) async => _dio.post(
  '/kiosks/location/',
  data: {
    'kiosk_id': kioskId,
    'latitude': latitude,
    'longitude': longitude,
    'accuracy': accuracy,
    'timestamp': DateTime.now().toIso8601String(),
  },
);
```

**Why This Was Removed**:
- This endpoint doesn't exist in backend (`/kiosks/location/`)
- GPS tracking was not in the original requirements

**BUT Consider Re-Adding**:
- Kiosks are **inside buses** (mobile, not stationary!)
- GPS tracking could be useful for:
  - Real-time bus location tracking
  - Route verification
  - Parent notifications ("Your child's bus is 5 minutes away")
  - Safety/security

**✅ HOW TO RE-ADD (If Needed)**:
1. Create backend endpoint: `POST /api/v1/kiosks/{kiosk_id}/location/`
2. Use generated API client
3. Queue GPS updates locally (upload every 30-60 seconds when online)

**ACTION**: Removed for now - discuss with team if GPS tracking needed

### 12. **Get Buses** ❌
- **Endpoint**: `GET /api/v1/buses/`
- **Status**: ❌ **REDUNDANT FOR KIOSKS**
- **Why**: Bus ID is in snapshot metadata

**✅ CORRECT Approach**:
```dart
// Read bus ID from snapshot metadata
final metadata = await databaseService.getMetadata();
final busId = metadata['bus_id'];
```

**ACTION**: No Flutter code uses this (good!)

### 13. **Get Routes** ❌
- **Endpoint**: `GET /api/v1/routes/`
- **Status**: ❌ **NOT NEEDED FOR KIOSKS**
- **Why**: Route information not needed for face recognition

**ACTION**: No Flutter code uses this (good!)

---

## 📋 Complete API Inventory

| # | Endpoint | Method | Backend | Frontend | Status | Action |
|---|----------|--------|---------|----------|--------|--------|
| 1 | `/api/v1/auth/` | POST | ✅ | ✅ | ✅ Connected | Keep |
| 2 | `/api/v1/auth/token/refresh/` | POST | ✅ | ✅ | ✅ Connected | Keep |
| 3 | `/api/v1/kiosks/{id}/heartbeat/` | POST | ✅ | ✅ | ✅ Connected | Keep |
| 4 | `/api/v1/kiosks/{id}/check-updates/` | GET | ✅ | ✅ | ✅ Connected | Keep |
| 5 | `/api/v1/kiosks/{id}/snapshot/` | GET | ✅ | ❌ | ⏳ Missing | **Connect** |
| 6 | `/api/v1/boarding-events/bulk/` | POST | ✅ | ❌ | ⏳ Missing | **Connect** |
| 7 | `/api/v1/kiosks/{id}/logs/` | POST | ✅ | ❌ | ⏳ Missing | **Connect** |
| 8 | `/api/v1/students/` | GET | ✅ | ❌ | ❌ Redundant | Remove |
| 9 | `/api/v1/face-embeddings/` | * | ❌ | ❌ | ❌ Removed | N/A |
| 10 | `/students/faces/` | POST | ❌ | ✅ | ❌ Invalid | **Delete** |
| 11 | `/kiosks/location/` | POST | ❌ | ✅ | ❌ Invalid | **Delete** |
| 12 | `/boarding/` | POST | ❌ | ✅ | ❌ Invalid | **Delete** |
| 13 | `/api/v1/buses/` | GET | ✅ | ❌ | ❌ Redundant | N/A |
| 14 | `/api/v1/routes/` | GET | ✅ | ❌ | ❌ Redundant | N/A |

---

## 🚀 Action Plan

### Priority 1: Connect Missing APIs (30 min)

#### Step 1: Connect Snapshot Download (10 min)
**File**: `bus_kiok/lib/services/sync/sync_service.dart`

```dart
// In _downloadSnapshot method, use generated client
Future<File> _downloadSnapshot(String kioskId) async {
  // Get snapshot download URL from API
  final response = await _apiClient.apiV1SnapshotRetrieve(kioskId: kioskId);
  final downloadUrl = response.data!.downloadUrl;
  final checksum = response.data!.checksum;

  // Download the actual SQLite file
  return await downloader.download(downloadUrl, checksum);
}
```

#### Step 2: Connect Boarding Events Upload (15 min)
**File**: `bus_kiok/lib/services/boarding_queue_service.dart` (create new)

```dart
class BoardingQueueService {
  final List<BoardingEvent> _queue = [];

  Future<void> queueEvent(BoardingEvent event) async {
    _queue.add(event);
    await _persistQueue(); // Save to local storage
  }

  Future<void> uploadQueuedEvents() async {
    if (_queue.isEmpty) return;

    final response = await _apiClient.apiV1BoardingEventsBulkCreate(
      bulkBoardingEventRequest: BulkBoardingEventRequest(events: _queue),
    );

    if (response.statusCode == 201) {
      _queue.clear();
      await _persistQueue();
    }
  }
}
```

#### Step 3: Connect Device Logs Upload (5 min)
**File**: `bus_kiok/lib/services/log_uploader_service.dart` (create new)

```dart
class LogUploaderService {
  Future<void> uploadLogs(String kioskId, List<LogEntry> logs) async {
    final response = await _apiClient.apiV1LogsCreate(
      kioskId: kioskId,
      bulkLogRequest: BulkLogRequest(logs: logs),
    );
  }
}
```

### Priority 2: Remove Redundant Code (15 min)

#### Step 1: Clean Up `api_service.dart`
**File**: `bus_kiok/lib/services/api_service.dart`

Delete these methods:
```dart
// ❌ DELETE line 89-98
uploadStudentFace() // REMOVE - server-side only

// ❌ DELETE line 104-115
uploadLocation() // REMOVE - not needed

// ❌ DELETE line 128-129
getStudents() // REMOVE - use snapshot instead

// ❌ DELETE line 131-141
recordBoarding() // REMOVE - use bulk upload instead
```

**Result**: File size reduces by ~50 lines, no dead code remains

---

## 🏗️ Final Architecture (After Cleanup)

### Kiosk Offline Mode (99% of time)
```
┌─────────────────────────────────────┐
│  LOCAL OPERATIONS                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  ✅ Read students from SQLite       │
│  ✅ Read embeddings from SQLite     │
│  ✅ Face recognition (local)        │
│  ✅ Queue boarding events (local)   │
│  ✅ Record logs (local)             │
└─────────────────────────────────────┘
```

### Kiosk Online Mode (Periodic Sync)
```
┌─────────────────────────────────────┐
│  API CALLS (MINIMAL)                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  1. Check for updates               │
│  2. Download new snapshot if needed │
│  3. Upload boarding events (bulk)   │
│  4. Upload logs (bulk)              │
│  5. Send heartbeat                  │
└─────────────────────────────────────┘
```

---

## 📊 Impact Summary

### Before Cleanup
- **Total API Methods**: 7 manual methods in `api_service.dart`
- **Redundant Code**: 4 methods (57% waste)
- **Critical Missing**: 3 endpoints not connected
- **Architecture**: ❌ Confused (mix of API calls and snapshot)

### After Cleanup
- **Total API Methods**: 0 manual methods (all via generated client)
- **Redundant Code**: 0 methods
- **Critical Missing**: 0 endpoints (all connected)
- **Architecture**: ✅ Clean offline-first design

---

## ✅ Summary

### ✅ Currently Working (Keep)
1. Authentication (JWT)
2. Token refresh
3. Heartbeat reporting
4. Check for updates

### ⏳ Need to Connect (Priority)
1. Snapshot download endpoint
2. Boarding events bulk upload
3. Device logs upload

### ❌ Need to Remove (Cleanup)
1. `uploadStudentFace()` method
2. `uploadLocation()` method
3. `getStudents()` method
4. `recordBoarding()` method

### Total Work Needed
- **Connect 3 APIs**: ~30 minutes
- **Remove 4 methods**: ~15 minutes
- **Total**: ~45 minutes to complete architecture cleanup! 🚀

---

**Result**: Clean, efficient, offline-first kiosk architecture with minimal API dependencies!
