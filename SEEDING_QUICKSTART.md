# EasyPool Seeding - Quick Start Guide

## Summary

I've created comprehensive seed data files modeled after The Heritage School's transport system. All data is ready to load into your Google Cloud Run deployment.

## What Was Created

### Seed Data Files (`backend_easy/seed_data/`)

1. **schools.json** - 1 school (The Heritage School)
2. **routes.json** - 8 bus routes covering Kolkata areas
3. **bus_stops.json** - 15 bus stops mapped to routes
4. **buses.json** - 8 buses with kiosks
5. **kiosks.json** - 8 kiosk devices
6. **sample_students.json** - 5 students + 5 parents (with encrypted PII)

### Management Command

**File:** `app/students/management/commands/seed_all_data.py`

Loads all seed data in correct dependency order with:
- Foreign key resolution
- Idempotent operations (safe to run multiple times)
- Transaction safety
- Clear logging

## How to Use

### Local Development

```bash
cd backend_easy
python manage.py seed_all_data
```

### Docker Container

```bash
docker-compose exec web python manage.py seed_all_data
```

### Clear and Reseed (DESTRUCTIVE)

```bash
python manage.py seed_all_data --clear
```

## Google Cloud Run Deployment

### Recommended: Cloud Run Job (Best Practice)

```bash
# 1. Create the seeding job
gcloud run jobs create easypool-seed-data \
  --image=gcr.io/YOUR_PROJECT/easypool-backend:latest \
  --region=asia-south1 \
  --set-env-vars="DATABASE_URL=...,ENCRYPTION_KEY=..." \
  --set-secrets="DJANGO_SECRET_KEY=django-secret:latest" \
  --command="bash,-c" \
  --args="python manage.py migrate && python manage.py seed_groups && python manage.py seed_all_data" \
  --task-timeout=15m

# 2. Execute the job (run once after deployment)
gcloud run jobs execute easypool-seed-data --region=asia-south1 --wait

# 3. Check logs
gcloud run jobs executions list --job=easypool-seed-data
```

### Alternative: Bake into Docker Image (Not Recommended)

Add to Dockerfile BEFORE `USER django`:

```dockerfile
# Copy seed data
COPY --chown=django:django seed_data/ /app/seed_data/

# Run seeding (requires database connection at build time - NOT IDEAL)
# RUN python manage.py seed_all_data  # Don't do this - run as job instead
```

### Alternative: Conditional Startup Script

Modify Dockerfile startup script to check if data exists:

```bash
# After migrations in start.sh:
if python manage.py shell -c "from students.models import School; exit(0 if School.objects.exists() else 1)"; then
    echo "[SEED] Data exists - skipping"
else
    echo "[SEED] No data - running seed..."
    python manage.py seed_all_data
fi
```

## Data Overview

### Routes (Heritage School Style)

- **Ankuran Route 01** - Bagbazar Area (3 stops)
- **Ankuran Route 02** - Salt Lake Sector V (3 stops)
- **Ankuran Route 03** - New Town (3 stops)
- **Route 04** - Park Street Area (3 stops)
- **Route 05** - South Kolkata (3 stops)
- **Route 06-08** - East/North/Howrah zones

### Bus Fleet

- 8 buses (BUS-001 to BUS-008)
- Each with unique license plate (WB 02 AC XXXX)
- Each with dedicated kiosk device
- 7 active, 1 in maintenance
- Capacity: 38-50 seats

### Sample Data

- 5 students with encrypted names
- 5 parents with encrypted emails/phones
- Students assigned to different buses/routes
- GPS coordinates for home addresses

## Verification

After seeding, verify data:

```bash
python manage.py shell

>>> from students.models import School, Student
>>> from buses.models import Bus, Route
>>>
>>> print(f"Schools: {School.objects.count()}")
>>> print(f"Routes: {Route.objects.count()}")
>>> print(f"Buses: {Bus.objects.count()}")
>>> print(f"Students: {Student.objects.count()}")
```

Expected output:
```
Schools: 1
Routes: 8
Buses: 8
Students: 5
```

## Next Steps

1. **Seed Groups/Permissions:**
   ```bash
   python manage.py seed_groups
   ```

2. **Create Admin User** (already done via `ensure_bootstrap_admin`):
   - Username: `admin123`
   - Password: `EasyPool2025Admin`

3. **Seed Boarding Events** (for testing dashboard):
   ```bash
   python manage.py seed_boarding_events --count=100
   ```

4. **Add Student Photos:**
   - Upload via admin panel at `/admin/students/student/`
   - Or place in `seed_data/dataset/student_name/` folders

## Important Notes

### Environment Variables Required

```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
ENCRYPTION_KEY=<your-fernet-key>  # Must be same across all environments
DJANGO_SECRET_KEY=<your-secret>
```

### Security

- Sample parent data uses FAKE emails/phones
- Student/parent names are encrypted using `ENCRYPTION_KEY`
- DO NOT commit real PII to seed files
- Use different seed data for production

### Idempotency

The command is idempotent - it checks if data exists before creating:
- Schools created by name (unique)
- Routes created by name (unique)
- Buses created by license plate (unique)
- Safe to run multiple times

## Troubleshooting

**Error: "Seed data directory not found"**
- Ensure `seed_data/` exists in Docker image
- Check path: default is `/app/seed_data`

**Error: Foreign key violations**
- Data loads in dependency order (schools -> routes -> buses -> students)
- Check that referenced routes/buses exist in JSON files

**Error: Encryption errors**
- Ensure `ENCRYPTION_KEY` environment variable is set
- Key must be valid Fernet key

**Error: Job timeout**
- Increase Cloud Run job timeout: `--task-timeout=20m`

## Customization

### Add More Routes

Edit `seed_data/routes.json`:

```json
{
  "model": "buses.route",
  "fields": {
    "name": "Route 09 - Custom Area",
    "description": "Custom route description",
    "color_code": "#FF5733",
    "line_pattern": "solid",
    "is_active": true
  }
}
```

### Add More Students

Edit `seed_data/sample_students.json` following the existing pattern.

### Custom Data Directory

```bash
python manage.py seed_all_data --data-dir=/path/to/custom/seed_data
```

## Documentation

- Full documentation: [seed_data/README.md](seed_data/README.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Deployment guide: See README.md in seed_data folder

---

**Questions?** Check the detailed README in `backend_easy/seed_data/README.md`
