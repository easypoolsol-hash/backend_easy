# EasyPool Seed Data - Deployment Guide

## Overview

This directory contains JSON seed data files for the EasyPool backend system, inspired by The Heritage School's transport system structure. The data can be loaded using the `seed_all_data` management command.

## Data Files Structure

```
seed_data/
├── schools.json          # School information (1 school)
├── routes.json           # 8 bus routes covering Kolkata
├── bus_stops.json        # 15 bus stops across routes
├── buses.json            # 8 buses with kiosk devices
├── kiosks.json           # 8 kiosk devices (one per bus)
└── sample_students.json  # 5 sample students + 5 parents
```

## Data Hierarchy

```
School (The Heritage School)
  ├── Routes (8)
  │   └── Bus Stops (15 total, mapped to routes)
  │       └── Route-Stop relationships (with sequence)
  ├── Buses (8)
  │   ├── Assigned to Routes
  │   └── Linked to Kiosks (device_id)
  ├── Kiosks (8)
  │   └── One per bus
  └── Students (5 sample)
      ├── Assigned to Buses
      └── Linked to Parents (5)
```

## Routes Overview (Inspired by Heritage School)

1. **Ankuran Route 01** - Bagbazar Area (3 stops)
2. **Ankuran Route 02** - Salt Lake Sector V (3 stops)
3. **Ankuran Route 03** - New Town (3 stops)
4. **Route 04** - Park Street Area (3 stops)
5. **Route 05** - South Kolkata (3 stops)
6. **Route 06** - East Kolkata
7. **Route 07** - North Kolkata
8. **Route 08** - Howrah Bridge Zone

## Usage

### Option 1: Run Locally (Development)

```bash
# From backend_easy directory
python manage.py seed_all_data
```

### Option 2: Run in Docker Container

```bash
docker-compose exec web python manage.py seed_all_data
```

### Option 3: Clear and Reseed

```bash
python manage.py seed_all_data --clear
```

**⚠️ WARNING:** `--clear` flag will DELETE all existing data!

## Google Cloud Run Deployment Strategies

### Strategy 1: Bake Data into Docker Image (NOT RECOMMENDED)

**Pros:**
- Data available immediately on container startup
- No external dependencies

**Cons:**
- ❌ Inflates image size unnecessarily
- ❌ Data becomes stale - requires image rebuild to update
- ❌ Violates immutable infrastructure principles
- ❌ Cannot update data without redeployment
- ❌ Makes testing harder (data baked in)

**Implementation:**
```dockerfile
# In Dockerfile (BEFORE USER django)
COPY --chown=django:django seed_data/ /app/seed_data/
RUN python manage.py seed_all_data
```

### Strategy 2: Cloud Run Job (RECOMMENDED) ✅

**Pros:**
- ✅ Separates data initialization from application
- ✅ Idempotent - safe to run multiple times
- ✅ Can be scheduled or manually triggered
- ✅ Follows industry best practices (migrations as jobs)
- ✅ Can be run in CI/CD pipeline

**Cons:**
- Requires manual trigger or CI/CD integration

**Implementation:**

1. **Create Cloud Run Job for seeding:**

```bash
# Upload seed data to Google Cloud Storage (one-time)
gsutil -m cp -r seed_data/ gs://YOUR_BUCKET/seed_data/

# Create Cloud Run Job
gcloud run jobs create easypool-seed-data \
  --image=gcr.io/YOUR_PROJECT/easypool-backend:latest \
  --region=asia-south1 \
  --set-env-vars="DATABASE_URL=postgresql://...,ENCRYPTION_KEY=..." \
  --set-secrets="DJANGO_SECRET_KEY=django-secret:latest" \
  --command="python,manage.py,seed_all_data" \
  --task-timeout=10m \
  --max-retries=2

# Execute the job
gcloud run jobs execute easypool-seed-data --region=asia-south1
```

2. **Or run as one-off task using existing service:**

```bash
# Get a shell in running Cloud Run instance
gcloud run services proxy easypool-backend --region=asia-south1

# Or use Cloud Run revisions
gcloud run jobs create seed-job \
  --execute-now \
  --image=gcr.io/YOUR_PROJECT/easypool-backend:latest \
  --set-env-vars="..." \
  --command="bash,-c,python manage.py migrate && python manage.py seed_groups && python manage.py seed_all_data"
```

### Strategy 3: Startup Script (CONDITIONAL SEEDING) ✅

**Pros:**
- ✅ Automatic on first deployment
- ✅ No manual intervention needed
- ✅ Idempotent - checks if data exists

**Cons:**
- Increases cold start time (first boot only)
- Requires careful idempotency checks

**Implementation:**

Modify Dockerfile startup script:

