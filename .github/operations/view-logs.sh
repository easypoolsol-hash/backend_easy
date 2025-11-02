#!/bin/bash
# View Cloud Run Logs Operation

set -euo pipefail

echo "📋 Viewing logs for ${ENVIRONMENT}..."

SERVICE_NAME="easypool-backend-${ENVIRONMENT}"

# Default to last 50 lines, or use EXTRA_ARGS for custom limit
LIMIT="${EXTRA_ARGS:-50}"

echo "🔍 Fetching last ${LIMIT} log entries..."

gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --limit="${LIMIT}" \
  --format="table(timestamp, severity, textPayload)" \
  --order=desc

echo ""
echo "✅ Log fetch complete!"
echo "💡 Tip: Use extra_args to change limit (e.g., '100')"
