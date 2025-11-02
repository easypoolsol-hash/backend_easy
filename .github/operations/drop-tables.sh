#!/bin/bash
# Drop All Tables Operation (DANGEROUS!)

set -euo pipefail

echo "⚠️  WARNING: This will DROP ALL TABLES!"

if [ "$ENVIRONMENT" = "production" ]; then
  echo "❌ BLOCKED: Cannot drop tables in production"
  exit 1
fi

if [ "$DRY_RUN" = "true" ]; then
  echo "🔍 DRY RUN - Would drop all tables in ${ENVIRONMENT}"
  echo "   This would delete:"
  echo "   - All user data"
  echo "   - All students, buses, kiosks"
  echo "   - All events and logs"
  echo "   - Migration history"
else
  echo "🗑️  Dropping all tables..."

  # Connect to Cloud SQL and drop all tables
  gcloud sql connect easypool-db-${ENVIRONMENT} \
    --user=postgres \
    --quiet \
    --database=easypool_${ENVIRONMENT} \
    << 'SQL'
DO $$ DECLARE
    r RECORD;
BEGIN
    -- Drop all tables
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;
SQL

  echo "✅ All tables dropped!"
  echo "⚠️  Remember to run migrations next!"
fi