```bash
# In Dockerfile RUN echo '#!/bin/bash\n\
...
# After migrations complete:
# Seed initial data (idempotent - checks if data exists)
if python manage.py shell -c "from students.models import School; exit(0 if School.objects.exists() else 1)"; then
    echo "[SEED] Data already exists - skipping seed"
else
    echo "[SEED] No data found - running initial seed..."
    python manage.py seed_all_data || echo "[SEED] Seeding failed (non-fatal)"
fi
...
```

### Strategy 4: Google Cloud Storage + Init Container

**Pros:**
- ✅ Data stored externally
- ✅ Easy to update without redeployment
- ✅ Versioned data files

**Cons:**
- More complex setup
- Requires GCS permissions

**Implementation:**

```bash
# 1. Upload seed data to GCS
gsutil -m cp -r seed_data/ gs://easypool-config/seed_data/

# 2. Modify Dockerfile to download on startup
RUN echo 'gsutil -m cp -r gs://easypool-config/seed_data/ /app/seed_data/' >> /app/start.sh
```

## Recommended Approach for Production

### **Hybrid Strategy: Cloud Run Job + Conditional Startup**

1. **Initial Deployment:**
   - Run Cloud Run Job to seed data: `gcloud run jobs execute easypool-seed-data`
   - Job runs migrations + groups + seed data

2. **Subsequent Deployments:**
   - Startup script checks if data exists
   - If no data (e.g., new database), auto-seeds
   - Otherwise, skips seeding

3. **Data Updates:**
   - Update JSON files in GCS
   - Re-run Cloud Run Job manually
   - Or update via admin panel

### Implementation Steps:

```bash
# 1. Create seeding job (one-time setup)
gcloud run jobs create easypool-init-data \
  --image=gcr.io/$PROJECT_ID/easypool-backend:latest \
  --region=asia-south1 \
  --set-env-vars="DATABASE_URL=$DATABASE_URL,ENCRYPTION_KEY=$ENCRYPTION_KEY" \
  --set-secrets="DJANGO_SECRET_KEY=django-secret:latest" \
  --command="bash,-c" \
  --args="python manage.py migrate && python manage.py seed_groups && python manage.py seed_all_data" \
  --task-timeout=15m \
  --max-retries=3

# 2. Execute job on initial deployment
gcloud run jobs execute easypool-init-data --region=asia-south1 --wait

# 3. Verify data loaded
gcloud run jobs executions logs read [EXECUTION_NAME] --region=asia-south1
```

## Data Management After Seeding

### Adding More Data

After initial seeding, you can:

1. **Via Admin Panel:** Add schools, routes, buses, students via `/admin/`
2. **Via API:** Use OpenAPI endpoints to create data
3. **Custom Scripts:** Create additional management commands for bulk imports

### Updating Existing Data

```bash
# Update specific records via management command
python manage.py shell

>>> from students.models import School
>>> school = School.objects.get(name="The Heritage School")
>>> school.address = "Updated Address"
>>> school.save()
```

### Clearing and Reseeding

```bash
# DANGER: This deletes ALL data
python manage.py seed_all_data --clear
```

## Environment Variables Required

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Encryption (for PII fields)
ENCRYPTION_KEY=<your-fernet-key>

# Django
DJANGO_SECRET_KEY=<your-secret-key>
```

## Security Considerations

1. **PII Encryption:**
   - Student names, parent names, emails, phones are encrypted at rest
   - `ENCRYPTION_KEY` must be same across all environments

2. **Seed Data Security:**
   - Sample data uses fake emails/phones
   - DO NOT commit real PII to seed files
   - Use environment-specific seed data for staging/prod

3. **Cloud Storage:**
   - If using GCS, ensure bucket has restricted access
   - Use workload identity for Cloud Run jobs

## Monitoring

```bash
# Check seed job status
gcloud run jobs executions list --job=easypool-init-data --region=asia-south1

# View logs
gcloud run jobs executions describe [EXECUTION_NAME] --region=asia-south1

# Monitor application startup
gcloud logging read "resource.type=cloud_run_revision AND textPayload=~'SEED'" --limit 50
```

## Troubleshooting

### Issue: "Seed data directory not found"
**Solution:** Ensure seed_data directory is copied to Docker image or mounted as volume

### Issue: Foreign key violations
**Solution:** Check data files - buses reference routes, students reference buses/schools

### Issue: Encryption errors
**Solution:** Ensure `ENCRYPTION_KEY` environment variable is set and valid

### Issue: Job timeout
**Solution:** Increase `--task-timeout` for Cloud Run Job

## Next Steps

After seeding data, you can:

1. **Create Admin User:** Already done via `ensure_bootstrap_admin`
2. **Seed Groups/Permissions:** `python manage.py seed_groups`
3. **Generate Boarding Events:** `python manage.py seed_boarding_events --count=100`
4. **Test Face Recognition:** Upload student photos via admin panel

---

**Questions?** Check the main project documentation or [ARCHITECTURE.md](../../ARCHITECTURE.md)
