#!/bin/bash
# Seed Permission Groups Operation

set -euo pipefail

echo "🌱 Seeding permission groups..."

JOB_NAME="easypool-seed-groups-${ENVIRONMENT}"

if [ "$DRY_RUN" = "true" ]; then
  echo "🔍 DRY RUN - Would seed the following groups:"
  echo "  - Super Administrator"
  echo "  - Backend Engineer"
  echo "  - School Administrator"
  echo "  - Parent"
  echo "  - New User"
else
  echo "🚀 Seeding groups"
  gcloud run jobs execute "$JOB_NAME" \
    --region=asia-south1 \
    --wait

  echo "✅ Groups seeded successfully!"
fi
