# Kiosk API Architecture - Offline-First Design

## 🎯 Executive Summary

Kiosks use an **offline-first architecture** with SQLite snapshots. Most APIs are **redundant** for kiosks because data is cached locally.

---

## 🗄️ Snapshot Contents (SQLite Database)

The snapshot (`SnapshotGenerator`) creates a local SQLite database containing:

### Table 1: `students`
```sql
student_id TEXT PRIMARY KEY
name TEXT NOT NULL
status TEXT NOT NULL DEFAULT 'active'
```
- Contains **only students assigned to THIS bus**
- Filtered by: `assigned_bus__bus_id = kiosk.bus_id`

### Table 2: `face_embeddings`
```sql
embedding_id INTEGER PRIMARY KEY
student_id TEXT NOT NULL
embedding_data BLOB NOT NULL  -- 192 floats (768 bytes)
quality_score REAL NOT NULL
```
- Contains face recognition vectors for students on THIS bus
- Embeddings are **pre-computed server-side** and fetched from Qdrant

### Table 3: `sync_metadata`
```sql
key TEXT PRIMARY KEY
value TEXT NOT NULL
```
- `sync_timestamp` - When snapshot was created
- `bus_id` - Which bus this snapshot is for
- `student_count` - Number of students
- `embedding_count` - Number of embeddings
- `content_hash` - Integrity verification hash

---

## ✅ Required Kiosk APIs (MINIMAL SET)

### 1. Authentication
- `POST /api/v1/auth/` - Login
- `POST /api/v1/auth/token/refresh/` - Keep session alive

### 2. Snapshot Sync
- `GET /api/v1/kiosks/{kiosk_id}/check-updates/?last_sync=X` - Check if snapshot outdated
- `GET /api/v1/kiosks/{kiosk_id}/snapshot/` - Download new snapshot (SQLite file)

### 3. Device Monitoring
- `POST /api/v1/kiosks/{kiosk_id}/heartbeat/` - Report device health

### 4. Data Upload (When Online)
- `POST /api/v1/boarding-events/bulk/` - Upload attendance records (batch)
- `POST /api/v1/kiosks/{kiosk_id}/logs/` - Upload device logs

---

## ❌ Redundant APIs (DO NOT USE FROM KIOSKS)

### Read Operations (Data in Snapshot)

#### ❌ `GET /api/v1/students/`
**Why redundant**: Student data is in snapshot
```dart
// WRONG: Calling API
final students = await apiService.getStudents();

// RIGHT: Reading from snapshot
final students = await databaseService.getAllStudents();
```

#### ❌ `GET /api/v1/students/{id}/`
**Why redundant**: Individual student details in snapshot
```dart
// WRONG: Calling API
final student = await apiService.getStudent(id);

// RIGHT: Reading from snapshot
final student = await databaseService.getStudent(id);
```

#### ❌ `GET /api/v1/face-embeddings/`
**Why redundant**: Embeddings in snapshot
```dart
// WRONG: Calling API
final embeddings = await apiService.getFaceEmbeddings();

// RIGHT: Reading from snapshot
final embeddings = await databaseService.getAllEmbeddings();
```

#### ❌ `GET /api/v1/buses/`
**Why redundant**: Bus ID in snapshot metadata
```dart
// WRONG: Calling API
final bus = await apiService.getBus(busId);

// RIGHT: Reading from snapshot
final busId = await databaseService.getMetadata('bus_id');
```

#### ❌ `GET /api/v1/routes/`
**Why redundant**: Routes not needed for face recognition
- Kiosks don't need route information
- Route data is for admin management only

### Write Operations (Server-Side Only)

#### ❌ `POST /api/v1/face-embeddings/` - **REMOVED**
**Why removed**: Embeddings are generated **server-side**, not by kiosks!

**Architecture**:
1. Admin uploads student photos via admin panel
2. **Backend generates embeddings** using ML model (FaceNet, ArcFace, etc.)
3. Embeddings stored in Qdrant vector database
4. **Snapshot generator fetches embeddings from Qdrant**
5. Kiosk downloads pre-computed embeddings in snapshot

