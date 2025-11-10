# Database Connection Pooling for Cloud Run

## Problem
Cloud Run applications scale horizontally (create multiple instances). Each instance opens database connections, which can exhaust PostgreSQL's connection limit, causing:
```
FATAL: remaining connection slots are reserved for non-replication superuser connections
```

## Solution Implemented

### 1. Reduced Connection Lifetime
- Changed `CONN_MAX_AGE` from 600 seconds (10 minutes) to 60 seconds (1 minute)
- Connections are recycled more frequently, reducing the total number of held connections

### 2. Per-Instance Connection Limit
- Added `POOL_SIZE` configuration (default: 5 connections per instance)
- Configurable via `DB_POOL_SIZE` environment variable

## Cloud SQL Configuration

### Check Current Settings
```bash
gcloud sql instances describe easypool-db --project=easypool-backend
```

### Recommended Settings

#### Option 1: Increase max_connections (Quick Fix)
```bash
gcloud sql instances patch easypool-db \
  --database-flags max_connections=100 \
  --project=easypool-backend
```

**Calculation:**
- If you expect max 10 Cloud Run instances
- Each instance uses 5 connections (DB_POOL_SIZE)
- Total needed: 10 × 5 = 50 connections
- Add 50% buffer: 50 × 1.5 = 75 connections
- **Recommended: 100 connections**

#### Option 2: Limit Cloud Run Max Instances
```bash
gcloud run services update easypool-backend-dev \
  --max-instances=10 \
  --region=asia-south1
```

### Current Configuration
The code now supports:
- `DB_POOL_SIZE`: Max connections per Cloud Run instance (default: 5)
- `CONN_MAX_AGE`: Connection lifetime in seconds (default: 60)

## Environment Variables

Set in Cloud Run environment:
```bash
# Optional: Adjust pool size per instance (default: 5)
DB_POOL_SIZE=5

# Cloud Run settings
--max-instances=10
--concurrency=80
```

## Deployment Steps

### 1. Update Cloud SQL max_connections
```bash
# Check current value
gcloud sql instances describe easypool-db --format="value(settings.databaseFlags)"

# Update to 100 connections
gcloud sql instances patch easypool-db \
  --database-flags max_connections=100 \
  --project=easypool-backend
```

### 2. Deploy Updated Code
```bash
git add .
git commit -m "Fix database connection exhaustion in Cloud Run"
git push origin develop
```

### 3. Set Cloud Run Limits (Optional)
```bash
gcloud run services update easypool-backend-dev \
  --max-instances=10 \
  --min-instances=1 \
  --region=asia-south1
```

## Monitoring

### Check Active Connections
```sql
SELECT count(*) FROM pg_stat_activity;
SELECT max_conn,used,res_for_super FROM
  (SELECT count(*) used FROM pg_stat_activity) t1,
  (SELECT setting::int max_conn FROM pg_settings WHERE name='max_connections') t2,
  (SELECT setting::int res_for_super FROM pg_settings WHERE name='superuser_reserved_connections') t3;
```

### Cloud Run Metrics
Monitor in Cloud Console:
- Instance count
- Connection errors
- Response times

## Best Practices

1. **Set max_connections higher than needed**
   - Formula: `(max_instances × pool_size) × 1.5`
   - Example: `(10 × 5) × 1.5 = 75` → Use 100

2. **Limit Cloud Run max instances**
   - Prevents runaway scaling
   - Protects database from connection exhaustion

3. **Use connection pooling**
   - `CONN_MAX_AGE`: 60 seconds (balance between performance and resource usage)
   - `DB_POOL_SIZE`: 5 connections per instance (sufficient for most workloads)

4. **Consider pgbouncer for high-scale**
   - For applications with >20 Cloud Run instances
   - Deploy as a sidecar or separate service

## Troubleshooting

### Still Getting Connection Errors?

1. **Check actual connection count:**
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'your_database_name';
   ```

2. **Verify max_connections:**
   ```sql
   SHOW max_connections;
   ```

3. **Check Cloud Run instance count:**
   ```bash
   gcloud run services describe easypool-backend-dev --region=asia-south1 --format="value(status.traffic[0].percent)"
   ```

4. **Reduce CONN_MAX_AGE further:**
   - Set to 30 seconds if still having issues
   - Trade-off: More connection overhead, but safer

5. **Reduce DB_POOL_SIZE:**
   - Set to 3 connections per instance
   - Trade-off: May impact performance under high concurrency

## References
- [Django CONN_MAX_AGE](https://docs.djangoproject.com/en/5.0/ref/settings/#conn-max-age)
- [Cloud Run Connection Management](https://cloud.google.com/sql/docs/postgres/manage-connections)
- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)
