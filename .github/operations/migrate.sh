#!/bin/bash
# Database Migration Operation

set -euo pipefail

echo "🗄️ Running database migration..."

JOB_NAME="easypool-migrate-${ENVIRONMENT}"

if [ "$DRY_RUN" = "true" ]; then
  echo "🔍 DRY RUN - Showing planned migrations"
  gcloud run jobs execute "$JOB_NAME" \
    --region=asia-south1 \
    --args="showmigrations${EXTRA_ARGS:+,$EXTRA_ARGS}" \
    --wait
else
  echo "🚀 Applying migrations"
  gcloud run jobs execute "$JOB_NAME" \
    --region=asia-south1 \
    --args="migrate${EXTRA_ARGS:+,$EXTRA_ARGS}" \
    --wait

  echo "✅ Migrations applied successfully!"
fi