**Implementation**: Changed `FaceEmbeddingMetadataViewSet` from `ModelViewSet` to `ReadOnlyModelViewSet`
- POST, PUT, PATCH, DELETE methods **completely removed**
- Only GET operations allowed (for admin viewing)

---

## 🏗️ Offline-First Architecture

```
┌─────────────────────────────────────────────────┐
│  KIOSK OFFLINE MODE (99% of the time)           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ├─ Read students → FROM SNAPSHOT (SQLite)      │
│  ├─ Read embeddings → FROM SNAPSHOT (SQLite)    │
│  ├─ Face recognition → LOCAL (using snapshot)   │
│  └─ Record boarding → LOCAL QUEUE (for upload)  │
└─────────────────────────────────────────────────┘
                    ↓↓↓ Periodic Sync ↓↓↓
┌─────────────────────────────────────────────────┐
│  KIOSK ONLINE MODE (Once per day)               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ├─ Check if snapshot outdated → API call       │
│  ├─ Download new snapshot → API call            │
│  ├─ Upload boarding events → API call (bulk)    │
│  └─ Upload device logs → API call               │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Implementation Notes

### Backend Changes
1. ✅ **Changed** `FaceEmbeddingMetadataViewSet` to `ReadOnlyModelViewSet`
   - Location: `backend_easy/app/students/views.py`
   - Effect: POST/PUT/DELETE completely removed

### Frontend Changes Needed
2. ⏳ **Remove redundant API calls** from `api_service.dart`:
   - Remove `getStudents()`
   - Remove `getStudent(id)`
   - Remove `getFaceEmbeddings()`
   - Remove `uploadStudentFace()`
   - Remove `uploadLocation()`

3. ⏳ **Connect missing critical APIs**:
   - Connect snapshot download endpoint
   - Fix boarding events endpoint (use bulk upload)
   - Add device logs upload endpoint

---

## 📊 API Status Summary

| Endpoint | Admin Needs? | Kiosk Needs? | Status |
|----------|--------------|--------------|--------|
| `GET /api/v1/students/` | ✅ Yes | ❌ No (in snapshot) | Keep for admins |
| `POST /api/v1/students/` | ✅ Yes | ❌ No | Keep for admins |
| `GET /api/v1/face-embeddings/` | ✅ Yes | ❌ No (in snapshot) | Keep for admins |
| `POST /api/v1/face-embeddings/` | ❌ No | ❌ No | **REMOVED** |
| `GET /api/v1/buses/` | ✅ Yes | ❌ No (in snapshot) | Keep for admins |
| `GET /api/v1/routes/` | ✅ Yes | ❌ No | Keep for admins |
| `GET /api/v1/kiosks/{id}/snapshot/` | ❌ No | ✅ Yes | ⏳ Connect |
| `POST /api/v1/boarding-events/bulk/` | ❌ No | ✅ Yes | ⏳ Connect |

---

## 🔒 Security Benefits

### Removed Attack Surface
- Kiosks **cannot** POST arbitrary embeddings
- Kiosks **cannot** modify student data
- All data writes go through authenticated admin panel

### Data Integrity
- Embeddings generated with **consistent model/version**
- Quality control enforced server-side
- Snapshot content hash prevents tampering

---

## 📝 Next Steps

1. ✅ **Done**: Remove POST from face-embeddings endpoint
2. ⏳ **Todo**: Clean up redundant methods in Flutter `api_service.dart`
3. ⏳ **Todo**: Connect missing critical APIs (snapshot, bulk upload, logs)
4. ⏳ **Todo**: Test offline mode with real snapshot data

---

## 🎯 Summary

**Key Insight**: Kiosks use an **offline-first architecture** with SQLite snapshots.

**80% of APIs are redundant** because data is cached locally. Only **5 endpoints** are actually needed:
1. Auth (login, refresh)
2. Check updates
3. Download snapshot
4. Upload boarding events
5. Upload logs

This is the **correct architecture** for offline-capable edge devices! 🚀
