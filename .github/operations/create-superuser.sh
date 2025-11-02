#!/bin/bash
# Create Django Superuser Operation

set -euo pipefail

echo "👤 Creating Django superuser..."

# Parse EXTRA_ARGS for username and email (format: "username,email")
if [ -n "$EXTRA_ARGS" ]; then
  USERNAME=$(echo "$EXTRA_ARGS" | cut -d',' -f1)
  EMAIL=$(echo "$EXTRA_ARGS" | cut -d',' -f2)
else
  USERNAME="admin"
  EMAIL="admin@easypool.in"
fi

if [ "$DRY_RUN" = "true" ]; then
  echo "🔍 DRY RUN - Would create superuser:"
  echo "   Username: ${USERNAME}"
  echo "   Email: ${EMAIL}"
  echo "   Environment: ${ENVIRONMENT}"
else
  echo "🚀 Creating superuser: ${USERNAME}"

  # Create superuser via Cloud Run job
  gcloud run jobs execute easypool-create-superuser-${ENVIRONMENT} \
    --region=asia-south1 \
    --args="createsuperuser,--noinput,--username=${USERNAME},--email=${EMAIL}" \
    --wait

  echo "✅ Superuser created!"
  echo "⚠️  Default password: changeme123"
  echo "   Please change it immediately after login"
fi
